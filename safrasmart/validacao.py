"""Contrato da API: normalização antes de persistir ou calcular."""
import math
from datetime import date
from uuid import UUID


class EntradaInvalida(ValueError):
    pass


def numero(valor, campo, minimo, maximo):
    if isinstance(valor, bool):
        raise EntradaInvalida(f"{campo}: informe um número válido.")
    try:
        valor = float(valor)
    except (TypeError, ValueError, OverflowError):
        raise EntradaInvalida(f"{campo}: informe um número válido.") from None
    if not math.isfinite(valor) or not minimo <= valor <= maximo:
        raise EntradaInvalida(f"{campo}: valor deve estar entre {minimo} e {maximo}.")
    return valor


def validar(dados):
    if not isinstance(dados, dict):
        raise EntradaInvalida("Envie um objeto JSON.")
    try:
        identificador = str(UUID(str(dados["id"])))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise EntradaInvalida("id: informe um UUID para permitir reenvios seguros.") from None
    saida = {"id": identificador}
    saida["lat"] = numero(dados.get("lat"), "lat", -90, 90)
    saida["lon"] = numero(dados.get("lon"), "lon", -180, 180)
    for campo, opcoes in {
        "cultura": {"soja", "milho"},
        "solo": {"arenoso", "argiloso", "misto"},
        "irrigacao": {"sequeiro", "aspersao", "gotejo"},
        "origem_localizacao": {"manual", "gps", "ip", "cidade"},
    }.items():
        valor = dados.get(campo, "manual" if campo == "origem_localizacao" else None)
        if not isinstance(valor, str) or valor not in opcoes:
            raise EntradaInvalida(f"{campo}: escolha uma das opções disponíveis.")
        saida[campo] = valor
    try:
        data = dados["data_plantio"]
        if not isinstance(data, str) or len(data) != 10:
            raise ValueError
        plantio = date.fromisoformat(data)
        if not 1981 <= plantio.year <= date.today().year + 2:
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise EntradaInvalida("data_plantio: use YYYY-MM-DD, de 1981 até os próximos dois anos.") from None
    saida["data_plantio"] = plantio.isoformat()
    for campo, padrao, tamanho in [("observacoes", "", 4000), ("propriedade", "Minha propriedade", 120)]:
        valor = dados.get(campo, padrao)
        if not isinstance(valor, str) or len(valor) > tamanho:
            raise EntradaInvalida(f"{campo}: máximo de {tamanho} caracteres.")
        saida[campo] = valor.strip() or padrao
    saida["prod_ant"] = None if dados.get("prod_ant") in (None, "") else numero(dados["prod_ant"], "prod_ant", 0, 1000)
    saida["precisao_m"] = None if dados.get("precisao_m") is None else numero(dados["precisao_m"], "precisao_m", 0, 100000)
    return saida
