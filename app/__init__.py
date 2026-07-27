from flask import Flask
from .core.config import Config
from .core.extensions import db, login_manager, socketio
from .core.models import Admin


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)
    login_manager.login_view = 'web.login'

    @login_manager.user_loader
    def load_user(user_id):
        return Admin.query.get(int(user_id))

    @app.context_processor
    def subscription_url_helpers():
        # Expose absolute subscription URLs everywhere in the admin UI.
        # This makes user-list buttons respect the dedicated Subscription Domain
        # instead of falling back to the panel IP/host.
        from .services.provisioning import subscription_url_for_user, get_subscription_base_url
        return dict(
            subscription_url_for_user=subscription_url_for_user,
            subscription_base_url=get_subscription_base_url,
        )

    from .web import web_bp
    from .api.routes import api_bp
    from .api_v2.routes import api_v2_bp
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(api_v2_bp, url_prefix='/api/v2')

    from .commands import register_commands
    register_commands(app)
    return app
