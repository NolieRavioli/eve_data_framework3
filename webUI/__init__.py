# webUI/__init__.py

from flask import Flask
from webUI.sso import auth_bp
from webUI.dashboard import dashboard_bp
from webUI.personal_routes import update_personal_bp
from webUI.public_routes import update_public_bp
from webUI.market_browser import market_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = 'nolieravioli'

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(update_personal_bp)
    app.register_blueprint(update_public_bp)
    app.register_blueprint(market_bp)

    return app
