"""Billing, plans, wallet, invoices and support tickets."""
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..core.extensions import db
from ..core.models import Coupon, Invoice, ServicePlan, Ticket, VpnUser, WalletTransaction
from ..services.provisioning import log
from ..services.v12 import mark_invoice_paid, wallet_balance
from .common import _allowed_form_protocols
from . import web_bp


@web_bp.route('/billing', methods=['GET','POST'])
@login_required
def billing():
    if request.method=='POST':
        inv=Invoice(user_id=request.form.get('user_id') or None, amount=float(request.form.get('amount') or 0), currency=request.form.get('currency','USD'), status=request.form.get('status','unpaid'), description=request.form.get('description',''))
        db.session.add(inv); db.session.commit(); flash('Invoice created')
        return redirect(url_for('web.billing'))
    return render_template('billing.html', invoices=Invoice.query.order_by(Invoice.id.desc()).all(), users=VpnUser.query.all(), coupons=Coupon.query.all())

@web_bp.route('/plans', methods=['GET','POST'])
@login_required
def finance_plans():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        plan_protocols = _allowed_form_protocols(request.form.getlist('protocols'))
        if not plan_protocols:
            flash('حداقل یک پروتکل برای پلن انتخاب کنید')
            return redirect(url_for('web.finance_plans'))
        p=ServicePlan(name=request.form['name'], days=int(request.form.get('days') or 0), traffic_gb=int(request.form.get('traffic_gb') or 0), price=float(request.form.get('price') or 0), currency=request.form.get('currency','USD'), protocols=','.join(plan_protocols), active=bool(request.form.get('active')))
        db.session.add(p); db.session.commit(); flash('پلن ذخیره شد')
        return redirect(url_for('web.finance_plans'))
    return render_template('plans.html', plans=ServicePlan.query.order_by(ServicePlan.id.desc()).all())

@web_bp.route('/wallet', methods=['GET','POST'])
@login_required
def wallet():
    if request.method=='POST':
        user_id=int(request.form.get('user_id') or 0)
        tx=WalletTransaction(user_id=user_id, amount=float(request.form.get('amount') or 0), currency=request.form.get('currency','USD'), kind=request.form.get('kind','credit'), note=request.form.get('note',''))
        db.session.add(tx); db.session.commit(); flash('تراکنش کیف پول ذخیره شد')
        return redirect(url_for('web.wallet'))
    users=VpnUser.query.order_by(VpnUser.username).all()
    balances={u.id: wallet_balance(u.id) for u in users}
    return render_template('wallet.html', users=users, balances=balances, txs=WalletTransaction.query.order_by(WalletTransaction.id.desc()).limit(100).all())

@web_bp.route('/invoices/<int:invoice_id>/paid', methods=['POST'])
@login_required
def invoice_paid(invoice_id):
    inv=mark_invoice_paid(invoice_id, provider='manual', authority=f'admin:{current_user.username}')
    flash('فاکتور پرداخت شد' if inv else 'فاکتور پیدا نشد')
    return redirect(url_for('web.billing'))

@web_bp.route('/tickets', methods=['GET','POST'])
@login_required
def tickets():
    if request.method == 'POST':
        t = Ticket(subject=request.form['subject'], body=request.form['body'], priority=request.form.get('priority','normal'), department=request.form.get('department','support'), owner_id=current_user.id)
        db.session.add(t); db.session.commit(); log(current_user.username,'create_ticket',t.subject)
        return redirect(url_for('web.tickets'))
    return render_template('tickets.html', tickets=Ticket.query.order_by(Ticket.id.desc()).all())
