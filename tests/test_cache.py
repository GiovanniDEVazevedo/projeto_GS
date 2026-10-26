from datetime import timedelta
from sqlalchemy import update
from safrasmart.cache import CacheAnalitico
from safrasmart.db import CacheDado, agora


def test_cache_reutiliza_e_expira(app):
    repo = app.extensions['repo']
    cache = CacheAnalitico(repo)
    chamadas = []
    def calcular():
        chamadas.append(1)
        return {'fonte': 'fixture', 'valores': [1, None]}
    assert cache.obter_ou_calcular({'lat': 1, 'fim': '2026-10-01'}, calcular)
    assert cache.obter_ou_calcular({'fim': '2026-10-01', 'lat': 1}, calcular)
    assert len(chamadas) == 1
    with repo.session.begin() as s:
        s.execute(update(CacheDado).values(expira_em=agora() - timedelta(seconds=1)))
    cache.obter_ou_calcular({'lat': 1, 'fim': '2026-10-01'}, calcular)
    assert len(chamadas) == 2
    cache.obter_ou_calcular({'lat': 1, 'fim': '2026-10-02'}, calcular)
    assert len(chamadas) == 3


def test_cache_nao_congela_resposta_parcial(app):
    repo = app.extensions['repo']
    cache = CacheAnalitico(repo)
    chamadas = []
    def calcular():
        chamadas.append(1)
        return {'completo': len(chamadas) >= 2}
    criterio = lambda r: r['completo']
    assert cache.obter_ou_calcular({'tipo': 'teste'}, calcular, cachear=criterio) == {'completo': False}
    assert cache.obter_ou_calcular({'tipo': 'teste'}, calcular, cachear=criterio) == {'completo': True}
    assert cache.obter_ou_calcular({'tipo': 'teste'}, calcular, cachear=criterio) == {'completo': True}
    assert len(chamadas) == 2
