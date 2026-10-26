import os
from uuid import uuid4

import pytest
import requests
from sqlalchemy.engine import make_url

from safrasmart.api.server import create_app
from safrasmart.db import criar_engine, migrar


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    def bloquear(*args, **kwargs):
        raise AssertionError("Testes unitários não podem depender de serviços externos.")
    monkeypatch.setattr(requests.sessions.Session, "request", bloquear)


@pytest.fixture
def payload():
    return {"id": str(uuid4()), "lat": -23.55, "lon": -46.63, "propriedade": "Sítio de teste",
            "cultura": "soja", "data_plantio": "2026-10-01", "solo": "argiloso", "irrigacao": "sequeiro",
            "prod_ant": 0, "observacoes": "Não encontrei lagartas"}


@pytest.fixture
def app(tmp_path):
    # TEST_DATABASE_URL deve apontar exclusivamente para um banco descartável.
    url = os.getenv("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'teste.db'}")
    if os.getenv("TEST_DATABASE_URL"):
        if make_url(url).get_backend_name() != "sqlite" and os.getenv("TEST_ALLOW_DATABASE_RESET") != "1":
            pytest.fail("Use um schema descartável e TEST_ALLOW_DATABASE_RESET=1 para autorizar recriar tabelas.")
        from safrasmart.db import Base
        from sqlalchemy import Column, MetaData, String, Table
        engine = criar_engine(url)
        Base.metadata.drop_all(engine)
        # DROP TABLE IF EXISTS não existe no Oracle 19c/21c.
        Table("alembic_version", MetaData(), Column("version_num", String(32))).drop(engine, checkfirst=True)
        engine.dispose()
    migrar(url)
    application = create_app({"TESTING": True, "DATABASE_URL": url})
    yield application
    application.extensions["repo"].engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def headers():
    return {"Authorization": "Bearer " + "a" * 64}
