import os

from celery import Celery


def make_celery():
    """Create a bare Celery instance wired to the Redis broker/backend.

    Broker transport options su podešene za fail-fast ponašanje: ako Redis
    nije dostupan, ``.delay()`` vraća grešku u ~1s umesto da blokira request
    thread na 5s+ dok Kombu default timeouts ne isteknu.
    """
    redis_url = os.environ.get('REDIS_URL', 'redis://:KCxrpjWsrY@127.0.0.1:6025/1')
    celery = Celery(
        'prijava',
        broker=redis_url,
        backend=redis_url,
        include=['prijava.tasks'],
    )
    celery.conf.update(
        broker_connection_retry=False,
        broker_connection_retry_on_startup=False,
        broker_connection_max_retries=0,
        broker_transport_options={
            'socket_timeout': 1.0,
            'socket_connect_timeout': 1.0,
            'socket_keepalive': True,
        },
        result_backend_transport_options={
            'socket_timeout': 1.0,
            'socket_connect_timeout': 1.0,
        },
    )
    return celery


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
