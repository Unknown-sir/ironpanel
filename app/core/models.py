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
    protocols = db.Column(db.String(120), default='openvpn,ocserv,l2tp,wireguard')
    data_limit_mb = db.Column(db.Integer, default=0)
    used_upload_mb = db.Column(db.Integer, default=0)
    used_download_mb = db.Column(db.Integer, default=0)
    connection_limit = db.Column(db.Integer, default=1)
    allowed_devices = db.Column(db.Integer, default=0)
    protocol_permissions = db.Column(db.String(120), default='openvpn,ocserv,l2tp,wireguard')
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
    def used_total_mb(self): return (self.used_upload_mb or 0) + (self.used_download_mb or 0)
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
    protocols = db.Column(db.String(120), default='openvpn,ocserv,l2tp,wireguard')
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
