import os

from celery import Celery


def make_celery():
    """Create a bare Celery instance wired to the Redis broker/backend."""
    redis_url = os.environ.get('REDIS_URL', 'redis://:KCxrpjWsrY@127.0.0.1:6025/1')
    return Celery(
        'prijava',
        broker=redis_url,
        backend=redis_url,
        include=['prijava.tasks'],
    )


# Module-level instance — tasks.py imports this as ``from prijava.celery_app import celery``
celery = make_celery()


def init_celery(app):
    """Hook Celery up to the Flask ``app`` (config + request-scoped task context)."""
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
