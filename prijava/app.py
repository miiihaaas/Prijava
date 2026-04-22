import json

from dotenv import load_dotenv
from flask import Flask

from prijava import db, login_manager, mail, migrate
from prijava.celery_app import init_celery
from prijava.config import apply_config
from prijava.context import register_context
from prijava.errors import register_error_handlers
from prijava.logging_config import configure_logging

load_dotenv()


def create_app():
    app = Flask(__name__)

    apply_config(app)
    configure_logging(app)

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    login_manager.init_app(app)

    from prijava.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.template_filter('from_json')
    def from_json(value):
        try:
            if value:
                return json.loads(value)
            return []
        except Exception as exc:
            app.logger.error(f"Greška pri pretvaranju JSON-a: {exc}")
            return []

    register_context(app)
    register_error_handlers(app)
    init_celery(app)

    from prijava.blueprints import register_blueprints
    register_blueprints(app)

    return app
