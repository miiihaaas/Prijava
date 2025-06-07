from datetime import timedelta, datetime
import os, ast
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=10)
app.config['JSON_AS_ASCII'] = False
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))  # Pretvori u int
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS').lower() in ['true', 'on', '1']
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL').lower() in ['true', 'on', '1']
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')
# Učitaj string iz .env fajla
mail_default_sender = os.getenv('MAIL_DEFAULT_SENDER')

# Konvertuj string u tuple ako postoji
if mail_default_sender:
    app.config['MAIL_DEFAULT_SENDER'] = ast.literal_eval(mail_default_sender)

# Inicijalizacija ekstenzija
db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Molimo prijavite se da biste pristupili ovoj stranici.'
login_manager.login_message_category = 'info'

# Inicijalizacija Celery
from prijava.celery_app import make_celery
celery = make_celery(app)

# Učitavanje modela
from prijava.models import User, Application

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_app():
    from prijava import routes
    return app

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()  # Poništi trenutnu transakciju u slučaju greške
    return render_template('errors/500.html'), 500

@app.errorhandler(400)
def bad_request_error(error):
    return render_template('errors/400.html'), 400

@app.errorhandler(405)
def method_not_allowed_error(error):
    return render_template('errors/405.html'), 405

