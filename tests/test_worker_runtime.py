import multiprocessing as mp
import threading
import time
from datetime import timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import update

from safrasmart.db import CacheDado, agora
from safrasmart.runtime import worker_local
from safrasmart.validacao import validar
from safrasmart.worker import (ParadaSolicitada, executar_isolado, processar_um,
                               rodar_worker, sinal_de_vida)


def _filho_fixture(canal, url, dados):
    canal.send({'resultado': {'status': 'sucesso', 'valores': [1] * 50000}})
    canal.close()


def _filho_lento(canal, url, dados):
    try:
        time.sleep(30)
    finally:
        canal.close()


def test_api_informa_ausencia_de_worker_sem_bloquear_cadastro(client, payload, headers):
    assert client.get('/api/health').json == {'status': 'ok', 'worker': {'ativo': False, 'instancias': 0}}
    assert client.post('/api/analises', json=payload, headers=headers).status_code == 202
    assert client.get('/api/analises/' + payload['id'], headers=headers).json['status'] == 'pendente'


def test_fluxo_fila_worker_resultado_e_sinal_de_vida(app, client, payload, headers):
    repo = app.extensions['repo']
    client.post('/api/analises', json=payload, headers=headers)
    def analisar(_):
        assert client.get('/api/health').json['worker']['ativo'] is True
        return {'status': 'parcial', 'erros': ['Satélite indisponível no cenário de teste']}
    rodar_worker(repo, once=True, executar=analisar)
    r = client.get('/api/analises/' + payload['id'], headers=headers)
    assert r.json['status'] == 'ok'
    assert r.json['resultado']['status'] == 'parcial'
    assert r.json['tentativas'] == 1
    assert client.get('/api/health').json['worker']['ativo'] is False


def test_sinais_independentes_e_expiracao(app):
    repo = app.extensions['repo']
    with sinal_de_vida(repo, intervalo=60):
        with sinal_de_vida(repo, intervalo=60):
            assert repo.status_worker() == {'ativo': True, 'instancias': 2}
        assert repo.status_worker() == {'ativo': True, 'instancias': 1}
        with repo.session.begin() as session:
            session.execute(update(CacheDado).where(CacheDado.chave.like('worker:%')).values(expira_em=agora() - timedelta(seconds=1)))
        assert repo.status_worker()['ativo'] is False
    assert repo.status_worker()['ativo'] is False


def test_sinal_renova_enquanto_analise_executa(app, monkeypatch):
    repo = app.extensions['repo']
    renovar = threading.Event()
    original = repo.cache_set
    chamadas = []
    def gravar(*args):
        original(*args)
        chamadas.append(1)
        if len(chamadas) >= 2:
            renovar.set()
    monkeypatch.setattr(repo, 'cache_set', gravar)
    with sinal_de_vida(repo, intervalo=.02):
        assert renovar.wait(2)
        assert repo.status_worker()['ativo']


def test_servidor_local_inicia_e_encerra_worker(app, monkeypatch):
    iniciado, encerrado = threading.Event(), threading.Event()
    def executar(repo, parar):
        assert repo is app.extensions['repo']
        iniciado.set()
        parar.wait(5)
        encerrado.set()
    monkeypatch.setenv('START_WORKER', 'true')
    monkeypatch.setattr('safrasmart.runtime.rodar_worker', executar)
    with worker_local(app):
        assert iniciado.wait(2)
        assert not encerrado.is_set()
    assert encerrado.is_set()


def test_servidor_pode_usar_worker_externo(app, monkeypatch):
    executar = Mock()
    monkeypatch.setenv('START_WORKER', 'false')
    monkeypatch.setattr('safrasmart.runtime.rodar_worker', executar)
    with worker_local(app):
        pass
    executar.assert_not_called()


def test_interrupcao_devolve_job_sem_consumir_tentativa(app, payload):
    repo = app.extensions['repo']
    repo.registrar('owner', validar(payload))
    def interromper(_):
        raise ParadaSolicitada()
    assert processar_um(repo, executar=interromper)
    registro = repo.obter('owner', payload['id'])
    assert registro['status'] == 'pendente'
    assert registro['tentativas'] == 0
    assert registro['persistido']
    job = repo.reivindicar()
    assert job['tentativas'] == 1


def test_worker_atrasado_nao_devolve_novo_job(app, payload):
    repo = app.extensions['repo']
    repo.registrar('owner', validar(payload))
    antigo = repo.reivindicar()
    assert repo.devolver(antigo)
    novo = repo.reivindicar()
    assert not repo.devolver(antigo)
    assert repo.finalizar(novo, resultado={'fixture': True})


def test_subprocesso_recebe_mesmo_banco_da_fila(app, payload, monkeypatch):
    repo = app.extensions['repo']
    repo.registrar('owner', validar(payload))
    executar = Mock(return_value={'fixture': True})
    monkeypatch.setattr('safrasmart.worker.executar_isolado', executar)
    assert processar_um(repo)
    assert executar.call_args.args[1] == repo.engine.url


def test_processo_isolado_entrega_resultado_grande_e_termina(monkeypatch):
    monkeypatch.setattr('safrasmart.worker._filho', _filho_fixture)
    resultado = executar_isolado({}, 'sqlite:///:memory:', timeout=10)
    assert len(resultado['valores']) == 50000


def test_cancelar_processo_interrompe_espera_e_remove_filho(monkeypatch):
    monkeypatch.setattr('safrasmart.worker._filho', _filho_lento)
    anteriores = {p.pid for p in mp.active_children()}
    parar = threading.Event()
    timer = threading.Timer(.2, parar.set)
    timer.start()
    inicio = time.monotonic()
    try:
        with pytest.raises(ParadaSolicitada):
            executar_isolado({}, 'sqlite:///:memory:', timeout=30, parar=parar)
    finally:
        timer.cancel()
    assert time.monotonic() - inicio < 7
    assert {p.pid for p in mp.active_children()} == anteriores


def test_timeout_continua_limitando_processo(monkeypatch):
    monkeypatch.setattr('safrasmart.worker._filho', _filho_lento)
    anteriores = {p.pid for p in mp.active_children()}
    with pytest.raises(TimeoutError, match='Tempo máximo'):
        executar_isolado({}, 'sqlite:///:memory:', timeout=.1)
    assert {p.pid for p in mp.active_children()} == anteriores
