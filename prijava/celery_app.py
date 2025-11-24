from celery import Celery
import os

# Kreiramo instancu celery direktno na nivou modula
# Tako da se može importovati kao prijava.celery_app.celery

def make_celery(app=None):
    """
    Kreira Celery instancu koja može da koristi Flask konfiguraciju
    """
    # Koristimo Redis sa ispravnim podacima sa vašeg servera
    redis_url = os.environ.get('REDIS_URL', 'redis://:KCxrpjWsrY@127.0.0.1:6025/1')
    
    celery = Celery(
        'prijava',
        broker=redis_url,
        backend=redis_url,
        include=['prijava.tasks']
    )
    
    # Učitaj konfiguraciju iz Flask aplikacije ako je prosleđena
    if app:
        celery.conf.update(app.config)
        
        # Kreiramo klasu TaskBase koja će imati pristup Flask kontekstu
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
                    
        celery.Task = ContextTask
        
    return celery

# Kreiramo celery instancu koja će biti dostupna kao prijava.celery_app.celery
celery = make_celery()