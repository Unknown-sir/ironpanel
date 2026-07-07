from datetime import datetime, timedelta
import secrets
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='main_admin')
    api_key = db.Column(db.String(96), unique=True, default=lambda: secrets.token_urlsafe(48))
    user_limit = db.Column(db.Integer, default=0)
    traffic_quota_gb = db.Column(db.Integer, default=0)
    panel_path = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class VpnUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    l2tp_password = db.Column(db.String(128), nullable=True)
    cisco_password = db.Column(db.String(128), nullable=True)
    enabled = db.Column(db.Boolean, default=True)
    protocols = db.Column(db.String(120), default='openvpn,ocserv,l2tp,wireguard,xray')
    data_limit_mb = db.Column(db.Integer, default=0)
    used_upload_mb = db.Column(db.Integer, default=0)
    used_download_mb = db.Column(db.Integer, default=0)
    # v13.4: exact byte counters are the source of truth for traffic accounting.
    # The MB columns are kept for backward compatibility and quick sorting.
    used_upload_bytes = db.Column(db.BigInteger, default=0)
    used_download_bytes = db.Column(db.BigInteger, default=0)
    connection_limit = db.Column(db.Integer, default=1)
    allowed_devices = db.Column(db.Integer, default=0)
    protocol_permissions = db.Column(db.String(120), default='openvpn,ocserv,l2tp,wireguard,xray')
    expires_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=30))
    subscription_token = db.Column(db.String(96), unique=True, default=lambda: secrets.token_urlsafe(48))
    wg_private_key = db.Column(db.Text, nullable=True)
    wg_public_key = db.Column(db.Text, nullable=True)
    wg_ip = db.Column(db.String(64), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
    @property
    def used_total_mb(self):
        exact = int((self.used_upload_bytes or 0) + (self.used_download_bytes or 0))
        if exact > 0:
            return exact // (1024 * 1024)
        return (self.used_upload_mb or 0) + (self.used_download_mb or 0)
    @property
    def used_total_bytes(self):
        exact = int((self.used_upload_bytes or 0) + (self.used_download_bytes or 0))
        if exact > 0:
            return exact
        return int(((self.used_upload_mb or 0) + (self.used_download_mb or 0)) * 1024 * 1024)
    @property
    def expired(self):
        # None means unlimited / no expiration. A value of 0 days at creation/edit is stored as None.
        return bool(self.expires_at and self.expires_at < datetime.utcnow())
    def protocol_list(self): return [p for p in (self.protocols or '').split(',') if p]
    def allowed_protocol_list(self): return [p for p in (self.protocol_permissions or self.protocols or '').split(',') if p]

class Node(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    api_key = db.Column(db.String(96), default=lambda: secrets.token_urlsafe(48))
    protocols = db.Column(db.String(120), default='openvpn,ocserv,l2tp,wireguard,xray')
    health = db.Column(db.String(20), default='unknown')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Port(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    protocol = db.Column(db.String(40), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    transport = db.Column(db.String(20), default='udp')
    node_id = db.Column(db.Integer, db.ForeignKey('node.id'), nullable=True)

class AppSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(180), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')
    priority = db.Column(db.String(20), default='normal')
    department = db.Column(db.String(40), default='support')
    user_id = db.Column(db.Integer, db.ForeignKey('vpn_user.id'), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=True)
    unread_for_admin = db.Column(db.Boolean, default=True)
    unread_for_user = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor = db.Column(db.String(120), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    target = db.Column(db.String(120), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BackupRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    size_bytes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DeviceSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('vpn_user.id'), nullable=False)
    protocol = db.Column(db.String(40), default='unknown')
    remote_ip = db.Column(db.String(80), default='')
    device_id = db.Column(db.String(128), default='')
    connected_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

class DailyUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('vpn_user.id'), nullable=False)
    day = db.Column(db.String(10), nullable=False)
    upload_mb = db.Column(db.Integer, default=0)
    download_mb = db.Column(db.Integer, default=0)


class DomainRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), unique=True, nullable=False)
    purpose = db.Column(db.String(80), default='vpn')
    ssl_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FirewallRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    protocol = db.Column(db.String(10), default='tcp')
    action = db.Column(db.String(20), default='allow')
    source = db.Column(db.String(120), default='any')
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DnsProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    primary_dns = db.Column(db.String(80), default='1.1.1.1')
    secondary_dns = db.Column(db.String(80), default='8.8.8.8')
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OnlineSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('vpn_user.id'), nullable=True)
    username = db.Column(db.String(80), nullable=False)
    protocol = db.Column(db.String(40), default='unknown')
    remote_ip = db.Column(db.String(80), default='')
    country = db.Column(db.String(80), default='Unknown')
    device_id = db.Column(db.String(128), default='')
    node_id = db.Column(db.Integer, db.ForeignKey('node.id'), nullable=True)
    connected_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('vpn_user.id'), nullable=True)
    amount = db.Column(db.Float, default=0)
    currency = db.Column(db.String(10), default='USD')
    status = db.Column(db.String(30), default='unpaid')
    description = db.Column(db.String(255), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    percent = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ApiToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(128), unique=True, default=lambda: secrets.token_urlsafe(48))
    scopes = db.Column(db.String(255), default='users:read,users:write')
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RemoteJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.Integer, db.ForeignKey('node.id'), nullable=True)
    action = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(30), default='queued')
    output = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserPortalAccount(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vpn_user_id = db.Column(db.Integer, db.ForeignKey('vpn_user.id'), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)


# ---------------- v12/v13 product modules ----------------
class ServicePlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    days = db.Column(db.Integer, default=30)  # 0 = unlimited
    traffic_gb = db.Column(db.Integer, default=0)  # 0 = unlimited
    price = db.Column(db.Float, default=0)
    currency = db.Column(db.String(10), default='USD')
    protocols = db.Column(db.String(120), default='openvpn,ocserv,l2tp,wireguard,xray')
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WalletTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('vpn_user.id'), nullable=True)
    amount = db.Column(db.Float, default=0)
    currency = db.Column(db.String(10), default='USD')
    kind = db.Column(db.String(30), default='credit')
    status = db.Column(db.String(30), default='done')
    reference = db.Column(db.String(120), default='')
    note = db.Column(db.String(255), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PaymentRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=True)
    provider = db.Column(db.String(80), default='manual')
    amount = db.Column(db.Float, default=0)
    currency = db.Column(db.String(10), default='USD')
    status = db.Column(db.String(30), default='pending')
    authority = db.Column(db.String(120), default='')
    raw_response = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LoginHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), default='')
    ip = db.Column(db.String(80), default='')
    user_agent = db.Column(db.String(255), default='')
    success = db.Column(db.Boolean, default=False)
    reason = db.Column(db.String(120), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RecoveryCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    code_hash = db.Column(db.String(255), nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TwoFactorSecret(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), unique=True, nullable=False)
    secret = db.Column(db.String(80), nullable=False)
    enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TelegramCommandLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(80), default='')
    command = db.Column(db.String(255), default='')
    result = db.Column(db.String(255), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UpdateRelease(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(40), nullable=False)
    channel = db.Column(db.String(30), default='stable')
    download_url = db.Column(db.String(255), default='')
    changelog = db.Column(db.Text, default='')
    published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class HealthCheckRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(30), default='unknown')
    detail = db.Column(db.Text, default='')
    repaired = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------- v14 Telegram sales bot for end-user VPN sales ----------------
class SalesBotCustomer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(32), unique=True, nullable=False)
    username = db.Column(db.String(120), default='')
    first_name = db.Column(db.String(120), default='')
    language_code = db.Column(db.String(10), default='fa')
    trial_used = db.Column(db.Boolean, default=False)
    blocked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SalesBotPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    days = db.Column(db.Integer, default=30)          # 0 = unlimited
    traffic_gb = db.Column(db.Integer, default=0)    # 0 = unlimited
    price = db.Column(db.Float, default=0)
    currency = db.Column(db.String(10), default='IRT')
    protocols = db.Column(db.String(120), default='openvpn,wireguard,ocserv,l2tp,xray')
    connection_limit = db.Column(db.Integer, default=1)
    active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_by_telegram_id = db.Column(db.String(32), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SalesBotOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(32), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('sales_bot_customer.id'), nullable=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('sales_bot_plan.id'), nullable=True)
    vpn_user_id = db.Column(db.Integer, db.ForeignKey('vpn_user.id'), nullable=True)
    order_type = db.Column(db.String(30), default='new')  # new, renew, extra, trial
    status = db.Column(db.String(30), default='pending_payment')  # pending_payment, receipt_sent, approved, rejected, cancelled
    amount = db.Column(db.Float, default=0)
    currency = db.Column(db.String(10), default='IRT')
    receipt_file_id = db.Column(db.String(255), default='')
    receipt_note = db.Column(db.Text, default='')
    admin_note = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)

class SalesBotBroadcast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    target = db.Column(db.String(30), default='all')
    status = db.Column(db.String(30), default='queued')
    sent_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
