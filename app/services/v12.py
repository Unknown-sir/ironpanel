
from __future__ import annotations
import base64, hmac, hashlib, struct, time, secrets
from datetime import datetime, timedelta
from flask import request
from werkzeug.security import generate_password_hash, check_password_hash
from ..core.extensions import db
from ..core.models import VpnUser, ServicePlan, WalletTransaction, Invoice, PaymentRecord, LoginHistory, TwoFactorSecret, RecoveryCode, TelegramCommandLog, Coupon
from .provisioning import sync_user, telegram_notify, user_access_status, user_usage_summary

def wallet_balance(user_id):
    rows = WalletTransaction.query.filter_by(user_id=user_id, status='done').all()
    return sum((r.amount or 0) if r.kind in ('credit','refund') else -(r.amount or 0) for r in rows)

def apply_plan(user: VpnUser, plan: ServicePlan):
    if plan.days and plan.days > 0:
        base = user.expires_at if user.expires_at and user.expires_at > datetime.utcnow() else datetime.utcnow()
        user.expires_at = base + timedelta(days=plan.days)
    else:
        user.expires_at = None
    user.data_limit_mb = 0 if not plan.traffic_gb else int(plan.traffic_gb) * 1024
    user.protocol_permissions = plan.protocols
    db.session.commit(); sync_user(user)
    return user

def create_invoice_for_user(user_id, amount, description='', currency='USD'):
    inv = Invoice(user_id=user_id, amount=float(amount or 0), currency=currency, status='unpaid', description=description)
    db.session.add(inv); db.session.commit(); return inv

def mark_invoice_paid(invoice_id, provider='manual', authority=''):
    inv = Invoice.query.get(invoice_id)
    if not inv: return None
    inv.status='paid'
    pay=PaymentRecord(invoice_id=inv.id, provider=provider, amount=inv.amount, currency=inv.currency, status='paid', authority=authority)
    db.session.add(pay)
    if inv.user_id:
        db.session.add(WalletTransaction(user_id=inv.user_id, amount=inv.amount, currency=inv.currency, kind='credit', status='done', reference=f'invoice:{inv.id}', note=inv.description))
    db.session.commit(); return inv

def log_login(username, success, reason=''):
    ip=request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
    ua=(request.headers.get('User-Agent') or '')[:255]
    db.session.add(LoginHistory(username=username, ip=ip, user_agent=ua, success=bool(success), reason=reason)); db.session.commit()

def base32_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')

def _hotp(secret, counter):
    key=base64.b32decode(secret + '='*((8-len(secret)%8)%8), casefold=True)
    msg=struct.pack('>Q', counter)
    hs=hmac.new(key, msg, hashlib.sha1).digest()
    o=hs[-1] & 15
    code=(struct.unpack('>I', hs[o:o+4])[0] & 0x7fffffff) % 1000000
    return f'{code:06d}'

def verify_totp(secret, code, window=1):
    if not secret or not code: return False
    counter=int(time.time()//30)
    return any(hmac.compare_digest(_hotp(secret, counter+i), str(code).zfill(6)) for i in range(-window, window+1))

def ensure_2fa(admin):
    row=TwoFactorSecret.query.filter_by(admin_id=admin.id).first()
    if not row:
        row=TwoFactorSecret(admin_id=admin.id, secret=base32_secret(), enabled=False)
        db.session.add(row); db.session.commit()
    return row

def generate_recovery_codes(admin, count=8):
    RecoveryCode.query.filter_by(admin_id=admin.id, used=False).delete()
    codes=[]
    for _ in range(count):
        c=secrets.token_hex(4)+'-'+secrets.token_hex(4)
        codes.append(c); db.session.add(RecoveryCode(admin_id=admin.id, code_hash=generate_password_hash(c)))
    db.session.commit(); return codes

def verify_recovery_code(admin, code):
    for r in RecoveryCode.query.filter_by(admin_id=admin.id, used=False).all():
        if check_password_hash(r.code_hash, code):
            r.used=True; db.session.commit(); return True
    return False

def handle_telegram_command(text, chat_id=''):
    text=(text or '').strip(); result='Unknown command'
    parts=text.split()
    if text == '/status':
        from .provisioning import service_status
        result='IronPanel online: '+str(service_status())
    elif parts[:1] == ['/user'] and len(parts) >= 2:
        u=VpnUser.query.filter_by(username=parts[1]).first()
        if u:
            ok,reason=user_access_status(u)
            usage=user_usage_summary(u)
            result=f'{u.username}: {reason} | used={usage["used_human"]} | raw={usage["raw_used_human"]} | multiplier={usage["traffic_multiplier_label"]} | limit={usage["total_human"]}'
        else: result='User not found'
    elif parts[:1] == ['/reset'] and len(parts) >= 2:
        u=VpnUser.query.filter_by(username=parts[1]).first()
        if u:
            u.used_upload_mb=0; u.used_download_mb=0; u.used_upload_bytes=0; u.used_download_bytes=0; db.session.commit(); sync_user(u); result='Traffic reset'
        else: result='User not found'
    db.session.add(TelegramCommandLog(chat_id=str(chat_id), command=text, result=result[:255])); db.session.commit()
    telegram_notify(result)
    return result
