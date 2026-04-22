from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Molimo prijavite se da biste pristupili ovoj stranici.'
login_manager.login_message_category = 'info'


from prijava.app import create_app  # noqa: E402  (re-export for run.py / init_db.py / create_admin.py)

app = create_app()
