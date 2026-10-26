"""Fila no próprio banco, sem Redis. Inicie com python -m safrasmart.worker."""
import argparse
import logging
import multiprocessing as mp
import os
import time
import threading
from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from .cache import CacheAnalitico
from .db import criar_engine
from .repositorio import Repositorio

log = logging.getLogger(__name__)


class ParadaSolicitada(Exception):
    pass


@contextmanager
def sinal_de_vida(repo, intervalo=5, ttl=30):
    """Sinal renovado inclusive enquanto uma consulta externa está bloqueada."""
    chave = "worker:" + uuid4().hex
    encerrar = threading.Event()

    def publicar():
        try:
            repo.cache_set(chave, {"tipo": "worker"}, ttl)
        except SQLAlchemyError:
            log.warning("Não foi possível renovar o sinal do worker.")

    def renovar():
        while not encerrar.wait(intervalo):
            publicar()

    publicar()
    thread = threading.Thread(target=renovar, name="worker-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        encerrar.set()
        thread.join(timeout=2)
        try:
            repo.cache_remover(chave)
        except SQLAlchemyError:
            log.warning("Sinal do worker expirará automaticamente.")


def _filho(canal, url, dados):
    engine = criar_engine(url)
    try:
        from .analisar import analisar
        resultado = analisar(lat=dados["lat"], lon=dados["lon"], cultura=dados["cultura"],
            data_plantio_dt=datetime.fromisoformat(dados["data_plantio"]), solo=dados["solo"],
            irrigacao=dados["irrigacao"], prod_ant=dados["prod_ant"], observacoes=dados["observacoes"],
            usar_ndvi=os.getenv("ENABLE_NDVI", "true").lower() == "true",
            cache=CacheAnalitico(Repositorio(engine)))
        canal.send({"resultado": resultado})
    except Exception:
        log.exception("Falha no processamento")
        canal.send({"erro": "Falha temporária no processamento. Consulte os logs do worker."})
    finally:
        canal.close()
        engine.dispose()


def executar_isolado(dados, url, timeout=180, parar=None):
    # Processo, e não thread: o timeout pode encerrar o trabalho efetivamente.
    contexto = mp.get_context("spawn")
    receber, enviar = contexto.Pipe(duplex=False)
    processo = contexto.Process(target=_filho, args=(enviar, url, dados))
    processo.start()
    enviar.close()
    try:
        prazo = time.monotonic() + timeout
        while True:
            if parar is not None and parar.is_set():
                raise ParadaSolicitada()
            restante = prazo - time.monotonic()
            if restante <= 0:
                raise TimeoutError("Tempo máximo da análise excedido.")
            if receber.poll(min(.5, restante)):
                try:
                    resposta = receber.recv()
                except EOFError:
                    raise RuntimeError("O processo analítico foi interrompido.") from None
                if resposta.get("erro"):
                    raise RuntimeError(resposta["erro"])
                return resposta["resultado"]
    finally:
        receber.close()
        processo.join(timeout=1)
        if processo.is_alive():
            processo.terminate()
            processo.join(timeout=3)
        if processo.is_alive():
            processo.kill()
            processo.join()


def processar_um(repo, executar=None, parar=None):
    job = repo.reivindicar()
    if not job:
        return False
    inicio = time.monotonic()
    try:
        # Não reavaliar o ambiente: usar a mesma conexão configurada na fila.
        resultado = (executar or (lambda dados: executar_isolado(dados, repo.engine.url)))(job["entrada"])
    except Exception:
        log.exception("analise_falhou id=%s tentativa=%s", job["id"], job["tentativas"])
        repo.finalizar(job, erro="Não foi possível concluir a análise. Uma nova tentativa será feita até o limite de 3.")
    else:
        repo.finalizar(job, resultado=resultado)
        log.info("analise_concluida id=%s duracao_s=%.2f", job["id"], time.monotonic() - inicio)
    return True


def rodar_worker(repo, parar=None, *, once=False, executar=None):
    parar = parar if parar is not None else threading.Event()
    with sinal_de_vida(repo):
        while not parar.is_set():
            try:
                encontrou = processar_um(repo, executar=executar, parar=parar)
            except SQLAlchemyError:
                log.error("Banco indisponível no worker; verifique conexão e migrações.")
                encontrou = False
            if once:
                break
            if not encontrou:
                parar.wait(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Processa no máximo um trabalho e termina")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    repo = Repositorio(criar_engine())
    try:
        rodar_worker(repo, once=args.once)
    except KeyboardInterrupt:
        pass
    finally:
        repo.engine.dispose()


if __name__ == "__main__":
    main()
