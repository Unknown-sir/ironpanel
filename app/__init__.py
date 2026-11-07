import hmac
import secrets
from urllib.parse import urlparse
from flask import Flask, abort, request, session
from .core.config import Config
from .core.extensions import db, login_manager, socketio
from .core.models import Admin


def get_csrf_token() -> str:
    tok = session.get('_csrf_token')
    if not tok:
        tok = secrets.token_urlsafe(32)
        session['_csrf_token'] = tok
    return tok


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)
    login_manager.login_view = 'web.login'

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(Admin, int(user_id))
        except Exception:
            return Admin.query.get(int(user_id))

    @app.before_request
    def csrf_protect():
        if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return None
        path = request.path or ''
        # API blueprints and Telegram webhook authenticate via headers/tokens
        if path.startswith(('/api/v1/', '/api/v2/', '/api/mirzabot/', '/api/xui/', '/telegram/bot')):
            return None
        if not app.config.get('WTF_CSRF_ENABLED', True):
            return None
        supplied = (
            request.form.get('csrf_token')
            or request.headers.get('X-CSRFToken')
            or request.headers.get('X-CSRF-Token')
            or (request.get_json(silent=True) or {}).get('csrf_token')
        )
        expected = session.get('_csrf_token')
        if supplied:
            if not expected or not hmac.compare_digest(str(expected), str(supplied)):
                abort(400, description='Invalid CSRF token')
            return None
        # Fallback same-origin verification for forms submitted before token injection
        origin = request.headers.get('Origin') or request.headers.get('Referer')
        if origin:
            parsed = urlparse(origin)
            req_host = (request.host or '').split(':')[0].lower()
            orig_host = (parsed.hostname or '').lower()
            if orig_host and req_host and orig_host != req_host:
                abort(400, description='Cross-origin POST blocked')
        return None

    @app.context_processor
    def subscription_url_helpers():
        # Expose absolute subscription URLs and CSRF helper everywhere in the admin UI.
        from .services.provisioning import subscription_url_for_user, get_subscription_base_url
        return dict(
            subscription_url_for_user=subscription_url_for_user,
            subscription_base_url=get_subscription_base_url,
            csrf_token=get_csrf_token,
        )

    from .web import web_bp
    from .api.routes import api_bp
    from .api_v2.routes import api_v2_bp
    from .api_mirzabot.routes import api_mirzabot_bp
    from .api_xui.routes import api_xui_bp
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(api_v2_bp, url_prefix='/api/v2')
    app.register_blueprint(api_mirzabot_bp, url_prefix='/api/mirzabot/v1')
    app.register_blueprint(api_xui_bp, url_prefix='/api/xui')

    from .commands import register_commands
    register_commands(app)
    return app
