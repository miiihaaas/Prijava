"""
Skripta za pokretanje Celery radnika u razvojnom okruženju.
Pokrenite sa: python run_celery.py
"""
from prijava.celery_app import make_celery

app = make_celery()

if __name__ == '__main__':
    app.worker_main(['worker', '--loglevel=info'])
