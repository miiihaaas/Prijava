from prijava.blueprints.admin import admin_bp
from prijava.blueprints.api import api_bp
from prijava.blueprints.auth import auth_bp
from prijava.blueprints.public import public_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
