"""Contrato da API: normalização antes de persistir ou calcular."""
import math
import re
from datetime import date, timedelta
from uuid import UUID

from .geometria import poligono_talhao

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


def codigo_ibge(valor):
    if not isinstance(valor, str) or not re.fullmatch(r"[0-9]{7}", valor):
        raise EntradaInvalida("Informe o código IBGE do município com 7 dígitos.")
    return valor


def validar_talhao(talhao):
    try:
        if not isinstance(talhao, dict):
            raise ValueError("Informe o talhão como um objeto.")
        nome = talhao.get("nome")
        if not isinstance(nome, str) or not nome.strip() or len(nome) > 120:
            raise ValueError("Informe um nome de até 120 caracteres para o talhão.")
        return {"id": str(UUID(str(talhao.get("id")))), "nome": nome.strip(),
                **poligono_talhao(talhao.get("geometria"))}
    except ValueError as erro:
        raise EntradaInvalida(f"Talhão inválido. {erro}") from None


def validar_opcao_zarc(valor):
    if not isinstance(valor, dict):
        raise EntradaInvalida("A seleção ZARC deve ser um objeto.")
    safra = valor.get("safra")
    regra = valor.get("regra")
    if not isinstance(safra, str) or not re.fullmatch(r"20[0-9]{2}/20[0-9]{2}", safra):
        raise EntradaInvalida("Informe a safra ZARC no formato AAAA/AAAA.")
    inicio, fim = map(int, safra.split("/"))
    if fim != inicio + 1 or not isinstance(regra, str) or not re.fullmatch(r"[0-9a-f]{24}", regra):
        raise EntradaInvalida("Escolha uma combinação completa do ZARC.")
    return {"safra": safra, "regra": regra}


def data_iso(valor, campo):
    try:
        if not isinstance(valor, str) or len(valor) != 10:
            raise ValueError
        data = date.fromisoformat(valor)
        if not 1981 <= data.year <= date.today().year + 2:
            raise ValueError
        return data
    except ValueError:
        raise EntradaInvalida(f"{campo}: informe uma data válida no formato AAAA-MM-DD.") from None


def validar_hidrico(valor, irrigacao):
    if not isinstance(valor, dict):
        raise EntradaInvalida("Parâmetros do balanço hídrico inválidos.")
    fim = data_iso(valor.get("fim"), "Fim da janela hídrica")
    cad = numero(valor.get("cad_mm"), "Capacidade de armazenamento", .1, 1000)
    armazenamento = numero(valor.get("armazenamento_inicial_mm"), "Armazenamento inicial", 0, cad)
    kc = numero(valor.get("kc"), "Kc", .01, 3)
    dias = valor.get("irrigacao_diaria_mm", {})
    if not isinstance(dias, dict) or len(dias) > 7:
        raise EntradaInvalida("Informe até sete lâminas diárias de irrigação.")
    laminas = {}
    for dia, lamina in dias.items():
        data = data_iso(dia, "Data de irrigação")
        if not fim - timedelta(days=6) <= data <= fim:
            raise EntradaInvalida("A irrigação informada precisa estar na janela de sete dias.")
        laminas[data.isoformat()] = numero(lamina, "Irrigação diária em mm", 0, 500)
    if irrigacao == "sequeiro" and any(laminas.values()):
        raise EntradaInvalida("Revise o sistema de cultivo informado ou as lâminas de irrigação.")
    return {"fim": fim.isoformat(), "cad_mm": cad, "armazenamento_inicial_mm": armazenamento,
            "kc": kc, "sequeiro": irrigacao == "sequeiro", "irrigacao_diaria_mm": laminas}


def validar_laudo(valor):
    if not isinstance(valor, dict):
        raise EntradaInvalida("Registro de laudo inválido.")
    data = data_iso(valor.get("data"), "Data da amostra")
    if data > date.today():
        raise EntradaInvalida("Informe uma data de coleta que já ocorreu.")
    inicio = numero(valor.get("profundidade_inicio_cm"), "Profundidade inicial", 0, 200)
    fim = numero(valor.get("profundidade_fim_cm"), "Profundidade final", 0, 200)
    if fim <= inicio:
        raise EntradaInvalida("A profundidade final do laudo deve ser maior que a inicial.")
    return {"data": data.isoformat(), "profundidade_inicio_cm": inicio, "profundidade_fim_cm": fim,
            "argila_pct": numero(valor.get("argila_pct"), "Argila no laudo", 0, 100),
            "origem": "Laudo informado pelo produtor"}


def validar_vistoria(valor):
    if not isinstance(valor, dict):
        raise EntradaInvalida("Registro de vistoria inválido.")
    resultado = {}
    for campo in ("hipotese", "proximo_passo", "retorno"):
        texto = valor.get(campo, "")
        if not isinstance(texto, str) or len(texto) > 1000:
            raise EntradaInvalida("Use até 1.000 caracteres por campo da vistoria.")
        resultado[campo] = texto.strip()
    return resultado


def validar(dados):
    if not isinstance(dados, dict):
        raise EntradaInvalida("Envie um objeto JSON.")
    try:
        identificador = str(UUID(str(dados["id"])))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise EntradaInvalida("id: informe um UUID para permitir reenvios seguros.") from None
    saida = {"id": identificador}
    talhao = validar_talhao(dados["talhao"]) if dados.get("talhao") is not None else None
    ponto = talhao or dados
    saida["lat"] = numero(ponto.get("lat"), "lat", -90, 90)
    saida["lon"] = numero(ponto.get("lon"), "lon", -180, 180)
    for campo, opcoes in {
        "cultura": {"soja", "milho"},
        "solo": {"arenoso", "argiloso", "misto"},
        "irrigacao": {"sequeiro", "aspersao", "gotejo"},
        "origem_localizacao": {"manual", "gps", "ip", "cidade", "talhao"},
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
    # Campos opcionais: não alterar a assinatura de operações de clientes antigos.
    colheita = dados.get("data_colheita")
    realizada = dados.get("colheita_realizada")
    if realizada is not None and not isinstance(realizada, bool):
        raise EntradaInvalida("colheita_realizada: informe true ou false.")
    if colheita not in (None, ""):
        try:
            if not isinstance(colheita, str) or len(colheita) != 10:
                raise ValueError
            colheita = date.fromisoformat(colheita)
        except (ValueError, TypeError):
            raise EntradaInvalida("data_colheita: use uma data válida no formato YYYY-MM-DD.") from None
        if colheita < plantio:
            raise EntradaInvalida("data_colheita: não pode ser anterior ao plantio.")
        if colheita > date.today():
            raise EntradaInvalida("data_colheita: informe a data real da colheita, sem datas futuras.")
        if realizada is False:
            raise EntradaInvalida("A data de colheita foi preenchida, mas a colheita está marcada como não realizada.")
        saida.update(data_colheita=colheita.isoformat(), colheita_realizada=True)
    elif realizada is True:
        raise EntradaInvalida("data_colheita: informe quando a colheita foi realizada.")
    elif realizada is False:
        saida.update(data_colheita=None, colheita_realizada=False)
    for campo, padrao, tamanho in [("observacoes", "", 4000), ("propriedade", "Minha propriedade", 120)]:
        valor = dados.get(campo, padrao)
        if not isinstance(valor, str) or len(valor) > tamanho:
            raise EntradaInvalida(f"{campo}: máximo de {tamanho} caracteres.")
        saida[campo] = valor.strip() or padrao
    saida["prod_ant"] = None if dados.get("prod_ant") in (None, "") else numero(dados["prod_ant"], "prod_ant", 0, 1000)
    saida["precisao_m"] = None if dados.get("precisao_m") is None else numero(dados["precisao_m"], "precisao_m", 0, 100000)
    if talhao:
        saida.update(talhao=talhao, origem_localizacao="talhao", precisao_m=None)
    elif saida["origem_localizacao"] == "talhao":
        raise EntradaInvalida("Selecione um talhão para usar seu ponto de referência.")
    if dados.get("municipio_ibge") not in (None, ""):
        saida["municipio_ibge"] = codigo_ibge(dados["municipio_ibge"])
    if dados.get("zarc") is not None:
        saida["zarc"] = validar_opcao_zarc(dados["zarc"])
    if dados.get("hidrico") is not None:
        saida["hidrico"] = validar_hidrico(dados["hidrico"], saida["irrigacao"])
    if dados.get("laudo_solo") is not None:
        saida["laudo_solo"] = validar_laudo(dados["laudo_solo"])
    if dados.get("vistoria") is not None:
        saida["vistoria"] = validar_vistoria(dados["vistoria"])
    return saida
