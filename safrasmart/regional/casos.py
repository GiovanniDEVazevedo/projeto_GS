"""Comparação privada entre safras anteriores do mesmo talhão."""

from datetime import date, datetime, time, timedelta
from math import isfinite

from sqlalchemy import select

from ..db import Analise, Safra, SafraTalhao
from ..repositorio import identificador
from .analises import ordenar_por_distancia

CAMPOS = ("chuva_mm", "temp_media_c")


def valores_climaticos(resultado):
    indices = resultado.get("indices") or {}
    valores = {"chuva_mm": indices.get("precip_total"), "temp_media_c": indices.get("temp_media_geral")}
    if not indices.get("precip_completa") or not all(type(v) in (float, int) and isfinite(v) for v in valores.values()):
        return None
    if (indices.get("cobertura_temperatura") or 0) < .8 or (indices.get("dias_esperados") or 0) < 7:
        return None
    return {**valores, "dias": indices["dias_esperados"]}


def casos_do_talhao(sessao, dono, dados, resultado):
    atual = valores_climaticos(resultado)
    referencia = resultado.get("metadata", {}).get("data_referencia")
    fase = (resultado.get("fase") or {}).get("nome")
    if not atual or not referencia or not fase:
        return {"status": "dados_insuficientes", "casos": []}
    plantio = date.fromisoformat(dados["data_plantio"])
    limite = datetime.combine(date.fromisoformat(referencia) + timedelta(days=1), time.min)
    tid = identificador("talhao", dono, dados["talhao"]["id"])
    consulta = (select(Analise).join(Safra).join(SafraTalhao, SafraTalhao.safra_id == Safra.id)
                .where(Analise.dono == dono, Analise.status == "ok", SafraTalhao.talhao_id == tid,
                       Safra.cultura == dados["cultura"], Safra.data_plantio < plantio,
                       Analise.criado_em < limite).order_by(Analise.criado_em.desc(), Analise.id).limit(100))
    anteriores = {}
    for analise in sessao.scalars(consulta):
        entrada = analise.entrada
        anterior = analise.resultado or {}
        retorno = (entrada.get("vistoria") or {}).get("retorno")
        fim = anterior.get("metadata", {}).get("data_referencia")
        if not retorno or not fim or fim >= referencia or (anterior.get("fase") or {}).get("nome") != fase:
            continue
        if any(entrada.get(campo) != dados.get(campo) for campo in ("solo", "irrigacao")):
            continue
        dia = date.fromisoformat(entrada["data_plantio"])
        distancia = abs(date(2000, dia.month, dia.day) - date(2000, plantio.month, plantio.day)).days
        if min(distancia, 366 - distancia) > 30:
            continue
        valores = valores_climaticos(anterior)
        if valores and valores["dias"] == atual["dias"]:
            anteriores.setdefault(analise.safra_id, {**valores, "fim": fim, "plantio": dia.isoformat(), "retorno": retorno})
    quantidade = len(anteriores)
    if quantidade < 3:
        return {"status": "amostra_pequena", "amostras": quantidade, "casos": []}
    return {"status": "disponivel", "amostras": quantidade,
            "casos": ordenar_por_distancia(atual, list(anteriores.values()), CAMPOS)[:3]}
