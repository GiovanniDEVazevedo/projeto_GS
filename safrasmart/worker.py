"""Fila no próprio banco, sem Redis. Inicie com python -m safrasmart.worker."""
import argparse
import logging
import multiprocessing as mp
import os
import time
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from .cache import CacheAnalitico
from .config import database_url
from .db import criar_engine
from .repositorio import Repositorio

log = logging.getLogger(__name__)


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


def executar_isolado(dados, url, timeout=180):
    # Processo, e não thread: o timeout pode encerrar o trabalho efetivamente.
    contexto = mp.get_context("spawn")
    receber, enviar = contexto.Pipe(duplex=False)
    processo = contexto.Process(target=_filho, args=(enviar, url, dados))
    processo.start()
    enviar.close()
    try:
        if receber.poll(timeout):
            try:
                resposta = receber.recv()
            except EOFError:
                raise RuntimeError("O processo analítico foi interrompido.") from None
            if resposta.get("erro"):
                raise RuntimeError(resposta["erro"])
            return resposta["resultado"]
        raise TimeoutError("Tempo máximo da análise excedido.")
    finally:
        receber.close()
        processo.join(timeout=1)
        if processo.is_alive():
            processo.terminate()
            processo.join(timeout=3)
        if processo.is_alive():
            processo.kill()
            processo.join()


def processar_um(repo, executar=None):
    job = repo.reivindicar()
    if not job:
        return False
    inicio = time.monotonic()
    try:
        resultado = (executar or (lambda dados: executar_isolado(dados, database_url())))(job["entrada"])
    except Exception:
        log.exception("analise_falhou id=%s tentativa=%s", job["id"], job["tentativas"])
        repo.finalizar(job, erro="Não foi possível concluir a análise. Uma nova tentativa será feita até o limite de 3.")
    else:
        repo.finalizar(job, resultado=resultado)
        log.info("analise_concluida id=%s duracao_s=%.2f", job["id"], time.monotonic() - inicio)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Processa no máximo um trabalho e termina")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    repo = Repositorio(criar_engine())
    try:
        while True:
            try:
                encontrou = processar_um(repo)
            except SQLAlchemyError:
                log.exception("Banco indisponível no worker")
                encontrou = False
            if args.once:
                break
            if not encontrou:
                time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        repo.engine.dispose()


if __name__ == "__main__":
    main()
