import math
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

from safrasmart.api.server import create_app
from safrasmart.db import Analise, Propriedade, Safra, agora
from safrasmart.validacao import validar
from safrasmart.worker import processar_um


def test_sync_parcial_e_reenvio_idempotente(client, app, payload, headers):
    invalido = {**payload, "id": str(uuid4()), "cultura": "cafe"}
    response = client.post('/api/sync', json=[payload, invalido], headers=headers)
    assert response.status_code == 200
    resultados = response.json
    assert resultados[0]['persistido'] is True
    assert resultados[1]['persistido'] is False
    assert resultados[1]['status'] == 'invalido'
    for _ in range(3):
        assert client.post('/api/analises', json=payload, headers=headers).status_code == 202
    with app.extensions['repo'].session() as s:
        assert s.scalar(select(func.count()).select_from(Analise)) == 1
        assert s.scalar(select(func.count()).select_from(Safra)) == 1
        assert s.scalar(select(func.count()).select_from(Propriedade)) == 1


def test_uuid_reutilizado_com_dados_diferentes(client, payload, headers):
    client.post('/api/analises', json=payload, headers=headers)
    r = client.post('/api/analises', json={**payload, 'observacoes': 'Solo encharcado'}, headers=headers)
    assert r.status_code == 409
    assert r.json['erro']


def test_servidor_reiniciado_preserva_fila_e_resultado(client, app, payload, headers):
    client.post('/api/analises', json=payload, headers=headers)
    novo = create_app(app.config).test_client()
    assert novo.get('/api/analises/' + payload['id'], headers=headers).json['status'] == 'pendente'
    assert processar_um(app.extensions['repo'], executar=lambda _: {'status': 'parcial', 'erros': ['Clima indisponível']})
    resposta = novo.get('/api/analises/' + payload['id'], headers=headers)
    assert resposta.json['status'] == 'ok'
    assert resposta.json['resultado']['status'] == 'parcial'
    assert novo.post('/api/analises', json=payload, headers=headers).status_code == 200


def test_historico_isolado_por_credencial(client, payload, headers):
    client.post('/api/analises', json=payload, headers=headers)
    outro = {'Authorization': 'Bearer ' + 'b' * 64}
    assert client.get('/api/analises/' + payload['id'], headers=outro).status_code == 404
    assert client.get('/api/analises', headers=outro).json == []
    assert client.get('/api/propriedades', headers=outro).json == []
    assert client.get('/api/safras', headers=headers).json[0]['cultura'] == 'soja'
    assert client.get('/api/analises').status_code == 401
    assert client.get('/api/health').status_code == 200


@pytest.mark.parametrize('alteracao', [
    {'lat': float('nan')}, {'lon': float('inf')}, {'lat': True}, {'lon': 181}, {'lat': -91},
    {'data_plantio': '2026-02-30'}, {'data_plantio': '2050-10-01'}, {'cultura': 'batata'},
    {'solo': []}, {'irrigacao': {}}, {'observacoes': 10}, {'observacoes': 'x' * 4001},
    {'prod_ant': -1}, {'prod_ant': True}, {'prod_ant': 'nan'}, {'id': '123'}, {'precisao_m': -1}
])
def test_entrada_invalida_e_400(client, headers, payload, alteracao):
    assert client.post('/api/analises', json={**payload, **alteracao}, headers=headers).status_code == 400


@pytest.mark.parametrize('body', [None, [], 42, 'x'])
def test_json_invalido(client, headers, body):
    response = client.post('/api/analises', json=body, headers=headers)
    assert response.status_code in (400, 415)


def test_sync_lote_invalido(client, headers, payload):
    assert client.post('/api/sync', json={}, headers=headers).status_code == 400
    assert client.post('/api/sync', json=[payload] * 51, headers=headers).status_code == 400
    response = client.post('/api/sync', json=[None, payload], headers=headers)
    assert response.status_code == 200
    assert [r['persistido'] for r in response.json] == [False, True]


def test_worker_lease_e_finalizacao_tardia(app, payload):
    repo = app.extensions['repo']
    repo.registrar('owner', validar(payload))
    job = repo.reivindicar()
    assert job is not None
    assert repo.reivindicar() is None
    with repo.session.begin() as s:
        s.execute(update(Analise).values(lease_ate=agora() - timedelta(seconds=1)))
    novo = repo.reivindicar()
    assert novo['token'] != job['token']
    assert not repo.finalizar(job, resultado={'antigo': True})
    assert repo.finalizar(novo, resultado={'novo': True})
    assert repo.obter('owner', payload['id'])['resultado'] == {'novo': True}


def test_retries_persistentes_com_limite(app, payload):
    repo = app.extensions['repo']
    repo.registrar('owner', validar(payload))
    def falhar(_):
        raise TimeoutError('externo')
    for _ in range(3):
        assert processar_um(repo, executar=falhar)
        with repo.session.begin() as s:
            s.execute(update(Analise).values(disponivel_em=agora() - timedelta(seconds=1)))
    assert repo.obter('owner', payload['id'])['status'] == 'erro'
    assert not processar_um(repo, executar=falhar)


def test_envios_concorrentes_nao_duplicam(app, payload):
    repo = app.extensions['repo']
    dados = validar(payload)
    with ThreadPoolExecutor(max_workers=4) as pool:
        respostas = list(pool.map(lambda _: repo.registrar('owner', dados), range(8)))
    assert all(r['persistido'] for r in respostas)
    with repo.session() as s:
        assert s.scalar(select(func.count()).select_from(Analise)) == 1


def test_worker_concorrente_adquire_uma_vez(app, payload):
    repo = app.extensions['repo']
    repo.registrar('owner', validar(payload))
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = list(pool.map(lambda _: repo.reivindicar(), range(4)))
    assert sum(j is not None for j in jobs) == 1


def test_headers_e_serviceworker(client):
    sw = client.get('/sw.js')
    assert sw.status_code == 200
    assert sw.headers['Service-Worker-Allowed'] == '/'
    assert client.get('/api/health').headers['Cache-Control'] == 'no-store'
    assert "script-src 'self'" in client.get('/').headers['Content-Security-Policy']
