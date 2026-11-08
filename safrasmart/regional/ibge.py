"""Malha municipal IBGE e séries PAM no formato JSON da API SIDRA."""

from io import BytesIO
from decimal import Decimal, InvalidOperation
from zipfile import ZipFile

import requests
import shapefile

from ..validacao import codigo_ibge

SIDRA = "https://apisidra.ibge.gov.br/values"
MALHAS = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais"
UFS = dict(zip(
    "11 12 13 14 15 16 17 21 22 23 24 25 26 27 28 29 31 32 33 35 41 42 43 50 51 52 53".split(),
    "RO AC AM RR PA AP TO MA PI CE RN PB PE AL SE BA MG ES RJ SP PR SC RS MS MT GO DF".split(),
))
CULTURAS = {"2711": "milho", "2713": "soja"}
VARIAVEIS = {"109": "area_plantada", "216": "area_colhida", "214": "producao", "112": "rendimento"}
UNIDADES = {"109": "Hectares", "216": "Hectares", "214": "Toneladas", "112": "Quilogramas por Hectare"}
SAFRAS_MILHO = {"114253": "primeira_safra", "114254": "segunda_safra"}


def url_pam(codigos, anos, tabela):
    local = ",".join(codigo_ibge(c) for c in codigos)
    periodos = ",".join(str(a) for a in anos)
    if tabela == "1612":
        return f"{SIDRA}/t/1612/n6/{local}/v/109,216,214,112/p/{periodos}/c81/2711,2713"
    if tabela == "839":
        return f"{SIDRA}/t/839/n6/{local}/v/109,216,214,112/p/{periodos}/c81/114253,114254"
    raise ValueError("Tabela PAM fora do escopo.")


def ler_pam(resposta, tabela, codigos):
    if not isinstance(resposta, list) or len(resposta) < 2 or resposta[0].get("V") != "Valor":
        raise ValueError("A resposta SIDRA não contém a tabela esperada.")
    por_municipio = {c: {} for c in codigos}
    for linha in resposta[1:]:
        codigo = linha["D1C"]
        variavel = VARIAVEIS.get(linha["D2C"])
        if codigo not in por_municipio or not variavel:
            raise ValueError("O SIDRA retornou município ou variável fora do recorte.")
        if linha["MN"] != UNIDADES[linha["D2C"]]:
            raise ValueError("A unidade PAM retornada pelo SIDRA mudou.")
        if tabela == "1612":
            cultura = CULTURAS.get(linha["D4C"])
            recorte = "total_anual"
            if cultura is None:
                raise ValueError("O SIDRA retornou uma cultura fora do recorte.")
        else:
            cultura = "milho"
            recorte = SAFRAS_MILHO.get(linha["D4C"])
            if recorte is None:
                raise ValueError("O SIDRA retornou um recorte de milho inesperado.")
        ano = int(linha["D3C"])
        agrupamento = por_municipio[codigo]
        registro = agrupamento.setdefault((cultura, recorte, ano), {
            "cultura": cultura, "recorte": recorte, "ano": ano, "tabela": tabela, "medidas": {},
        })
        original = linha["V"]
        if variavel in registro["medidas"]:
            raise ValueError("O SIDRA retornou medidas duplicadas.")
        try:
            valor = Decimal(original)
        except InvalidOperation:
            valor = None
        if valor is not None and (not valor.is_finite() or not 0 <= valor <= 10**14):
            raise ValueError("O SIDRA retornou uma medida fora da faixa.")
        registro["medidas"][variavel] = {"valor": float(valor) if valor is not None else None,
                                        "original": original, "unidade": linha["MN"]}
    return {codigo: [registros[chave] for chave in sorted(registros)]
            for codigo, registros in por_municipio.items()}


def baixar_pam(codigos, anos, tabela):
    url = url_pam(codigos, anos, tabela)
    resposta = requests.get(url, timeout=(10, 35))
    resposta.raise_for_status()
    return ler_pam(resposta.json(), tabela, codigos), url


def url_malha(uf, ano):
    return f"{MALHAS}/municipio_{ano}/UFs/{uf}/{uf}_Municipios_{ano}.zip"


def ler_malha(arquivo, codigos):
    with ZipFile(arquivo) as zipado:
        nomes = {nome.rsplit(".", 1)[-1].lower(): nome for nome in zipado.namelist() if "." in nome}
        prj = zipado.read(nomes["prj"]).decode("ascii", errors="replace").upper()
        if "GEOGCS" not in prj or "SIRGAS" not in prj or "DEGREE" not in prj:
            raise ValueError("A malha precisa usar coordenadas geográficas SIRGAS 2000.")
        codificacao = zipado.read(nomes["cpg"]).decode("ascii").strip() if "cpg" in nomes else "latin-1"
        codificacao = "cp1252" if codificacao == "1252" else codificacao
        with shapefile.Reader(shp=BytesIO(zipado.read(nomes["shp"])),
                              dbf=BytesIO(zipado.read(nomes["dbf"])), encoding=codificacao) as leitor:
            for item in leitor.iterShapeRecords():
                dados = item.record.as_dict()
                codigo = str(dados["CD_MUN"])
                if codigo in codigos:
                    yield codigo, dados["NM_MUN"], dados["SIGLA_UF"], item.shape.__geo_interface__


def baixar_malhas(codigos, ano):
    selecionados = set(codigo_ibge(c) for c in codigos)
    encontrados = {}
    for uf in sorted({UFS[c[:2]] for c in selecionados}):
        url = url_malha(uf, ano)
        resposta = requests.get(url, timeout=(10, 60))
        resposta.raise_for_status()
        for codigo, nome, sigla, geo in ler_malha(BytesIO(resposta.content), selecionados):
            encontrados[codigo] = (nome, sigla, geo, url)
    if set(encontrados) != selecionados:
        raise ValueError("A malha IBGE não contém todos os municípios solicitados.")
    return encontrados
