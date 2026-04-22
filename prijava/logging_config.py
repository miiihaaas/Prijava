import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def configure_logging(app):
    """Konfiguriše logging sistem za Flask aplikaciju"""
    logs_dir = os.path.join(app.root_path, 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s u %(module)s: %(message)s'
    )

    file_handler = RotatingFileHandler(
        os.path.join(logs_dir, 'prijava.log'),
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    is_production = os.getenv('FLASK_ENV') == 'production' or os.getenv('ENVIRONMENT') == 'production'
    if not is_production:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG)
        app.logger.addHandler(console_handler)

    app.logger.setLevel(logging.INFO)

    try:
        app.logger.info('Prijava aplikacija pokrenuta')
    except BrokenPipeError:
        pass
