from celery import Celery

def make_celery(app=None):
    """
    Kreira Celery instancu koja može da koristi Flask konfiguraciju
    """
    # Koristimo Redis sa ispravnim podacima sa vašeg servera
    redis_url = 'redis://:7GHdXQBCHo@localhost:6025/0'
    
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