import click, secrets, json, re
from .core.extensions import db
from .core.models import Admin, Port, Node, AppSetting, DnsProfile

DEFAULT_SETTINGS = {
    'public_host': None,
    'tunnel_host': '',
    'active_protocols': 'openvpn,ocserv,l2tp,wireguard,xray,pptp,hysteria2,telegram_proxy,ssh',
    'port_panel': '8080',
    'port_openvpn_udp': '1194',
    'port_openvpn_tcp': '1195',
    'port_ocserv_tcp': '8445',
    'port_ocserv_udp': '8445',
    'port_l2tp_udp': '1701',
    'port_ipsec_ike': '500',
    'port_ipsec_nat': '4500',
    'port_wireguard_udp': '51820',
    'port_xray_tcp': '443',
    'port_xray_api': '10085',
    'port_pptp_tcp': '1723',
    'port_hysteria2_udp': '4433',
    'port_telegram_proxy_base': '6969',
    'port_ssh_tcp': '422',
    'telegram_proxy_enabled': '1',
    'telegram_proxy_secret_salt': '',
    'telegram_proxy_repo': 'https://github.com/Unknown-sir/JSMTProxy.git',
    'license_server_url': 'http://license.skyshield.space:8002',
    'license_key': '',
    'license_status': 'free',
    'license_message': 'نسخه رایگان Beginner فعال است.',
    'license_type': 'beginer',
    'license_paid_active': '0',
    'license_features': '{"nodes": false, "sales_bot": false, "billing": false, "network": false, "updates": true, "xray": true, "outbound": true, "backup": true, "monitoring": true, "api": true, "subscription": true, "node_agent": false, "outbound_failover": true, "ssl": true}',
    'ocserv_transport': 'tcp_udp',
    'wireguard_transport': 'udp',
    'l2tp_transport': 'udp',
    'telegram_bot_token': '',
    'telegram_chat_id': '',
    'notify_login': '1',
    'notify_expiry': '1',
    'grace_days': '0',
    'ha_enabled': '0',
    'load_balancer_enabled': '0',
    'auto_failover_enabled': '1',
    'auto_backup_enabled': '1',
    'auto_backup_time': '03:00',
    'backup_remote_type': 'local',
    'backup_remote_path': '',
    'theme_mode': 'dark',
    'language': 'en',
    'wireguard_mtu': '1280',
    'wireguard_persistent_keepalive': '25',
    'wireguard_dns': '1.1.1.1',
    'subscription_domain': '',
    'job_worker_enabled': '1',
    'security_2fa_enabled': '0',
    'security_ip_whitelist': '',
    'security_captcha_enabled': '0',
    'fail2ban_enabled': '0',
    'release_channel': 'stable',
    'payment_currency': 'USD',
    'payment_manual_enabled': '1',
    'telegram_bot_enabled': '0',
    'remote_update_enabled': '1',
    'github_version_url': 'https://raw.githubusercontent.com/Unknown-sir/ironpanel/main/VERSION',
    'github_repo_url': 'https://github.com/Unknown-sir/ironpanel.git',
    'github_branch': 'main',
    'github_update_check_interval_minutes': '60',
    'github_update_cache': '',
    'license_hardware_binding': '1',
    # v14: sales bot settings for selling VPN accounts from inside IronPanel
    'sales_bot_enabled': '0',
    'sales_bot_token': '',
    'sales_bot_admin_ids': '',
    'sales_bot_support_url': 'https://t.me/unknown_eng',
    'sales_bot_payment_text': 'لطفاً مبلغ پلن را به کارت/حساب اعلام‌شده واریز کنید و تصویر رسید را همین‌جا ارسال کنید.',
    'sales_bot_trial_enabled': '1',
    'sales_bot_trial_days': '1',
    'sales_bot_trial_traffic_gb': '1',
    'sales_bot_currency': 'IRT',
    # v16: full Xray Core integration. Xray is available for every license type.
    'xray_enabled': '1',
    'xray_profile_type': 'vless-reality',
    'xray_domain': '',
    'xray_port': '443',
    'xray_api_port': '10085',
    'xray_uuid_namespace': '',
    'xray_reality_dest': 'www.cloudflare.com:443',
    'xray_reality_sni': 'www.cloudflare.com',
    'xray_reality_server_names': 'www.cloudflare.com,cloudflare.com',
    'xray_reality_private_key': '',
    'xray_reality_public_key': '',
    'xray_reality_short_ids': '',
    'xray_reality_fingerprint': 'chrome',
    'xray_reality_spiderx': '/',
    'xray_flow': 'xtls-rprx-vision',
    'xray_tls_cert_file': '/etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem',
    'xray_tls_key_file': '/etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem',
    'xray_alpn': 'h2,http/1.1',
    'xray_ws_path': '/ironpanel-ws',
    'xray_ws_host': '',
    'xray_grpc_service_name': 'ironpanel-grpc',
    'xray_mux_enabled': '0',
    'xray_sniffing_enabled': '1',
    'xray_dns_servers': '1.1.1.1,8.8.8.8',
    'xray_routing_mode': 'direct',
    'xray_block_private': '0',
    'xray_loglevel': 'warning',
    'xray_ss_method': 'chacha20-ietf-poly1305',
    # v16.7: Outbound routing manager (available for every license type)
    'outbound_enabled': '0',
    'outbound_type': 'openvpn',
    'outbound_config': '',
    'outbound_protocols': '',
    'outbound_status': 'not_configured',
    'outbound_last_test': '',
    'outbound_last_error': '',
    'outbound_openvpn_interface': 'ironout',
    'outbound_policy_table': '166',
    'outbound_policy_mark': '0x66',
    'outbound_tproxy_port': '12345',
    # v17: enterprise node/subscription/outbound/backup options
    'v17_node_agent_enabled': '1',
    'v17_node_install_repo': 'https://github.com/Unknown-sir/ironpanel.git',
    'subscription_formats_enabled': 'raw,clash,singbox,hiddify,qr',
    'subscription_hide_raw_from_users': '0',
    'backup_v17_enabled': '1',
    'backup_v17_keep_last': '7',
    'backup_v17_telegram_delivery': '0',
    'outbound_v2_failover_enabled': '1',
    'outbound_v2_dns_leak_test': '1',
    'xray_v17_validate_before_delivery': '1',
    'pptp_enabled': '1',
    'hysteria2_enabled': '1',
    'hysteria2_port': '4433',
    'hysteria2_obfs_password': '',
    'hysteria2_tls_cert_file': '/etc/hysteria/server.crt',
    'hysteria2_tls_key_file': '/etc/hysteria/server.key',
    'hysteria2_up_mbps': '100 mbps',
    'hysteria2_down_mbps': '300 mbps',
    'ssl_enabled': '0',
    'ssl_panel_enabled': '0',
    'ssl_domain': '',
    'ssl_cert_file': '',
    'ssl_key_file': '',
    'ssl_storage_root': '/etc/ironpanel/ssl',
    'traffic_multiplier_enabled': '0',
    'traffic_multiplier_value': '1',
    # v19.1: per-protocol speed limits in Mbps; 0 means unlimited.
    'speed_limit_openvpn_mbps': '0',
    'speed_limit_wireguard_mbps': '0',
    'speed_limit_ocserv_mbps': '0',
    'speed_limit_l2tp_mbps': '0',
    'speed_limit_xray_mbps': '0',
    'speed_limit_pptp_mbps': '0',
    'speed_limit_hysteria2_mbps': '0',
    'speed_limit_telegram_proxy_mbps': '0',
    'speed_limit_ssh_mbps': '0',
    'ui_style': 'vpn-ui-teal',
}





def upsert_setting(key, value):
    row = AppSetting.query.filter_by(key=key).first()
    if not row:
        db.session.add(AppSetting(key=key, value=str(value or '')))
    elif value not in (None, '') and not row.value:
        row.value = str(value)

def _sqlite_light_migration(db):
    # Safe SQLite migration for existing Ironpanel installs.
    # SQLite create_all() does not add new columns to existing tables, so every
    # release must explicitly add missing columns before the web process starts.
    engine = db.engine
    if not engine.url.get_backend_name().startswith('sqlite'):
        return
    with engine.begin() as conn:
        tables = {r[0] for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if 'vpn_user' in tables:
            cols = {r[1] for r in conn.exec_driver_sql('PRAGMA table_info(vpn_user)').fetchall()}
            additions = {
                'l2tp_password': "ALTER TABLE vpn_user ADD COLUMN l2tp_password VARCHAR(128)",
                'cisco_password': "ALTER TABLE vpn_user ADD COLUMN cisco_password VARCHAR(128)",
                'enabled': "ALTER TABLE vpn_user ADD COLUMN enabled BOOLEAN DEFAULT 1",
                'protocols': "ALTER TABLE vpn_user ADD COLUMN protocols VARCHAR(120) DEFAULT 'openvpn,ocserv,l2tp,wireguard,xray,pptp,hysteria2,telegram_proxy,ssh'",
                'data_limit_mb': "ALTER TABLE vpn_user ADD COLUMN data_limit_mb INTEGER DEFAULT 0",
                'used_upload_mb': "ALTER TABLE vpn_user ADD COLUMN used_upload_mb INTEGER DEFAULT 0",
                'used_download_mb': "ALTER TABLE vpn_user ADD COLUMN used_download_mb INTEGER DEFAULT 0",
                'used_upload_bytes': "ALTER TABLE vpn_user ADD COLUMN used_upload_bytes BIGINT DEFAULT 0",
                'used_download_bytes': "ALTER TABLE vpn_user ADD COLUMN used_download_bytes BIGINT DEFAULT 0",
                'connection_limit': "ALTER TABLE vpn_user ADD COLUMN connection_limit INTEGER DEFAULT 1",
                'allowed_devices': "ALTER TABLE vpn_user ADD COLUMN allowed_devices INTEGER DEFAULT 0",
                'protocol_permissions': "ALTER TABLE vpn_user ADD COLUMN protocol_permissions VARCHAR(120) DEFAULT 'openvpn,ocserv,l2tp,wireguard,xray,pptp,hysteria2,telegram_proxy,ssh'",
                'expires_at': "ALTER TABLE vpn_user ADD COLUMN expires_at DATETIME",
                'subscription_token': "ALTER TABLE vpn_user ADD COLUMN subscription_token VARCHAR(96)",
                'wg_private_key': "ALTER TABLE vpn_user ADD COLUMN wg_private_key TEXT",
                'wg_public_key': "ALTER TABLE vpn_user ADD COLUMN wg_public_key TEXT",
                'wg_ip': "ALTER TABLE vpn_user ADD COLUMN wg_ip VARCHAR(64)",
                'owner_id': "ALTER TABLE vpn_user ADD COLUMN owner_id INTEGER",
                'created_at': "ALTER TABLE vpn_user ADD COLUMN created_at DATETIME",
            }
            for col, sql in additions.items():
                if col not in cols:
                    conn.exec_driver_sql(sql)
            conn.exec_driver_sql("UPDATE vpn_user SET enabled=1 WHERE enabled IS NULL")
            conn.exec_driver_sql("UPDATE vpn_user SET protocols='openvpn,ocserv,l2tp,wireguard,xray,pptp,hysteria2,telegram_proxy,ssh' WHERE protocols IS NULL OR protocols=''")
            conn.exec_driver_sql("UPDATE vpn_user SET protocol_permissions='openvpn,ocserv,l2tp,wireguard,xray,pptp,hysteria2,telegram_proxy,ssh' WHERE protocol_permissions IS NULL OR protocol_permissions=''")
            conn.exec_driver_sql("UPDATE vpn_user SET data_limit_mb=0 WHERE data_limit_mb IS NULL")
            conn.exec_driver_sql("UPDATE vpn_user SET used_upload_mb=0 WHERE used_upload_mb IS NULL")
            conn.exec_driver_sql("UPDATE vpn_user SET used_download_mb=0 WHERE used_download_mb IS NULL")
            conn.exec_driver_sql("UPDATE vpn_user SET used_upload_bytes=COALESCE(used_upload_bytes, used_upload_mb * 1048576, 0) WHERE used_upload_bytes IS NULL OR used_upload_bytes=0")
            conn.exec_driver_sql("UPDATE vpn_user SET used_download_bytes=COALESCE(used_download_bytes, used_download_mb * 1048576, 0) WHERE used_download_bytes IS NULL OR used_download_bytes=0")
            conn.exec_driver_sql("UPDATE vpn_user SET connection_limit=1 WHERE connection_limit IS NULL")
            conn.exec_driver_sql("UPDATE vpn_user SET allowed_devices=0 WHERE allowed_devices IS NULL")

            # v18: make Xray, PPTP and Hysteria2 available on upgraded installs without disabling existing protocols.
            try:
                for extra in ['xray','pptp','hysteria2','telegram_proxy','ssh']:
                    conn.exec_driver_sql(f"UPDATE vpn_user SET protocols = protocols || ',{extra}' WHERE protocols IS NOT NULL AND protocols!='' AND instr(',' || protocols || ',', ',{extra},')=0")
                    conn.exec_driver_sql(f"UPDATE vpn_user SET protocol_permissions = protocol_permissions || ',{extra}' WHERE protocol_permissions IS NOT NULL AND protocol_permissions!='' AND instr(',' || protocol_permissions || ',', ',{extra},')=0")
            except Exception:
                pass

        if 'node' in tables:
            cols = {r[1] for r in conn.exec_driver_sql('PRAGMA table_info(node)').fetchall()}
            for col, sql in {
                'location': "ALTER TABLE node ADD COLUMN location VARCHAR(120) DEFAULT ''",
                'version': "ALTER TABLE node ADD COLUMN version VARCHAR(40) DEFAULT ''",
                'agent_version': "ALTER TABLE node ADD COLUMN agent_version VARCHAR(40) DEFAULT ''",
                'public_ip': "ALTER TABLE node ADD COLUMN public_ip VARCHAR(80) DEFAULT ''",
                'cpu_percent': "ALTER TABLE node ADD COLUMN cpu_percent FLOAT DEFAULT 0",
                'ram_percent': "ALTER TABLE node ADD COLUMN ram_percent FLOAT DEFAULT 0",
                'disk_percent': "ALTER TABLE node ADD COLUMN disk_percent FLOAT DEFAULT 0",
                'traffic_rx_bytes': "ALTER TABLE node ADD COLUMN traffic_rx_bytes BIGINT DEFAULT 0",
                'traffic_tx_bytes': "ALTER TABLE node ADD COLUMN traffic_tx_bytes BIGINT DEFAULT 0",
                'last_seen': "ALTER TABLE node ADD COLUMN last_seen DATETIME",
                'last_error': "ALTER TABLE node ADD COLUMN last_error TEXT DEFAULT ''",
            }.items():
                if col not in cols:
                    conn.exec_driver_sql(sql)
        if 'admin' in tables:
            cols = {r[1] for r in conn.exec_driver_sql('PRAGMA table_info(admin)').fetchall()}
            if 'role' not in cols:
                conn.exec_driver_sql("ALTER TABLE admin ADD COLUMN role VARCHAR(20) DEFAULT 'main_admin'")
            if 'api_key' not in cols:
                conn.exec_driver_sql("ALTER TABLE admin ADD COLUMN api_key VARCHAR(96)")
            if 'user_limit' not in cols:
                conn.exec_driver_sql("ALTER TABLE admin ADD COLUMN user_limit INTEGER DEFAULT 0")
            if 'traffic_quota_gb' not in cols:
                conn.exec_driver_sql("ALTER TABLE admin ADD COLUMN traffic_quota_gb INTEGER DEFAULT 0")
            if 'panel_path' not in cols:
                conn.exec_driver_sql("ALTER TABLE admin ADD COLUMN panel_path VARCHAR(120)")
            if 'enabled' not in cols:
                conn.exec_driver_sql("ALTER TABLE admin ADD COLUMN enabled BOOLEAN DEFAULT 1")
            conn.exec_driver_sql("UPDATE admin SET enabled=1 WHERE enabled IS NULL")
            if 'created_at' not in cols:
                conn.exec_driver_sql("ALTER TABLE admin ADD COLUMN created_at DATETIME")

FAMOUS_DNS_PROFILES = [
    ('Cloudflare', '1.1.1.1', '1.0.0.1', True),
    ('Google', '8.8.8.8', '8.8.4.4', False),
    ('Quad9', '9.9.9.9', '149.112.112.112', False),
    ('OpenDNS', '208.67.222.222', '208.67.220.220', False),
    ('AdGuard DNS', '94.140.14.14', '94.140.15.15', False),
    ('DNS.SB', '185.222.222.222', '45.11.45.11', False),
    ('Shecan', '178.22.122.100', '185.51.200.2', False),
    ('Electro', '78.157.42.100', '78.157.42.101', False),
    ('Begzar', '185.55.226.26', '185.55.225.25', False),
]


def _ensure_famous_dns_profiles():
    """Seed well-known DNS profiles without removing admin custom profiles."""
    changed = False
    has_default = bool(DnsProfile.query.filter_by(is_default=True).first())
    for name, primary, secondary, preferred_default in FAMOUS_DNS_PROFILES:
        profile = DnsProfile.query.filter_by(name=name).first()
        should_default = bool(preferred_default and not has_default)
        if not profile:
            db.session.add(DnsProfile(name=name, primary_dns=primary, secondary_dns=secondary, is_default=should_default))
            changed = True
            if should_default:
                has_default = True
        else:
            # Keep custom profiles intact, but keep built-in well-known profile addresses fresh.
            if profile.primary_dns != primary or profile.secondary_dns != secondary:
                profile.primary_dns = primary
                profile.secondary_dns = secondary
                changed = True
            if preferred_default and not has_default:
                profile.is_default = True
                has_default = True
                changed = True
    return changed


def _safe_reseller_slug(raw, fallback):
    base = (raw or fallback or '').strip().strip('/')
    base = re.sub(r'[^a-zA-Z0-9_-]+', '-', base).strip('-_').lower()
    if not base:
        base = f"reseller-{secrets.token_hex(3)}"
    reserved = {'dashboard','users','user','static','login','logout','api','api-v2','subscription','sub','settings','resellers','reseller','r','admin-bot','sales-bot','upgrade','updates','health','monitoring','sessions'}
    if base in reserved:
        base = f"r-{base}"
    candidate = base
    idx = 2
    while Admin.query.filter(Admin.role == 'sub_admin', Admin.panel_path == candidate).first():
        candidate = f"{base}-{idx}"
        idx += 1
    return candidate

def _ensure_reseller_portals():
    changed = False
    for reseller in Admin.query.filter_by(role='sub_admin').all():
        if not getattr(reseller, 'panel_path', None):
            reseller.panel_path = _safe_reseller_slug('', reseller.username or f'reseller-{reseller.id}')
            changed = True
        if getattr(reseller, 'enabled', None) is None:
            reseller.enabled = True
            changed = True
        if getattr(reseller, 'user_limit', None) is None:
            reseller.user_limit = 0
            changed = True
        if getattr(reseller, 'traffic_quota_gb', None) is None:
            reseller.traffic_quota_gb = 0
            changed = True
    return changed

def register_commands(app):
    @app.cli.command('init-db')
    @click.option('--admin-user', default='admin')
    @click.option('--admin-pass', default='admin')
    def init_db(admin_user, admin_pass):
        db.create_all()
        # v18.5.8: create_all() does not add new columns to existing SQLite
        # databases. Run the lightweight migration before any ORM query so
        # upgraded installs do not fail on columns added in newer releases
        # (for example admin.enabled / reseller portal fields).
        _sqlite_light_migration(db)
        if not Admin.query.filter_by(username=admin_user).first():
            a = Admin(username=admin_user, role='main_admin', api_key=secrets.token_urlsafe(48))
            a.set_password(admin_pass); db.session.add(a)
        if not Node.query.first():
            db.session.add(Node(name='local', host=app.config['PUBLIC_HOST'], health='local'))
        defaults=[('openvpn',1194,'udp'),('ocserv',8445,'tcp'),('ocserv',8445,'udp'),('l2tp',1701,'udp'),('ipsec',500,'udp'),('ipsec',4500,'udp'),('wireguard',51820,'udp'),('xray',443,'tcp'),('xray-api',10085,'tcp'),('pptp',1723,'tcp'),('hysteria2',4433,'udp'),('telegram-proxy',6969,'tcp'),('ssh',422,'tcp')]
        for proto,port,trans in defaults:
            if not Port.query.filter_by(protocol=proto, port=port, transport=trans).first():
                db.session.add(Port(protocol=proto, port=port, transport=trans))
        _ensure_famous_dns_profiles()
        for k,v in DEFAULT_SETTINGS.items():
            upsert_setting(k, app.config['PUBLIC_HOST'] if k == 'public_host' else v)
        _ensure_reseller_portals()
        db.session.commit()
        click.echo('Ironpanel database initialized/upgraded')

    @app.cli.command('upgrade-db')
    def upgrade_db():
        db.create_all()
        _sqlite_light_migration(db)
        _ensure_famous_dns_profiles()
        for k,v in DEFAULT_SETTINGS.items():
            upsert_setting(k, app.config['PUBLIC_HOST'] if k == 'public_host' else v)
        # v18: append new protocols to active_protocols on existing installs.
        ap = AppSetting.query.filter_by(key='active_protocols').first()
        if ap:
            protos=[x.strip() for x in (ap.value or 'openvpn,ocserv,l2tp,wireguard,xray').split(',') if x.strip()]
            for extra in ['xray','pptp','hysteria2','telegram_proxy','ssh']:
                if extra not in protos: protos.append(extra)
            ap.value=','.join(protos)
        # v18.4: installs without a key automatically run the free Beginner edition.
        key_row = AppSetting.query.filter_by(key='license_key').first()
        if not key_row or not (key_row.value or '').strip():
            free_features = {
                'nodes': False, 'sales_bot': False, 'billing': False, 'network': False,
                'updates': True, 'xray': True, 'outbound': True, 'backup': True,
                'monitoring': True, 'api': True, 'subscription': True,
                'node_agent': False, 'outbound_failover': True, 'ssl': True, 'traffic_multiplier': True,
            }
            for key, value in {
                'license_status': 'free',
                'license_message': 'نسخه رایگان Beginner فعال است.',
                'license_type': 'beginer',
                'license_paid_active': '0',
                'license_features': json.dumps(free_features, ensure_ascii=False),
            }.items():
                row = AppSetting.query.filter_by(key=key).first()
                if not row:
                    db.session.add(AppSetting(key=key, value=str(value)))
                else:
                    row.value = str(value)
        _ensure_reseller_portals()
        db.session.commit()
        click.echo('Ironpanel database upgraded')
    @app.cli.command('sync-usage')
    def sync_usage():
        from .services.provisioning import collect_usage_from_runtime, enforce_usage_limits
        count = collect_usage_from_runtime()
        stopped = enforce_usage_limits()
        online = 0
        try:
            from .services.v10 import refresh_online_sessions
            online = len(refresh_online_sessions())
        except Exception:
            online = 0
        click.echo(f'Ironpanel usage sync completed. Updated users: {count}. Stopped users: {stopped}. Online sessions: {online}')


    @app.cli.command('process-jobs')
    def process_jobs_cmd():
        from .services.v13 import process_local_jobs
        jobs = process_local_jobs()
        click.echo(f'IronPanel processed {len(jobs)} queued job(s)')

    @app.cli.command('enforce-limits')
    def enforce_limits():
        from .services.provisioning import collect_usage_from_runtime, enforce_usage_limits
        count = collect_usage_from_runtime()
        stopped = enforce_usage_limits()
        click.echo(f'Ironpanel limit enforcement completed. Usage updates: {count}. Stopped users: {stopped}')


# v17 command registration extension
# These commands are added after the main register_commands function is loaded by Flask.
def _register_v17_commands(app):
    @app.cli.command('backup-v17')
    def backup_v17_cmd():
        from .services.v17 import run_full_backup_v17
        p=run_full_backup_v17(); print(str(p))
    @app.cli.command('health-v17')
    def health_v17_cmd():
        from .services.v17 import v17_health_checks
        import json
        print(json.dumps(v17_health_checks(), ensure_ascii=False, default=str, indent=2))

_original_register_commands = register_commands

def register_commands(app):
    _original_register_commands(app)
    _register_v17_commands(app)
