import click, secrets
from .core.extensions import db
from .core.models import Admin, Port, Node, AppSetting, DnsProfile

DEFAULT_SETTINGS = {
    'public_host': None,
    'tunnel_host': '',
    'active_protocols': 'openvpn,ocserv,l2tp,wireguard,xray',
    'port_panel': '8080',
    'port_openvpn_udp': '1194',
    'port_openvpn_tcp': '1195',
    'port_ocserv_tcp': '8443',
    'port_ocserv_udp': '8443',
    'port_l2tp_udp': '1701',
    'port_ipsec_ike': '500',
    'port_ipsec_nat': '4500',
    'port_wireguard_udp': '51820',
    'port_xray_tcp': '443',
    'port_xray_api': '10085',
    'license_server_url': 'http://license.skyshield.space:8002',
    'license_key': '',
    'license_status': 'not_configured',
    'license_message': '',
    'license_type': 'admin',
    'license_features': '',
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
    'language': 'fa',
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
                'protocols': "ALTER TABLE vpn_user ADD COLUMN protocols VARCHAR(120) DEFAULT 'openvpn,ocserv,l2tp,wireguard,xray'",
                'data_limit_mb': "ALTER TABLE vpn_user ADD COLUMN data_limit_mb INTEGER DEFAULT 0",
                'used_upload_mb': "ALTER TABLE vpn_user ADD COLUMN used_upload_mb INTEGER DEFAULT 0",
                'used_download_mb': "ALTER TABLE vpn_user ADD COLUMN used_download_mb INTEGER DEFAULT 0",
                'used_upload_bytes': "ALTER TABLE vpn_user ADD COLUMN used_upload_bytes BIGINT DEFAULT 0",
                'used_download_bytes': "ALTER TABLE vpn_user ADD COLUMN used_download_bytes BIGINT DEFAULT 0",
                'connection_limit': "ALTER TABLE vpn_user ADD COLUMN connection_limit INTEGER DEFAULT 1",
                'allowed_devices': "ALTER TABLE vpn_user ADD COLUMN allowed_devices INTEGER DEFAULT 0",
                'protocol_permissions': "ALTER TABLE vpn_user ADD COLUMN protocol_permissions VARCHAR(120) DEFAULT 'openvpn,ocserv,l2tp,wireguard,xray'",
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
            conn.exec_driver_sql("UPDATE vpn_user SET protocols='openvpn,ocserv,l2tp,wireguard,xray' WHERE protocols IS NULL OR protocols=''")
            conn.exec_driver_sql("UPDATE vpn_user SET protocol_permissions='openvpn,ocserv,l2tp,wireguard,xray' WHERE protocol_permissions IS NULL OR protocol_permissions=''")
            conn.exec_driver_sql("UPDATE vpn_user SET data_limit_mb=0 WHERE data_limit_mb IS NULL")
            conn.exec_driver_sql("UPDATE vpn_user SET used_upload_mb=0 WHERE used_upload_mb IS NULL")
            conn.exec_driver_sql("UPDATE vpn_user SET used_download_mb=0 WHERE used_download_mb IS NULL")
            conn.exec_driver_sql("UPDATE vpn_user SET used_upload_bytes=COALESCE(used_upload_bytes, used_upload_mb * 1048576, 0) WHERE used_upload_bytes IS NULL OR used_upload_bytes=0")
            conn.exec_driver_sql("UPDATE vpn_user SET used_download_bytes=COALESCE(used_download_bytes, used_download_mb * 1048576, 0) WHERE used_download_bytes IS NULL OR used_download_bytes=0")
            conn.exec_driver_sql("UPDATE vpn_user SET connection_limit=1 WHERE connection_limit IS NULL")
            conn.exec_driver_sql("UPDATE vpn_user SET allowed_devices=0 WHERE allowed_devices IS NULL")

            # v16: make Xray available on upgraded installs without disabling existing protocols.
            try:
                conn.exec_driver_sql("UPDATE vpn_user SET protocols = protocols || ',xray' WHERE protocols IS NOT NULL AND protocols!='' AND instr(',' || protocols || ',', ',xray,')=0")
                conn.exec_driver_sql("UPDATE vpn_user SET protocol_permissions = protocol_permissions || ',xray' WHERE protocol_permissions IS NOT NULL AND protocol_permissions!='' AND instr(',' || protocol_permissions || ',', ',xray,')=0")
            except Exception:
                pass
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
            if 'created_at' not in cols:
                conn.exec_driver_sql("ALTER TABLE admin ADD COLUMN created_at DATETIME")

def register_commands(app):
    @app.cli.command('init-db')
    @click.option('--admin-user', default='admin')
    @click.option('--admin-pass', default='admin')
    def init_db(admin_user, admin_pass):
        db.create_all()
        if not Admin.query.filter_by(username=admin_user).first():
            a = Admin(username=admin_user, role='main_admin', api_key=secrets.token_urlsafe(48))
            a.set_password(admin_pass); db.session.add(a)
        if not Node.query.first():
            db.session.add(Node(name='local', host=app.config['PUBLIC_HOST'], health='local'))
        defaults=[('openvpn',1194,'udp'),('ocserv',8443,'tcp'),('ocserv',8443,'udp'),('l2tp',1701,'udp'),('ipsec',500,'udp'),('ipsec',4500,'udp'),('wireguard',51820,'udp'),('xray',443,'tcp'),('xray-api',10085,'tcp')]
        for proto,port,trans in defaults:
            if not Port.query.filter_by(protocol=proto, port=port, transport=trans).first():
                db.session.add(Port(protocol=proto, port=port, transport=trans))
        if not DnsProfile.query.first():
            db.session.add(DnsProfile(name='Cloudflare', primary_dns='1.1.1.1', secondary_dns='1.0.0.1', is_default=True))
        for k,v in DEFAULT_SETTINGS.items():
            upsert_setting(k, app.config['PUBLIC_HOST'] if k == 'public_host' else v)
        db.session.commit()
        click.echo('Ironpanel database initialized/upgraded')

    @app.cli.command('upgrade-db')
    def upgrade_db():
        db.create_all()
        _sqlite_light_migration(db)
        if not DnsProfile.query.first():
            db.session.add(DnsProfile(name='Cloudflare', primary_dns='1.1.1.1', secondary_dns='1.0.0.1', is_default=True))
        for k,v in DEFAULT_SETTINGS.items():
            upsert_setting(k, app.config['PUBLIC_HOST'] if k == 'public_host' else v)
        # v16: append xray to active_protocols on existing installs.
        ap = AppSetting.query.filter_by(key='active_protocols').first()
        if ap and 'xray' not in (ap.value or '').split(','):
            ap.value = ((ap.value or 'openvpn,ocserv,l2tp,wireguard').rstrip(',') + ',xray')
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

    @app.cli.command('enforce-limits')
    def enforce_limits():
        from .services.provisioning import collect_usage_from_runtime, enforce_usage_limits
        count = collect_usage_from_runtime()
        stopped = enforce_usage_limits()
        click.echo(f'Ironpanel limit enforcement completed. Usage updates: {count}. Stopped users: {stopped}')

