from datetime import timedelta

from sqlalchemy import update

from safrasmart.db import Analise, agora
from safrasmart.validacao import validar


def test_quedas_repetidas_encerram_job_sem_perder_entrada(app, payload):
    repo = app.extensions['repo']
    repo.registrar('owner', validar(payload))
    for tentativa in range(1, 4):
        job = repo.reivindicar()
        assert job['tentativas'] == tentativa
        with repo.session.begin() as session:
            session.execute(update(Analise).values(lease_ate=agora() - timedelta(seconds=1)))
    assert repo.reivindicar() is None
    registro = repo.obter('owner', payload['id'])
    assert registro['status'] == 'erro'
    assert registro['persistido'] is True
    assert registro['tentativas'] == 3
