from uuid import uuid4

import pytest

from safrasmart.db import criar_engine, migrar
from safrasmart.repositorio import Repositorio
from safrasmart.validacao import validar


def limite():
    return {"type": "Polygon", "coordinates": [[[-55.721, -12.551], [-55.719, -12.551],
            [-55.719, -12.549], [-55.721, -12.549], [-55.721, -12.551]]]}


def test_seleciona_talhao_e_preserva_identidade_da_safra(client, headers, payload):
    talhao = {"id": str(uuid4()), "nome": "Faixa Norte", "geometria": limite()}
    entrada = {**payload, "talhao": talhao}
    primeira = client.post("/api/analises", headers=headers, json=entrada)
    assert primeira.status_code == 202
    dado = primeira.json
    assert dado["talhao"]["lat"] == pytest.approx(-12.55)
    assert dado["talhao"]["area_ha"] > 0
    assert client.post("/api/analises", headers=headers, json=entrada).json["id"] == dado["id"]
    novo = client.post("/api/analises", headers=headers, json={
        **entrada, "id": str(uuid4()), "solo": "misto", "irrigacao": "gotejo",
    })
    assert novo.status_code == 202
    assert novo.json["safra_id"] == dado["safra_id"]
    lista = client.get("/api/talhoes", headers=headers).json
    assert [t["id"] for t in lista] == [talhao["id"]]
    assert client.get("/api/talhoes", headers={"Authorization": "Bearer " + "b" * 64}).json == []
    assert client.post("/api/analises", headers=headers, json={
        **entrada, "id": str(uuid4()), "talhao": {**talhao, "nome": "Alterado"},
    }).status_code == 409


@pytest.mark.parametrize("contorno", [
    [[-55.72, -12.55], [-55.71, -12.54], [-55.72, -12.54], [-55.71, -12.55], [-55.72, -12.55]],
    [[-55.72, -12.55], [-55.71, -12.54], [-55.72, -12.54], [-55.71, -12.55]],
    [[-60, -15], [-50, -15], [-50, -10], [-60, -15]],
])
def test_rejeita_limite_invalido(client, headers, payload, contorno):
    entrada = {**payload, "talhao": {"id": str(uuid4()), "nome": "Inválido",
                                   "geometria": {"type": "Polygon", "coordinates": [contorno]}}}
    assert client.post("/api/analises", headers=headers, json=entrada).status_code == 400
    assert client.get("/api/talhoes", headers=headers).json == []


def test_migracao_preserva_analise_existente(tmp_path, payload):
    url = "sqlite:///" + str(tmp_path / "anterior.db")
    migrar(url, "0001")
    engine = criar_engine(url)
    try:
        repo = Repositorio(engine)
        anterior = repo.registrar("dono", validar(payload))
        migrar(url)
        assert repo.obter("dono", payload["id"]) == anterior
        assert repo.registrar("dono", validar(payload)) == anterior
        assert repo.talhoes("dono") == []
    finally:
        engine.dispose()


def test_ndvi_recebe_o_poligono_do_talhao(monkeypatch):
    from datetime import date, datetime
    from unittest.mock import Mock

    from safrasmart.analisar import analisar

    buscar = Mock(return_value={"ndvi": [.4], "ndvi_medio_geral": .4})
    monkeypatch.setattr("safrasmart.analisar.buscar_dados_meteo", lambda *a, **kw: None)
    monkeypatch.setattr("safrasmart.analisar.gee_configurado", lambda: True)
    monkeypatch.setattr("safrasmart.ndvi.buscar_ndvi", buscar)
    r = analisar(-1, -1, "milho", datetime(2026, 10, 1), "misto", "sequeiro", hoje=date(2026, 11, 1),
                 talhao={"id": str(uuid4()), "nome": "Norte", "geometria": limite()})
    assert buscar.call_args.kwargs["geometria"] == limite()
    assert r["metadata"]["talhao"]["nome"] == "Norte"
    assert r["ndvi"]["area"] == "Pixels válidos dentro do polígono do talhão."
