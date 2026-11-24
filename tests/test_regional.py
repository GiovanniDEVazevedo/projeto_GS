import csv
from datetime import date, timedelta
from io import StringIO
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import select

from safrasmart.db import Importacao
from safrasmart.regional import catalogo, clima, ibge, perfil, zarc
from safrasmart.regional.analises import anos_analogos, balanco_hidrico, janela
from safrasmart.validacao import validar

CODIGO = "5107925"
MALHA = {"type": "Polygon", "coordinates": [[[-56, -13], [-55, -13], [-55, -12], [-56, -12], [-56, -13]]]}


def publicar(sessao, tipo, dados, recorte=""):
    return catalogo.publicar(sessao, tipo, CODIGO, dados, fonte="Fonte de teste",
                            versao="1", url="https://example.org", licenca="Fixture", recorte=recorte)


def tabua():
    regra = {"Nome_cultura": "Milho 1ª Safra", "SafraIni": "2026", "SafraFin": "2027",
             "Cod_Cultura": "12015080000011", "Cod_Ciclo": "20", "Cod_Solo": "11", "geocodigo": CODIGO,
             "Cod_Outros_Manejos": "1", "Nome_Outros_Manejos": "Sequeiro", "Cod_Clima": "0", "Nome_Clima": "Não se aplica",
             "Cod_NM": "", "Produtividade": "", "Portaria": "Port.225_de_10-07-2026",
             **dict.fromkeys(zarc.DECENDIOS, "0"), "dec28": "30", "dec36": "20"}
    arquivo = StringIO()
    escritor = csv.DictWriter(arquivo, list(regra), delimiter=";")
    escritor.writeheader()
    escritor.writerow(regra)
    arquivo.seek(0)
    return arquivo


def test_publicacao_idempotente_reversivel_e_atomica(app):
    sessao = app.extensions["repo"].session
    with sessao.begin() as s:
        anterior = publicar(s, "pam", {"series": [1]}, "1612")
        assert publicar(s, "pam", {"series": [1]}, "1612") == anterior
        novo = publicar(s, "pam", {"series": [2]}, "1612")
    with pytest.raises(ValueError, match="falha"):
        with sessao.begin() as s:
            publicar(s, "pam", {"series": [3]}, "1612")
            raise ValueError("falha antes de publicar")
    with sessao.begin() as s:
        assert catalogo.carregar(s, "pam", CODIGO, "1612").id == novo
        assert len(s.scalars(select(Importacao)).all()) == 2
        catalogo.ativar(s, anterior)
    with sessao() as s:
        assert catalogo.carregar(s, "pam", CODIGO, "1612").dados == {"series": [1]}


def test_localiza_contorno_sem_inventar_codigo(app):
    sessao = app.extensions["repo"].session
    with sessao.begin() as s:
        catalogo.cadastrar_municipio(s, CODIGO, "Sorriso", "MT", MALHA, "IBGE 2024")
    with sessao() as s:
        municipio, origem = catalogo.localizar_municipio(s, -12.55, -55.72)
        assert (municipio.codigo, origem) == (CODIGO, "malha_ibge")
        assert catalogo.localizar_municipio(s, 0, 0, CODIGO) == (None, "municipio_diverge_da_area")
        assert catalogo.localizar_municipio(s, 0, 0)[0] is None


def test_pam_preserva_safra_unidade_e_valor_suprimido():
    resposta = [{"V": "Valor"}, {"D1C": CODIGO, "D2C": "112", "D3C": "2024",
        "D4C": "114253", "MN": "Quilogramas por Hectare", "V": "X"},
        {"D1C": CODIGO, "D2C": "112", "D3C": "2024",
         "D4C": "114254", "MN": "Quilogramas por Hectare", "V": "0"}]
    primeiro, segundo = ibge.ler_pam(resposta, "839", [CODIGO])[CODIGO]
    assert primeiro["recorte"] == "primeira_safra"
    assert primeiro["medidas"]["rendimento"] == {
        "original": "X", "valor": None, "unidade": "Quilogramas por Hectare",
    }
    assert segundo["medidas"]["rendimento"]["valor"] == 0
    resposta[-1]["MN"] = "Toneladas"
    with pytest.raises(ValueError, match="unidade"):
        ibge.ler_pam(resposta, "839", [CODIGO])


def test_zarc_consulta_combinacao_e_portaria_sem_converter_textura(client, app, headers):
    regras = zarc.ler_zarc(tabua(), "2026/2027", [CODIGO])[CODIGO]
    with app.extensions["repo"].session.begin() as s:
        catalogo.cadastrar_municipio(s, CODIGO, "Sorriso", "MT", MALHA)
        publicar(s, "zarc", {"regras": regras}, "2026/2027")
    url = "/api/regional/zarc?municipio=" + CODIGO + "&cultura=milho&safra=2026/2027"
    opcoes = client.get(url + "&irrigacao=sequeiro", headers=headers).json
    assert len(opcoes["opcoes"]) == 1
    assert "AD1" in opcoes["opcoes"][0]["rotulo"]
    assert client.get(url + "&irrigacao=gotejo", headers=headers).json["opcoes"] == []
    resposta = client.get(url + "&regra=" + regras[0]["id"], headers=headers).json
    assert resposta["janelas"] == [
        {"decendio": 28, "inicio": "01/10", "fim": "10/10", "risco_pct": 30},
        {"decendio": 36, "inicio": "21/12", "fim": "31/12", "risco_pct": 20},
    ]
    assert resposta["portaria"] == "Port.225_de_10-07-2026"
    assert client.get(url.replace("2026/2027", "2025/2026"), headers=headers).json["status"] == "sem_referencia"


def test_clima_trata_lacuna_zero_e_anos_futuros():
    serie = {"2025-10-01": {"chuva_mm": 0}, "2025-10-03": {"chuva_mm": 5}}
    parcial = janela(serie, date(2025, 10, 3), 3)
    assert parcial["chuva_mm"] is None and parcial["chuva_parcial_mm"] == 5 and parcial["dias_chuva"] == 2
    for ano, chuva in [(2022, 2), (2023, 3), (2024, 1), (2025, 2), (2026, 2)]:
        serie[f"{ano}-11-01"] = {"chuva_mm": chuva}
    analogos = anos_analogos(serie, date(2025, 11, 1), tamanho=1)
    assert analogos["amostras"] == 3
    assert analogos["casos"][0]["fim"] == "2022-11-01"
    assert analogos["casos"][0]["distancia"] == 0


def test_inmet_agrega_24_horas_utc_e_preserva_dia_parcial():
    linhas = [
        "CODIGO (WMO):;A001", "LATITUDE:;-12,55", "LONGITUDE:;-55,72", "ALTITUDE:;300,0",
        "DATA (YYYY-MM-DD);HORA (UTC);PRECIPITAÇÃO TOTAL, HORÁRIO (mm);"
        "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C);TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C)",
    ]
    linhas += [f"2026-01-01;{hora:02d}00 UTC;0,5;27;18" for hora in range(1, 24)]
    linhas += ["2026-01-02;0000 UTC;0,5;25;16", "2026-01-02;0100 UTC;-9999;25;16"]
    diaria, ponto = clima.ler_inmet("\n".join(linhas).encode("latin-1"))
    assert diaria["2026-01-01"] == {"chuva_mm": 12, "temp_max": 27, "temp_min": 16}
    assert diaria["2026-01-02"]["chuva_mm"] is None
    assert ponto["estacao"] == "A001"


def test_chirps_preliminar_e_final_podem_coexistir(app):
    dias = clima.ler_chirps_csv(StringIO("data,precipitacao_mm\n2026-01-01,0\n2026-01-02,\n"))
    sessao = app.extensions["repo"].session
    with sessao.begin() as s:
        for edicao in ("preliminar", "final"):
            publicar(s, "clima", {"dias": dias}, f"chirps-rnl-{edicao}")
    with sessao() as s:
        assert len(catalogo.publicacoes_ativas(s, "clima", CODIGO)) == 2
        r = perfil.resumir_clima(catalogo.carregar(s, "clima", CODIGO, "chirps-rnl-final"), date(2026, 1, 3))
        assert r["ultimo_dia"] == "2026-01-01"
        assert r["janelas"][0]["dias_chuva"] == 1


def test_balanco_hidrico_respeita_armazenamento_e_lacunas():
    fim = date(2026, 11, 1)
    ini = fim - timedelta(days=1)
    parametros = {"cad_mm": 10, "armazenamento_inicial_mm": 0, "kc": 1, "sequeiro": True}
    serie = {ini.isoformat(): {"chuva_mm": 25, "et0_mm": 3}, fim.isoformat(): {"chuva_mm": 0, "et0_mm": 15}}
    r = balanco_hidrico(serie, ini, fim, parametros)
    assert r["dias"][0]["excedente_mm"] == 12
    assert r["dias"][1]["demanda_nao_atendida_mm"] == 5
    assert r["armazenamento_final_mm"] == 0
    assert balanco_hidrico(serie, ini, fim, {**parametros, "sequeiro": False})["status"] == "dados_diarios_incompletos"


def test_worker_entrega_contexto_no_resultado(app, payload, monkeypatch):
    from safrasmart import worker

    repo = app.extensions["repo"]
    with repo.session.begin() as s:
        catalogo.cadastrar_municipio(s, CODIGO, "Sorriso", "MT", MALHA, "IBGE 2024")
        publicar(s, "pam", {"series": [{"cultura": "soja", "ano": 2024, "recorte": "total_anual", "medidas": {}}]}, "1612")
    monkeypatch.setenv("ENABLE_NDVI", "false")
    monkeypatch.setattr("safrasmart.analisar.buscar_dados_meteo", lambda *a, **kw: None)
    canal = Mock()
    dados = validar({**payload, "id": str(uuid4()), "lat": -12.55, "lon": -55.72})
    worker._filho(canal, repo.engine.url, dados)
    resultado = canal.send.call_args.args[0]["resultado"]
    assert resultado["regional"]["municipio"]["codigo"] == CODIGO
    assert resultado["regional"]["pam"]["series"][0]["registros"][0]["ano"] == 2024


def test_casos_de_talhao_usam_apenas_safras_anteriores_do_dono(app, payload):
    from safrasmart.regional.casos import casos_do_talhao

    repo = app.extensions["repo"]
    talhao = {"id": str(uuid4()), "nome": "Norte", "geometria": {"type": "Polygon", "coordinates": [
        [[-55.721, -12.551], [-55.719, -12.551], [-55.719, -12.549], [-55.721, -12.549], [-55.721, -12.551]]]}}
    def resultado(dia, chuva):
        return {"metadata": {"data_referencia": dia}, "fase": {"nome": "V6-VT"},
                "indices": {"precip_total": chuva, "temp_media_geral": 24, "precip_completa": True,
                            "dias_esperados": 15, "cobertura_temperatura": .9}}

    base = {**payload, "talhao": talhao, "vistoria": {"retorno": "Registrado na revisita"}}
    ano_atual = date.today().year + 1
    for dono, ano, chuva in [("a", ano_atual - 4, 20), ("a", ano_atual - 3, 30),
                             ("a", ano_atual - 2, 40), ("b", ano_atual - 1, 30)]:
        repo.registrar(dono, validar({**base, "id": str(uuid4()), "data_plantio": f"{ano}-10-01"}))
        job = repo.reivindicar()
        assert repo.finalizar(job, resultado=resultado(f"{ano}-11-01", chuva))
    dados = validar({**base, "data_plantio": f"{ano_atual}-10-01"})
    with repo.session() as s:
        achados = casos_do_talhao(s, "a", dados, resultado(f"{ano_atual}-11-01", 30))
    assert achados["amostras"] == 3
    assert achados["casos"][0]["plantio"] == f"{ano_atual - 3}-10-01"
    assert achados["casos"][0]["distancia"] == 0
