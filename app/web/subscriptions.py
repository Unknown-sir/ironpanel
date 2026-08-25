"""Public subscription pages, config downloads, QR codes and user portal."""
import io
import re
import zipfile
from pathlib import Path

from flask import Response, abort, current_app, flash, jsonify, redirect, render_template, request, send_file, send_from_directory, url_for
from flask_login import current_user, login_required

from ..core.extensions import db
from ..core.models import VpnUser
from ..services.provisioning import (
    get_public_host,
    get_setting,
    get_subscription_base_url,
    set_setting,
    set_subscription_theme,
    subscription_theme_settings,
    subscription_url_for_user,
    sync_user,
    user_access_status,
    user_config_payload,
    user_usage_summary,
)
from ..services.xray import xray_link
from ..services.v17 import subscription_for_client
from .common import _collect_usage_for_view
from . import web_bp


def _safe_download_username(username: str) -> str:
    value = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(username or 'user')).strip('._-')
    return value or 'user'

def config_download_name(user: VpnUser, source_filename: str) -> str:
    base = _safe_download_username(user.username)
    name = str(source_filename or '')
    node_match = re.match(r'^node-(\d+)-([a-z0-9_]+)\.(ovpn|conf|txt|yaml)$', name)
    if node_match:
        from ..core.models import Node
        node = Node.query.get(int(node_match.group(1)))
        protocol = node_match.group(2).replace('_', '-')
        extension = node_match.group(3)
        node_label = _safe_download_username(
            (getattr(node, 'server_name', '') if node else '')
            or (getattr(node, 'subscription_label', '') if node else '')
            or (getattr(node, 'name', '') if node else '')
            or f'node-{node_match.group(1)}'
        )
        return f'{base}-{node_label}-{protocol}.{extension}'
    if name.endswith('.ovpn'):
        return f'{base}.ovpn'
    if name == 'wireguard.conf':
        return f'{base}.conf'
    if name == 'xray.txt':
        return f'{base}.txt'
    if name == 'hysteria2.yaml':
        return f'{base}.yaml'
    if name == 'hysteria2.txt':
        return f'{base}-hysteria2.txt'
    if name == 'telegram_proxy.txt':
        return f'{base}-telegram-proxy.txt'
    if name == 'ssh.txt':
        return f'{base}-ssh.txt'
    if name == 'subscription.txt':
        return f'{base}-subscription.txt'
    suffix = Path(name).suffix or '.txt'
    return f'{base}{suffix}'

@web_bp.route('/s/<token>')
def subscription(token):
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    _collect_usage_for_view(5)
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    configs = user_config_payload(u)
    from ..services.direct_locations import subscription_sections
    sections = subscription_sections(configs, get_public_host())
    return render_template(
        'subscription.html', user=u, host=get_public_host(),
        subscription_base_url=get_subscription_base_url(),
        subscription_url=subscription_url_for_user(u), configs=configs, sections=sections,
        download_names={name: config_download_name(u, name) for name in configs.keys()},
        usage=user_usage_summary(u), theme=subscription_theme_settings(),
    )

def _combined_subscription_text(user: VpnUser, configs: dict) -> str:
    from ..services.direct_locations import subscription_sections
    chunks = []
    for section in subscription_sections(configs, get_public_host()):
        heading = ' '.join(x for x in [section.get('flag',''), section.get('title','')] if x).strip()
        chunks.append(f'===== {heading} =====')
        for item in section.get('configs', []):
            if item.get('name') == 'ACCOUNT_STATUS.txt':
                continue
            chunks.append(f'--- {item.get("title", "Config")} ---')
            chunks.append(str(item.get('body') or '').strip())
    return '\n\n'.join(x for x in chunks if x).strip() + '\n'


@web_bp.route('/s/<token>/download-all.zip')
def subscription_download_all(token):
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    ok, reason = user_access_status(u)
    if not ok:
        return reason, 403
    configs = user_config_payload(u)
    buffer = io.BytesIO()
    used_names = set()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for source_name, body in configs.items():
            if source_name == 'ACCOUNT_STATUS.txt':
                continue
            download_name = config_download_name(u, source_name)
            candidate = download_name
            serial = 2
            while candidate in used_names:
                stem = Path(download_name).stem
                suffix = Path(download_name).suffix
                candidate = f'{stem}-{serial}{suffix}'
                serial += 1
            used_names.add(candidate)
            archive.writestr(candidate, str(body or ''))
        archive.writestr(f'{_safe_download_username(u.username)}-all-configs.txt', _combined_subscription_text(u, configs))
    buffer.seek(0)
    return send_file(
        buffer, mimetype='application/zip', as_attachment=True,
        download_name=f'{_safe_download_username(u.username)}-ironpanel-configs.zip',
    )


@web_bp.route('/s/<token>/download/<filename>')
def subscription_download(token, filename):
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    ok, reason = user_access_status(u)
    if not ok:
        return reason, 403
    configs = user_config_payload(u)
    if filename == 'subscription.txt':
        body = _combined_subscription_text(u, configs)
        headers = {'Content-Disposition': f'attachment; filename="{config_download_name(u, filename)}"'}
        return Response(body, mimetype='text/plain; charset=utf-8', headers=headers)
    if filename not in configs or filename == 'ACCOUNT_STATUS.txt':
        abort(404)
    # Public subscription downloads use the token URL, so users do not need to know the profile path.
    return send_from_directory(current_app.config['CONFIG_ROOT'] / 'profiles' / u.username, filename, as_attachment=True, download_name=config_download_name(u, filename))


# ---------------- IronPanel v11: User Portal v2, QR codes, GeoIP helper, OpenAPI ----------------
@web_bp.route('/qr/subscription/<token>.png')
def qr_subscription(token):
    from ..services.v11 import make_qr_png
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    data = subscription_url_for_user(u)
    return Response(make_qr_png(data), mimetype='image/png')

@web_bp.route('/qr/wireguard/<int:user_id>.png')
@login_required
def qr_wireguard(user_id):
    from ..services.v11 import make_qr_png
    u = VpnUser.query.get_or_404(user_id)
    configs = user_config_payload(u)
    data = configs.get('wireguard.conf', '') or ''
    return Response(make_qr_png(data), mimetype='image/png')

@web_bp.route('/qr/xray/<int:user_id>.png')
@login_required
def qr_xray(user_id):
    from ..services.v11 import make_qr_png
    u = VpnUser.query.get_or_404(user_id)
    return Response(make_qr_png(xray_link(u)), mimetype='image/png')

@web_bp.route('/s/<token>/xray-qr.png')
def subscription_xray_qr(token):
    from ..services.v11 import make_qr_png
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    return Response(make_qr_png(xray_link(u)), mimetype='image/png')


@web_bp.route('/s/<token>/wireguard-qr.png')
def subscription_wireguard_qr(token):
    from ..services.v11 import make_qr_png
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    configs = user_config_payload(u)
    return Response(make_qr_png(configs.get('wireguard.conf','')), mimetype='image/png')


@web_bp.route('/s/<token>/qr/<path:name>.png')
def subscription_config_qr(token, name):
    from ..services.v11 import make_qr_png
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    ok, reason = user_access_status(u)
    if not ok:
        return reason, 403
    configs = user_config_payload(u)
    config_name = str(name or '').strip()
    if config_name not in configs:
        abort(404)
    from ..services.direct_locations import protocol_from_config_name
    protocol = protocol_from_config_name(config_name)
    if protocol not in ('wireguard', 'xray', 'hysteria2') or config_name == 'hysteria2.yaml':
        abort(404)
    data = (configs.get(config_name) or '').strip()
    if not data:
        abort(404)
    return Response(make_qr_png(data), mimetype='image/png')

@web_bp.route('/s/<token>/hysteria2-qr.png')
def subscription_hysteria2_qr(token):
    from ..services.v11 import make_qr_png
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    configs = user_config_payload(u)
    return Response(make_qr_png(configs.get('hysteria2.txt','')), mimetype='image/png')

@web_bp.route('/api/openapi.json')
def openapi_json():
    from ..services.v11 import openapi_spec
    return jsonify(openapi_spec('/api/v2'))

@web_bp.route('/api/geoip')
@login_required
def api_geoip():
    from ..services.v11 import geoip_country
    ip = request.args.get('ip','')
    return jsonify(ip=ip, country=geoip_country(ip))

@web_bp.route('/portal/<token>')
def user_portal(token):
    u=VpnUser.query.filter_by(subscription_token=token).first_or_404()
    configs=user_config_payload(u); ok,reason=user_access_status(u)
    return render_template('user_portal.html', user=u, configs=configs, access_ok=ok, access_reason=reason, usage=user_usage_summary(u))

@web_bp.route('/portal/<token>/reset-password', methods=['POST'])
def portal_reset_password(token):
    u = VpnUser.query.filter_by(subscription_token=token).first_or_404()
    new_password = request.form.get('password','').strip()
    if len(new_password) < 6:
        flash('رمز عبور باید حداقل ۶ کاراکتر باشد')
        return redirect(url_for('web.user_portal', token=token))
    u.set_password(new_password)
    u.l2tp_password = new_password
    u.cisco_password = new_password
    db.session.commit(); sync_user(u)
    flash('رمز عبور سرویس‌ها تغییر کرد و پروتکل‌ها sync شدند')
    return redirect(url_for('web.user_portal', token=token))

@web_bp.route('/subscription-manager', methods=['GET','POST'])
@login_required
def subscription_manager():
    if request.method == 'POST':
        set_subscription_theme(request.form)
        set_setting('subscription_domain', (request.form.get('subscription_domain') or '').strip().rstrip('/'))
        flash('قالب، دامنه و تنظیمات صفحه Subscription ذخیره شد')
        return redirect(url_for('web.subscription_manager'))
    return render_template('subscription_manager.html', users=VpnUser.query.order_by(VpnUser.id.desc()).all(), formats=['auto','raw','clash','singbox','hiddify'], theme=subscription_theme_settings(), subscription_domain=get_setting('subscription_domain',''), subscription_base_url=get_subscription_base_url())

@web_bp.route('/s/<token>/<client_type>')
def subscription_client(token, client_type):
    u=VpnUser.query.filter_by(subscription_token=token).first_or_404()
    body,mime,status=subscription_for_client(u, client_type, request=request)
    return current_app.response_class(body, status=status, mimetype=mime)
