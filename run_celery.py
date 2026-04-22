"""
Skripta za pokretanje Celery radnika u razvojnom okruženju.
Pokrenite sa: python run_celery.py

create_app() se poziva zbog bočnog efekta — init_celery(app) postavlja
Flask konfiguraciju i ContextTask na modul-level `celery` singletonu,
koji onda worker koristi.
"""
from prijava import create_app
from prijava.celery_app import celery

create_app()

if __name__ == '__main__':
    celery.worker_main(['worker', '--loglevel=info'])
