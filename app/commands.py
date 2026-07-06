import click, secrets
from .core.extensions import db
from .core.models import Admin, Port, Node, AppSetting

DEFAULT_SETTINGS = {
    'public_host': None,
    'tunnel_host': '',
    'active_protocols': 'openvpn,ocserv,l2tp,wireguard',
    'port_panel': '8080',
    'port_openvpn_udp': '1194',
    'port_openvpn_tcp': '1195',
    'port_ocserv_tcp': '8443',
    'port_ocserv_udp': '8443',
    'port_l2tp_udp': '1701',
    'port_ipsec_ike': '500',
    'port_ipsec_nat': '4500',
    'port_wireguard_udp': '51820',
    'license_server_url': 'http://license.skyshield.space:8002',
    'license_key': '',
    'license_status': 'not_configured',
    'license_message': '',
    'ocserv_transport': 'tcp_udp',
    'wireguard_transport': 'udp',
    'l2tp_transport': 'udp',
}


def upsert_setting(key, value):
    row = AppSetting.query.filter_by(key=key).first()
    if not row:
        db.session.add(AppSetting(key=key, value=str(value or '')))
    elif value not in (None, '') and not row.value:
        row.value = str(value)

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
        defaults=[('openvpn',1194,'udp'),('ocserv',8443,'tcp'),('ocserv',8443,'udp'),('l2tp',1701,'udp'),('ipsec',500,'udp'),('ipsec',4500,'udp'),('wireguard',51820,'udp')]
        for proto,port,trans in defaults:
            if not Port.query.filter_by(protocol=proto, port=port, transport=trans).first():
                db.session.add(Port(protocol=proto, port=port, transport=trans))
        for k,v in DEFAULT_SETTINGS.items():
            upsert_setting(k, app.config['PUBLIC_HOST'] if k == 'public_host' else v)
        db.session.commit()
        click.echo('Ironpanel database initialized/upgraded')

    @app.cli.command('upgrade-db')
    def upgrade_db():
        db.create_all()
        for k,v in DEFAULT_SETTINGS.items():
            upsert_setting(k, app.config['PUBLIC_HOST'] if k == 'public_host' else v)
        db.session.commit()
        click.echo('Ironpanel database upgraded')
