"""Dashboard, health probe and system metrics endpoints."""
import psutil
from flask import flash, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..core.models import Node, Ticket, VpnUser
from ..services.provisioning import service_status
from ..services.license import check_license, current_license_features, license_remaining_days
from ..services.v13 import current_version, github_latest_version
from .common import _online_sessions_snapshot, _refresh_sessions_background
from . import web_bp


def _system_stats_snapshot():
    try:
        vm=psutil.virtual_memory(); sw=psutil.swap_memory(); du=psutil.disk_usage('/')
        freq=psutil.cpu_freq()
        cpu_freq=round((freq.current if freq else 0)/1000,2)
        return dict(
            cpu_percent=psutil.cpu_percent(interval=0.05), cpu_freq=cpu_freq,
            ram_percent=vm.percent, ram_used_mb=round(vm.used/1024/1024), ram_total_mb=round(vm.total/1024/1024),
            swap_percent=sw.percent, swap_used_mb=round(sw.used/1024/1024), swap_total_mb=round(sw.total/1024/1024),
            disk_percent=du.percent, disk_used_gb=round(du.used/1024/1024/1024), disk_total_gb=round(du.total/1024/1024/1024),
            cpu_sub=f'{cpu_freq} GHz', ram_sub=f'{round(vm.used/1024/1024)}MB / {round(vm.total/1024/1024)}MB',
            swap_sub=f'{round(sw.used/1024/1024)}MB / {round(sw.total/1024/1024)}MB',
            disk_sub=f'{round(du.used/1024/1024/1024)}GB / {round(du.total/1024/1024/1024)}GB'
        )
    except Exception:
        return dict(cpu_percent=0,cpu_freq=0,ram_percent=0,ram_used_mb=0,ram_total_mb=0,swap_percent=0,swap_used_mb=0,swap_total_mb=0,disk_percent=0,disk_used_gb=0,disk_total_gb=0,cpu_sub='N/A',ram_sub='N/A',swap_sub='N/A',disk_sub='N/A')

@web_bp.route('/api/system/metrics')
@login_required
def system_metrics():
    data = _system_stats_snapshot()
    try:
        lres = check_license(force=False)
        data.update(license_days_remaining=license_remaining_days(lres), license_valid=bool(lres.get('valid') and lres.get('paid')), license_expires_at=lres.get('expires_at',''), license_type=lres.get('license_type','beginer'), license_status=lres.get('status','free'), license_free=not bool(lres.get('valid') and lres.get('paid')))
    except Exception:
        data.update(license_days_remaining=None, license_valid=False, license_expires_at='', license_type='beginer', license_status='free', license_free=True)
    return jsonify(**data)

@web_bp.route('/')
def index():
    return redirect(url_for('web.dashboard') if current_user.is_authenticated else url_for('web.login'))

@web_bp.route('/dashboard')
@login_required
def dashboard():
    users = VpnUser.query.all() if current_user.role == 'main_admin' else VpnUser.query.filter_by(owner_id=current_user.id).all()
    tickets = Ticket.query.order_by(Ticket.id.desc()).limit(8).all()
    nodes = Node.query.all()
    _refresh_sessions_background()
    online_sessions_data = _online_sessions_snapshot()
    # new format: (users_with_sessions, sessions_list)
    if isinstance(online_sessions_data, tuple):
        online_count, online_sessions = online_sessions_data
    else:
        online_count = len(online_sessions_data)
        online_sessions = online_sessions_data
    license_result = check_license(force=False)
    return render_template(
        'dashboard.html',
        users=users,
        tickets=tickets,
        nodes=nodes,
        online_count=online_count,
        online_sessions=online_sessions,
        github=github_latest_version(),
        license_result=license_result,
        license_days=license_remaining_days(license_result),
        license_features=current_license_features(),
        services=service_status(),
        system_stats=_system_stats_snapshot(),
    )

@web_bp.route('/healthz')
def healthz():
    return jsonify(ok=True, service='ironpanel', version=current_version() if 'current_version' in globals() else '')

@web_bp.route('/dashboard/quick-upgrade', methods=['POST'])
@login_required
def dashboard_quick_upgrade():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    latest = github_latest_version(force=True)
    if not latest.get('update_available'):
        flash('نسخه جدیدتری در GitHub پیدا نشد یا بررسی نسخه ناموفق بود.')
        return redirect(url_for('web.dashboard'))
    flash('آپدیت مرحله‌ای شروع می‌شود. صفحه را باز نگه دار تا درصد پیشرفت و لاگ را ببینی.')
    return redirect(url_for('web.updates', autostart=1))
