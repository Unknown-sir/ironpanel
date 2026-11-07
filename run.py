from app import create_app
from app.core.extensions import socketio

app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=app.config['PANEL_PORT'])
