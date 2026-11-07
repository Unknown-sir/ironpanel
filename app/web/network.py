"""Network & core services UI: firewall, DNS, domains, SSL, Xray, outbound, speed limits."""
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..core.extensions import db
from ..core.models import DomainRecord, DnsProfile, FirewallRule, Node, OutboundProfile, ProtocolOutboundMap, VpnUser
from ..services.provisioning import (
    active_protocols,
    apply_runtime_configs,
    log,
    set_setting,
    sync_all_users,
    user_access_status,
)
from ..services.firewall_manager import apply_firewall_rules, create_ip_ban, firewall_summary, ip_matches_target, normalize_ip_target
from ..services.ssl_manager import default_ssl_domain, issue_and_apply_ssl, renew_all_ssl, ssl_status
from ..services.geofiles import geofile_status, update_geofiles
from ..services.outbound import (
    apply_outbound_runtime,
    disable_outbound_runtime,
    outbound_runtime_status,
    outbound_settings,
    save_outbound_settings,
    test_outbound_config,
)
from ..services.speed_limit import (
    PROTOCOL_ICONS,
    PROTOCOL_LABELS,
    apply_speed_limits_runtime,
    save_speed_limits,
    save_user_speed_limits,
    speed_limit_rows,
    speed_limit_status,
    speed_limit_user_matrix,
)
from ..services.xray import (
    XRAY_PROFILE_TYPES,
    ensure_reality_keys,
    reset_xray_builder,
    update_xray_builder,
    update_xray_settings,
    write_xray_config,
    xray_builder_enabled,
    xray_builder_inbounds,
    xray_runtime_status,
    xray_settings,
)
from .common import _ensure_famous_dns_profiles_web
from . import web_bp


@web_bp.route('/firewall', methods=['GET','POST'])
@login_required
def firewall():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        action = request.form.get('action') or 'add_rule'
        try:
            if action == 'add_ban':
                target, _family = normalize_ip_target(request.form.get('ip',''))
                remote_ip = (request.headers.get('X-Forwarded-For') or request.remote_addr or '').split(',')[0].strip()
                if remote_ip and ip_matches_target(remote_ip, target) and not request.form.get('confirm_self_ban'):
                    flash('این IP/CIDR با IP فعلی شما هم‌پوشانی دارد. برای جلوگیری از قفل‌شدن، گزینه تأیید را فعال کنید.')
                    return redirect(url_for('web.firewall'))
                r = create_ip_ban(target, request.form.get('name',''))
                log(current_user.username, 'firewall_ip_ban', r.source, r.name)
                flash('IP به لیست بن کامل اضافه شد و قوانین اعمال شدند.')
            elif action == 'add_rule':
                r=FirewallRule(name=request.form['name'], port=int(request.form['port']), protocol=request.form.get('protocol','tcp'), action=request.form.get('rule_action') or request.form.get('action','allow'), source=request.form.get('source','any'), enabled=bool(request.form.get('enabled')))
                db.session.add(r); db.session.commit(); apply_firewall_rules(); flash('Firewall rule saved')
            elif action == 'toggle':
                r = FirewallRule.query.get(int(request.form.get('rule_id') or 0))
                if r:
                    r.enabled = not bool(r.enabled); db.session.commit(); apply_firewall_rules(); flash('وضعیت قانون فایروال تغییر کرد.')
            elif action == 'delete':
                r = FirewallRule.query.get(int(request.form.get('rule_id') or 0))
                if r:
                    db.session.delete(r); db.session.commit(); apply_firewall_rules(); flash('قانون فایروال حذف شد و لیست بن بازسازی شد.')
            elif action == 'reapply':
                apply_firewall_rules(); flash('قوانین فایروال دوباره اعمال شدند.')
        except Exception as exc:
            db.session.rollback()
            flash('خطا در اعمال فایروال: ' + str(exc)[:220])
        return redirect(url_for('web.firewall'))
    return render_template('firewall.html', summary=firewall_summary())

@web_bp.route('/dns', methods=['GET','POST'])
@login_required
def dns_manager():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    _ensure_famous_dns_profiles_web()
    if request.method=='POST':
        action = request.form.get('action') or ('set_default' if request.form.get('set_default') else 'add_custom')
        if action == 'add_defaults':
            _ensure_famous_dns_profiles_web()
            flash('DNSهای معروف اضافه/به‌روزرسانی شدند.')
        elif action == 'set_default':
            DnsProfile.query.update({'is_default':False})
            p = DnsProfile.query.get(int(request.form['profile_id']))
            if p:
                p.is_default=True
                db.session.commit()
                flash('DNS default saved.')
        elif action == 'apply_wireguard':
            p = DnsProfile.query.get(int(request.form['profile_id']))
            if p:
                value = ', '.join([x for x in [p.primary_dns, p.secondary_dns] if x])
                set_setting('wireguard_dns', value)
                db.session.commit()
                try:
                    apply_runtime_configs()
                    sync_all_users(restart=False)
                except Exception as exc:
                    flash('DNS applied, but runtime sync failed: ' + str(exc)[:180])
                    return redirect(url_for('web.dns_manager'))
                flash(f'{p.name} روی WireGuard DNS اعمال شد: {value}')
        else:
            name = (request.form.get('name') or '').strip()
            primary = (request.form.get('primary_dns') or '').strip()
            secondary = (request.form.get('secondary_dns') or '').strip()
            if name and primary:
                db.session.add(DnsProfile(name=name, primary_dns=primary, secondary_dns=secondary))
                db.session.commit()
                flash('DNS profile saved')
        return redirect(url_for('web.dns_manager'))
    return render_template('dns.html', profiles=DnsProfile.query.order_by(DnsProfile.is_default.desc(), DnsProfile.name.asc()).all())

@web_bp.route('/domains', methods=['GET','POST'])
@login_required
def domains():
    if current_user.role != 'main_admin': return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        d=DomainRecord(domain=request.form['domain'], purpose=request.form.get('purpose','vpn'), ssl_enabled=bool(request.form.get('ssl_enabled')))
        db.session.add(d); db.session.commit(); flash('Domain saved')
        return redirect(url_for('web.domains'))
    return render_template('domains.html', domains=DomainRecord.query.all())

@web_bp.route('/ssl', methods=['GET','POST'])
@login_required
def ssl_manager():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action', 'issue')
        if action == 'renew':
            result = renew_all_ssl()
        else:
            result = issue_and_apply_ssl(
                request.form.get('domain') or default_ssl_domain(),
                request.form.get('email', ''),
                force_xray_tls=request.form.get('force_xray_tls') == '1',
            )
            log(current_user.username, 'ssl_issue', result.get('domain',''), result.get('message','')[-500:])
        flash(result.get('message', 'SSL operation finished'))
        return redirect(url_for('web.ssl_manager'))
    return render_template('ssl.html', status=ssl_status(default_ssl_domain()))

@web_bp.route('/ssl/<int:domain_id>/issue', methods=['POST'])
@login_required
def ssl_issue(domain_id):
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    d=DomainRecord.query.get_or_404(domain_id)
    result = issue_and_apply_ssl(d.domain, force_xray_tls=request.form.get('force_xray_tls') == '1')
    flash(result.get('message', 'SSL operation finished'))
    return redirect(url_for('web.domains'))

@web_bp.route('/ssl/renew-all', methods=['POST'])
@login_required
def ssl_renew_all():
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    result = renew_all_ssl()
    flash(result.get('message', 'درخواست تمدید SSL اجرا شد'))
    return redirect(url_for('web.ssl_manager'))

@web_bp.route('/geofiles', methods=['GET','POST'])
@login_required
def geofiles_manager():
    if current_user.role != 'main_admin':
        flash('دسترسی مجاز نیست')
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        res = update_geofiles(request.form.get('source','loyalsoldier'))
        log(current_user.username, 'geofiles_update', request.form.get('source',''), res.get('log','')[-500:])
        flash(res.get('message','GeoFile update finished'))
        return redirect(url_for('web.geofiles_manager'))
    return render_template('geofiles.html', status=geofile_status())

# ---------------- IronPanel v16.7: Outbound Manager ----------------
@web_bp.route('/outbound', methods=['GET','POST'])
@login_required
def outbound_manager():
    # Outbound is intentionally available for all license types, but only the main admin can change routing.
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'disable':
            ok, out = disable_outbound_runtime()
            log(current_user.username, 'outbound_disable', 'runtime', out[-500:])
            flash('Outbound غیرفعال شد' if ok else 'خطا در غیرفعال‌سازی Outbound: ' + out[-800:])
            return redirect(url_for('web.outbound_manager'))
        if action == 'test':
            save_outbound_settings(
                outbound_type=request.form.get('outbound_type','openvpn'),
                config_text=request.form.get('outbound_config',''),
                enabled=request.form.get('outbound_enabled') == '1',
                protocols=request.form.getlist('outbound_protocols') or [],
            )
            ok, out = test_outbound_config()
            log(current_user.username, 'outbound_test', request.form.get('outbound_type',''), out[-500:])
            flash('تست اتصال Outbound موفق بود؛ حالا پروتکل‌ها را انتخاب و Apply کن' if ok else 'تست اتصال Outbound ناموفق بود: ' + out[-1200:])
            return redirect(url_for('web.outbound_manager'))
        if action == 'apply':
            save_outbound_settings(
                outbound_type=request.form.get('outbound_type','openvpn'),
                config_text=request.form.get('outbound_config',''),
                enabled=True,
                protocols=request.form.getlist('outbound_protocols') or [],
            )
            ok_test, test_out = test_outbound_config()
            if not ok_test:
                flash('کانفیگ Outbound وصل نشد و اعمال نشد: ' + test_out[-1200:])
                return redirect(url_for('web.outbound_manager'))
            ok, out = apply_outbound_runtime()
            log(current_user.username, 'outbound_apply', ','.join(request.form.getlist('outbound_protocols')), out[-500:])
            flash('Outbound فعال شد و مسیر ترافیک پروتکل‌های انتخابی اعمال شد' if ok else 'Outbound تست شد ولی اعمال runtime خطا داد: ' + out[-1200:])
            return redirect(url_for('web.outbound_manager'))
        # save only
        save_outbound_settings(
            outbound_type=request.form.get('outbound_type','openvpn'),
            config_text=request.form.get('outbound_config',''),
            enabled=request.form.get('outbound_enabled') == '1',
            protocols=request.form.getlist('outbound_protocols') or [],
        )
        flash('تنظیمات Outbound ذخیره شد. برای فعال‌سازی، اول تست و بعد Apply کن.')
        return redirect(url_for('web.outbound_manager'))
    return render_template('outbound.html', settings=outbound_settings(), status=outbound_runtime_status(), active=active_protocols())


# ---------------- IronPanel v16: Advanced Xray Core ----------------

def protocol_enabled_for_template(user, proto):
    proto = str(proto or '').strip()
    return proto in active_protocols() and proto in (user.allowed_protocol_list() or user.protocol_list() or active_protocols())

@web_bp.route('/xray', methods=['GET','POST'])
@login_required
def xray_core():
    # Xray is intentionally available for every license type; only main admin can change runtime core settings.
    if current_user.role != 'main_admin':
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        try:
            if action == 'generate_reality_keys':
                ensure_reality_keys(commit=True, force=True)
                flash('Reality keypair جدید ساخته شد و کلید عمومی/خصوصی به‌روزرسانی شد')
            elif action == 'save_builder':
                update_xray_builder(request.form)
                ok, out = write_xray_config([u for u in VpnUser.query.all() if user_access_status(u)[0] and protocol_enabled_for_template(u, 'xray')], restart=True)
                log(current_user.username, 'xray_builder_update', 'multi-inbound', out[-500:])
                flash('Xray Builder ذخیره و کانفیگ چند Inbound بازسازی شد' if ok else 'خطا در Xray Builder: ' + out[-800:])
            elif action == 'reset_builder':
                reset_xray_builder()
                flash('Presetهای Xray Builder به حالت پیش‌فرض برگشت')
            else:
                update_xray_settings(request.form)
                # Keep protocol list in sync with the dedicated Xray port fields.
                set_setting('port_xray_tcp', request.form.get('xray_port') or '443')
                set_setting('port_xray_api', request.form.get('xray_api_port') or '10085')
                db.session.commit()
                ok, out = write_xray_config([u for u in VpnUser.query.all() if user_access_status(u)[0] and protocol_enabled_for_template(u, 'xray')], restart=True)
                log(current_user.username, 'xray_update', 'core', out[-500:])
                flash('تنظیمات Xray ذخیره و کانفیگ بازسازی شد' if ok else 'خطا در ساخت کانفیگ Xray: ' + out[-800:])
        except Exception as exc:
            db.session.rollback()
            log(current_user.username, 'xray_apply_exception', action, str(exc)[-500:])
            flash('تنظیمات ذخیره نشد یا Apply هسته خطا داد: ' + str(exc)[:240])
        return redirect(url_for('web.xray_core'))
    valid_users = [u for u in VpnUser.query.all() if user_access_status(u)[0] and protocol_enabled_for_template(u, 'xray')]
    return render_template('xray.html', settings=xray_settings(), profile_types=XRAY_PROFILE_TYPES, runtime=xray_runtime_status(), users=valid_users, builder_inbounds=xray_builder_inbounds(), builder_enabled=xray_builder_enabled())


def _routing_protocol_rows(profiles, maps):
    by_protocol = {m.protocol: m for m in maps}
    by_id = {p.id: p for p in profiles}
    protocols = ['openvpn','wireguard','ocserv','l2tp','xray','pptp','hysteria2','telegram_proxy','ssh']
    rows=[]
    for protocol in protocols:
        m = by_protocol.get(protocol)
        p = by_id.get(m.outbound_profile_id) if m and m.outbound_profile_id else None
        rows.append({
            'protocol': protocol,
            'label': PROTOCOL_LABELS.get(protocol, protocol.upper()),
            'icon': PROTOCOL_ICONS.get(protocol, '◈'),
            'profile_id': p.id if p else None,
            'profile_name': p.name if p else '',
            'enabled': bool(m.enabled) if m else False,
            'failover': m.failover_profile_ids if m else '',
        })
    return rows

@web_bp.route('/routing-rules', methods=['GET','POST'])
@login_required
def routing_rules():
    if current_user.role != 'main_admin':
        flash('فقط ادمین اصلی به Routing Rules دسترسی دارد.')
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action','save_rules')
        if action == 'create_profile':
            name = (request.form.get('name') or '').strip()
            if not name:
                flash('نام پروفایل الزامی است.')
                return redirect(url_for('web.routing_rules'))
            p = OutboundProfile(
                name=name[:120],
                profile_type=(request.form.get('profile_type') or 'openvpn')[:30],
                config_body=request.form.get('config_body',''),
                enabled=True,
                priority=int(request.form.get('priority') or 100),
                kill_switch=request.form.get('kill_switch') == '1',
                route_mode=(request.form.get('route_mode') or 'full')[:30],
                route_targets=request.form.get('route_targets',''),
            )
            db.session.add(p); db.session.commit()
            log(current_user.username, 'routing_profile_create', p.name)
            flash('Outbound Profile ساخته شد.')
        elif action == 'delete_profile':
            p = OutboundProfile.query.get_or_404(int(request.form.get('profile_id') or 0))
            ProtocolOutboundMap.query.filter_by(outbound_profile_id=p.id).delete()
            name = p.name
            db.session.delete(p); db.session.commit()
            log(current_user.username, 'routing_profile_delete', name)
            flash('پروفایل و ruleهای وابسته حذف شدند.')
        elif action == 'test_profile':
            from ..services.v17 import test_outbound_profile
            p = OutboundProfile.query.get_or_404(int(request.form.get('profile_id') or 0))
            ok, detail = test_outbound_profile(p)
            flash(('تست موفق: ' if ok else 'تست ناموفق: ') + detail[:300])
        elif action == 'save_rules':
            protocols = ['openvpn','wireguard','ocserv','l2tp','xray','pptp','hysteria2','telegram_proxy','ssh']
            for protocol in protocols:
                profile_id = int(request.form.get(f'profile_{protocol}') or 0)
                enabled = request.form.get(f'enabled_{protocol}') == '1' and profile_id > 0
                failover = (request.form.get(f'failover_{protocol}') or '').strip()[:255]
                m = ProtocolOutboundMap.query.filter_by(protocol=protocol, node_id=None).first()
                if not enabled:
                    if m:
                        db.session.delete(m)
                    continue
                if not m:
                    m = ProtocolOutboundMap(protocol=protocol, node_id=None)
                    db.session.add(m)
                m.outbound_profile_id = profile_id
                m.enabled = True
                m.failover_profile_ids = failover
            db.session.commit()
            log(current_user.username, 'routing_rules_save', 'protocol-matrix')
            flash('Routing Rules ذخیره شد. برای اعمال policy routing، در صورت نیاز Outbound Runtime را Apply کن.')
        return redirect(url_for('web.routing_rules'))
    from ..services.v17 import outbound_matrix
    profiles, maps = outbound_matrix()
    return render_template('routing_rules.html', profiles=profiles, maps=maps, nodes=Node.query.all(), protocol_rows=_routing_protocol_rows(profiles, maps))

@web_bp.route('/outbound/v2', methods=['GET','POST'])
@login_required
def outbound_v2():
    if request.method == 'POST':
        action=request.form.get('action')
        if action == 'create_profile':
            p=OutboundProfile(name=request.form.get('name','Outbound'), profile_type=request.form.get('profile_type','openvpn'), config_body=request.form.get('config_body',''), priority=int(request.form.get('priority') or 100), kill_switch=bool(request.form.get('kill_switch')), route_mode=request.form.get('route_mode','full'), route_targets=request.form.get('route_targets',''))
            db.session.add(p); db.session.commit(); flash('پروفایل اوتباند ساخته شد')
        elif action == 'test_profile':
            from ..services.v17 import test_outbound_profile
            p=OutboundProfile.query.get_or_404(int(request.form.get('profile_id'))); ok,detail=test_outbound_profile(p); flash(('تست موفق: ' if ok else 'تست ناموفق: ')+detail)
        elif action == 'map_protocol':
            m=ProtocolOutboundMap(protocol=request.form.get('protocol'), outbound_profile_id=int(request.form.get('profile_id') or 0) or None, node_id=int(request.form.get('node_id') or 0) or None, enabled=True, failover_profile_ids=request.form.get('failover_profile_ids',''))
            db.session.add(m); db.session.commit(); flash('Route map ذخیره شد')
        return redirect(url_for('web.outbound_v2'))
    from ..services.v17 import outbound_matrix
    profiles,maps=outbound_matrix()
    return render_template('outbound_v2.html', profiles=profiles, maps=maps, nodes=Node.query.all())

@web_bp.route('/speed-limits', methods=['GET','POST'])
@login_required
def speed_limits():
    if current_user.role != 'main_admin':
        flash('فقط ادمین اصلی می‌تواند محدودیت سرعت را تغییر دهد.')
        return redirect(url_for('web.dashboard'))
    if request.method == 'POST':
        action = request.form.get('action','save_apply')
        if action in ('save','save_apply'):
            changed = save_speed_limits(request.form)
            changed_users = save_user_speed_limits(request.form)
            log(current_user.username, 'speed_limits_save', ','.join(changed) or 'no-change')
            if action == 'save_apply':
                ok, out = apply_speed_limits_runtime()
                log(current_user.username, 'speed_limits_apply', str(ok), out[-500:])
                flash(('محدودیت سرعت هر کاربر/پروتکل ذخیره و روی سرور اعمال شد. کاربران تغییر یافته: %s' % changed_users) if ok else 'ذخیره شد ولی اعمال runtime خطا داشت: ' + out[-180:])
            else:
                flash('محدودیت سرعت ذخیره شد.')
        elif action == 'apply':
            ok, out = apply_speed_limits_runtime()
            log(current_user.username, 'speed_limits_apply', str(ok), out[-500:])
            flash('محدودیت‌ها دوباره روی سرور اعمال شدند.' if ok else 'اعمال محدودیت با خطا مواجه شد: ' + out[-180:])
        return redirect(url_for('web.speed_limits'))
    return render_template('speed_limits.html', rows=speed_limit_rows(), user_matrix=speed_limit_user_matrix(), status=speed_limit_status())
