"""Tábua de risco do MAPA, com as combinações oficiais preservadas."""

import csv
import hashlib
import io
import json
import re
from calendar import monthrange

import requests

CATALOGO = "https://dados.agricultura.gov.br/api/3/action/package_show"
CONJUNTO = "tabua-de-risco-zoneamento-agricola-de-risco-climatico"
PORTARIAS = "https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/programa-nacional-de-zoneamento-agricola-de-risco-climatico/portarias"
CICLOS = {20: "I", 21: "II", 22: "III", 24: "IV", 25: "V", 26: "VI"}
SOLOS = {1: "Arenoso (cód. 1)", 2: "Textura média (cód. 2)", 3: "Argiloso (cód. 3)",
         **{n: f"AD{n - 10}" for n in range(11, 17)}}
DECENDIOS = [f"dec{i}" for i in range(1, 37)]


def nome_safra(safra):
    if not re.fullmatch(r"20[0-9]{2}/20[0-9]{2}", safra):
        raise ValueError("Use uma safra no formato AAAA/AAAA.")
    ini, fim = map(int, safra.split("/"))
    if fim != ini + 1:
        raise ValueError("O ano final da safra deve suceder o inicial.")
    return safra


def ler_zarc(arquivo, safra, codigos):
    leitor = csv.DictReader(arquivo, delimiter=";")
    colunas = {"Nome_cultura", "SafraIni", "SafraFin", "Cod_Cultura", "Cod_Ciclo", "Cod_Solo",
               "geocodigo", "Cod_Outros_Manejos", "Nome_Outros_Manejos", "Cod_Clima", "Nome_Clima",
               "Cod_NM", "Produtividade", "Portaria", *DECENDIOS}
    if not colunas.issubset(leitor.fieldnames or []):
        raise ValueError("CSV ZARC com colunas diferentes do dicionário oficial.")
    resultado = {codigo: {} for codigo in codigos}
    for linha in leitor:
        codigo = linha["geocodigo"]
        nome = linha["Nome_cultura"].strip()
        cultura = nome.casefold().split(" ")[0]
        if codigo not in resultado or cultura not in {"milho", "soja"}:
            continue
        if f"{linha['SafraIni']}/{linha['SafraFin']}" != safra:
            raise ValueError("O CSV ZARC contém outra safra no recorte solicitado.")
        if not linha["Portaria"].strip():
            raise ValueError("Combinação ZARC sem portaria identificada.")
        decendios = [int(linha[c]) if linha[c] else None for c in DECENDIOS]
        if any(n not in {None, 0, 20, 30, 40} for n in decendios):
            raise ValueError("O ZARC retornou uma classe de risco desconhecida.")
        grupo, solo, manejo = (int(linha[c]) for c in ("Cod_Ciclo", "Cod_Solo", "Cod_Outros_Manejos"))
        regra = {"cultura": cultura, "nome": nome, "codigo_cultura": linha["Cod_Cultura"],
                 "grupo": grupo, "solo": solo, "manejo": manejo, "manejo_nome": linha["Nome_Outros_Manejos"],
                 "clima": linha["Cod_Clima"], "clima_nome": linha["Nome_Clima"],
                 "nivel_manejo": linha["Cod_NM"], "produtividade": linha["Produtividade"],
                 "portaria": linha["Portaria"], "decendios": decendios}
        identificador = hashlib.sha256(json.dumps(regra, sort_keys=True).encode()).hexdigest()[:24]
        resultado[codigo][identificador] = {"id": identificador, **regra}
    if not any(resultado.values()):
        raise ValueError("O CSV não contém combinações de soja ou milho para este recorte.")
    return {c: sorted(v.values(), key=lambda r: (r["nome"], r["grupo"], r["solo"], r["manejo"], r["id"]))
            for c, v in resultado.items()}


def baixar_zarc(safra, codigos):
    nome_safra(safra)
    resposta = requests.get(CATALOGO, params={"id": CONJUNTO}, timeout=(10, 25))
    resposta.raise_for_status()
    recursos = resposta.json()["result"]["resources"]
    recurso = next((r for r in recursos if r.get("name", "").endswith(f"Safra {safra}")
                    and r.get("format", "").casefold() == "csv"), None)
    if recurso is None or not recurso["url"].startswith("https://dados.agricultura.gov.br/"):
        raise ValueError("CSV oficial indisponível para a safra solicitada.")
    with requests.get(recurso["url"], stream=True, timeout=(10, 60)) as resposta:
        resposta.raise_for_status()
        resposta.raw.decode_content = True
        dados = ler_zarc(io.TextIOWrapper(resposta.raw, encoding="utf-8-sig"), safra, codigos)
    return dados, recurso["url"], recurso.get("last_modified") or recurso["id"]


def descricao_regra(regra):
    rotulos = [regra["nome"], f"Grupo {CICLOS.get(regra['grupo'], regra['grupo'])}",
               SOLOS.get(regra["solo"], f"Solo cód. {regra['solo']}"), regra["manejo_nome"]]
    if regra["clima"] not in {"", "0"}:
        rotulos.append(regra["clima_nome"])
    if regra["nivel_manejo"]:
        rotulos.append(f"NM{regra['nivel_manejo']}")
    if regra["produtividade"]:
        rotulos.append(regra["produtividade"])
    rotulos.append(regra["portaria"])
    return " · ".join(rotulos)


def decendio(data):
    return (data.month - 1) * 3 + min((data.day - 1) // 10, 2) + 1


def janelas(regra):
    resultado = []
    for indice, risco in enumerate(regra["decendios"]):
        if risco not in {20, 30, 40}:
            continue
        mes, parte = divmod(indice, 3)
        mes += 1
        inicio = parte * 10 + 1
        fim = inicio + 9 if parte < 2 else monthrange(2000 if mes == 2 else 2001, mes)[1]
        # O terceiro decêndio de fevereiro termina no último dia do mês.
        final = "fim de fevereiro" if mes == 2 and parte == 2 else f"{fim:02d}/{mes:02d}"
        resultado.append({"decendio": indice + 1, "inicio": f"{inicio:02d}/{mes:02d}", "fim": final, "risco_pct": risco})
    return resultado
