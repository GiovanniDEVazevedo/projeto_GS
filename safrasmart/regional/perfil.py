"""Consultas e montagem das referências preservadas no resultado da análise."""

from datetime import date, timedelta
from math import asin, cos, radians, sin, sqrt

from . import catalogo, zarc
from .analises import anos_analogos, balanco_hidrico, janela
from .clima import RECORTE_ARQUIVO


def producao(sessao, codigo, cultura):
    series = []
    for tabela in ("1612", "839"):
        publicacao = catalogo.carregar(sessao, "pam", codigo, tabela)
        if publicacao:
            registros = [r for r in publicacao.dados["series"] if r["cultura"] == cultura]
            if registros:
                series.append({"fonte": catalogo.fonte_da(publicacao), "registros": registros})
    return {"status": "disponivel" if series else "sem_serie", "series": series,
            "limitacao": "Produção Agrícola Municipal, agregada para todo o município."}


def consulta_zarc(sessao, codigo, cultura, safra, regra_id=None, irrigacao=None):
    zarc.nome_safra(safra)
    publicacao = catalogo.carregar(sessao, "zarc", codigo, safra)
    if not publicacao:
        return {"status": "sem_referencia", "safra": safra}
    fonte = catalogo.fonte_da(publicacao)
    regras = [r for r in publicacao.dados["regras"] if r["cultura"] == cultura]
    if irrigacao == "sequeiro":
        regras = [r for r in regras if r["manejo"] == 1]
    elif irrigacao in {"aspersao", "gotejo"}:
        regras = [r for r in regras if r["manejo"] in {2, 3}]
    if not regra_id:
        return {"status": "selecionar_combinacao" if regras else "sem_referencia", "safra": safra,
                "fonte": fonte, "opcoes": [{"id": r["id"], "rotulo": zarc.descricao_regra(r)} for r in regras]}
    regra = next((r for r in regras if r["id"] == regra_id), None)
    if regra is None:
        return {"status": "combinacao_indisponivel", "safra": safra, "fonte": fonte}
    return {"status": "disponivel", "safra": safra, "fonte": fonte, "portaria": regra["portaria"],
            "rotulo": zarc.descricao_regra(regra), "janelas": zarc.janelas(regra), "url_portarias": zarc.PORTARIAS}


def resumir_clima(publicacao, referencia):
    serie = publicacao.dados["dias"]
    limite = referencia.isoformat()
    anteriores = [dia for dia, valores in serie.items() if dia < limite and any(v is not None for v in valores.values())]
    fonte = catalogo.fonte_da(publicacao)
    if not anteriores:
        return {"status": "sem_cobertura", "fonte": fonte, "janelas": []}
    fim = date.fromisoformat(max(anteriores))
    return {"status": "disponivel", "fonte": fonte, "ultimo_dia": fim.isoformat(),
            "atraso_dias": (referencia - fim).days - 1,
            "janelas": [janela(serie, fim, tamanho) for tamanho in (7, 15, 30)],
            "anos_analogos": anos_analogos(serie, fim)}


def distancia_km(a, b):
    lat1, lat2 = radians(a["lat"]), radians(b["lat"])
    dif_lon = radians(b["lon"] - a["lon"])
    termos = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dif_lon / 2) ** 2
    return 12_742 * asin(sqrt(min(1, termos)))


def validar_chuva_estacao(modelo, estacao, referencia):
    ponto_modelo, ponto_estacao = (p.metadados["ponto"] for p in (modelo, estacao))
    distancia = distancia_km(ponto_modelo, ponto_estacao)
    altitudes = [p.get("altitude_m") for p in (ponto_modelo, ponto_estacao)]
    diferenca_altitude = abs(altitudes[0] - altitudes[1]) if None not in altitudes else None
    metadados = {"distancia_km": round(distancia, 1), "diferenca_altitude_m": diferenca_altitude,
                 "fonte_estacao": catalogo.fonte_da(estacao), "fonte_modelo": catalogo.fonte_da(modelo)}
    if distancia > 50 or (diferenca_altitude is not None and diferenca_altitude > 250):
        return {"status": "referencia_distante", **metadados}
    serie_modelo, serie_estacao = (p.dados["dias"] for p in (modelo, estacao))
    comum = sorted(serie_modelo.keys() & serie_estacao.keys())
    erros = [serie_modelo[d]["chuva_mm"] - serie_estacao[d]["chuva_mm"] for d in comum
             if d < referencia.isoformat() and serie_modelo[d].get("chuva_mm") is not None
             and serie_estacao[d].get("chuva_mm") is not None]
    return {"status": "disponivel" if erros else "sem_pares", "dias_pareados": len(erros),
            "vies_mm": round(sum(erros) / len(erros), 2) if erros else None,
            "erro_absoluto_medio_mm": round(sum(map(abs, erros)) / len(erros), 2) if erros else None,
            **metadados}


def contexto(sessao, dados, referencia):
    talhao = dados.get("talhao") or {}
    municipio, origem = catalogo.localizar_municipio(
        sessao, dados["lat"], dados["lon"], dados.get("municipio_ibge"), talhao.get("geometria"))
    if municipio is None:
        return {"status": origem}
    codigo = municipio.codigo
    zarc_entrada = dados.get("zarc")
    clima = catalogo.publicacoes_ativas(sessao, "clima", codigo)
    solo = catalogo.publicacoes_ativas(sessao, "mapbiomas", codigo)
    resultado = {
        "status": "disponivel",
        "municipio": {"codigo": codigo, "nome": municipio.nome, "uf": municipio.uf, "origem": origem,
                      "versao_malha": municipio.malha_versao},
        "pam": producao(sessao, codigo, dados["cultura"]),
        "zarc": (consulta_zarc(sessao, codigo, dados["cultura"], zarc_entrada["safra"],
                              zarc_entrada["regra"], dados["irrigacao"])
                 if zarc_entrada else {"status": "consulta_incompleta"}),
        "clima": [resumir_clima(p, referencia) for p in clima],
        "solo": [{"fonte": catalogo.fonte_da(p), **p.dados} for p in solo],
        "balanco_hidrico": {"status": "parametros_ausentes"},
        "validacao_estacoes": [],
    }
    modelo = next((p for p in clima if p.metadados["recorte"] == RECORTE_ARQUIVO), None)
    if modelo:
        resultado["validacao_estacoes"] = [
            validar_chuva_estacao(modelo, estacao, referencia) for estacao in clima
            if estacao.metadados["recorte"].startswith("inmet-")]
    parametros = dados.get("hidrico")
    if parametros:
        if not modelo:
            resultado["balanco_hidrico"] = {"status": "fonte_et0_ausente"}
        else:
            fim = date.fromisoformat(parametros["fim"])
            inicio = fim - timedelta(days=6)
            if fim >= referencia or inicio < date.fromisoformat(dados["data_plantio"]):
                resultado["balanco_hidrico"] = {"status": "janela_fora_do_cultivo"}
            else:
                resultado["balanco_hidrico"] = {
                    **balanco_hidrico(modelo.dados["dias"], inicio, fim, parametros), "fonte": catalogo.fonte_da(modelo),
                    "distancia_modelo_km": round(distancia_km(dados, modelo.metadados["ponto"]), 1),
                }
    return resultado
