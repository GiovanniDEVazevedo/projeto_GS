"""Worker no servidor local; em Gunicorn, o processo continua separado."""
import logging
import threading
from contextlib import contextmanager

from .worker import rodar_worker
from .config import booleano_env

log = logging.getLogger(__name__)


@contextmanager
def worker_local(app):
    habilitado = booleano_env("START_WORKER", True)
    if not habilitado:
        log.info("Worker local desativado. Execute python -m safrasmart.worker separadamente.")
        yield
        return
    parar = threading.Event()
    thread = threading.Thread(target=rodar_worker, args=(app.extensions["repo"], parar),
                              name="safrasmart-worker", daemon=True)
    thread.start()
    log.info("Worker local iniciado junto com o servidor.")
    try:
        yield
    finally:
        parar.set()
        thread.join(timeout=10)
