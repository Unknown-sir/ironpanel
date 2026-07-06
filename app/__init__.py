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

    from .web import web_bp
    from .api.routes import api_bp
    from .api_v2.routes import api_v2_bp
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(api_v2_bp, url_prefix='/api/v2')

    from .commands import register_commands
    register_commands(app)
    return app
