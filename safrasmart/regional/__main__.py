"""Carrega ou reativa recortes públicos. Executar separadamente do servidor."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import requests
from shapely.geometry import Point, shape
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..clima import hoje_local
from ..db import FonteDados, Importacao, Municipio, criar_engine, migrar, sessoes
from ..validacao import codigo_ibge, numero
from . import catalogo, clima, ibge, mapbiomas, zarc


def periodo(inicio, fim):
    if inicio > fim or (fim - inicio).days > 20 * 366 or fim >= hoje_local():
        raise ValueError("Use até 20 anos de dias passados em cada recorte.")
    return inicio, fim


def ponto_valido(lat, lon):
    return {"lat": numero(lat, "latitude", -90, 90), "lon": numero(lon, "longitude", -180, 180)}


def piloto(args, sessao):
    codigos = list(dict.fromkeys(codigo_ibge(c) for c in args.municipios))
    if len(codigos) > 10 or not 1974 <= args.primeiro_ano <= args.ultimo_ano < hoje_local().year:
        raise ValueError("Informe até dez municípios e anos PAM completos.")
    if args.ultimo_ano - args.primeiro_ano > 19:
        raise ValueError("Use até 20 anos por publicação PAM.")
    anos = list(range(args.primeiro_ano, args.ultimo_ano + 1))
    safra = zarc.nome_safra(args.safra)
    print("Consultando malhas IBGE, PAM/SIDRA e ZARC/MAPA…", flush=True)
    with ThreadPoolExecutor(max_workers=4) as executor:
        malhas_future = executor.submit(ibge.baixar_malhas, codigos, args.ano_malha)
        pam_futures = {t: executor.submit(ibge.baixar_pam, codigos, anos, t) for t in ("1612", "839")}
        zarc_future = None if args.zarc_csv else executor.submit(zarc.baixar_zarc, safra, codigos)
        malhas = malhas_future.result()
        pam = {t: future.result() for t, future in pam_futures.items()}
        if zarc_future:
            tabua, url_zarc, versao_zarc = zarc_future.result()
        else:
            with args.zarc_csv.open(encoding="utf-8-sig", newline="") as arquivo:
                tabua = zarc.ler_zarc(arquivo, safra, codigos)
            url_zarc, versao_zarc = zarc.PORTARIAS, args.zarc_csv.name
    clima_dados = {}
    if not args.sem_clima:
        inicio, fim = periodo(args.clima_inicio, args.clima_fim)
        print(f"Consultando Open-Meteo ERA5 de {inicio} a {fim}…", flush=True)
        for codigo, (_, _, geometria, _) in malhas.items():
            contorno = shape(geometria)
            referencia = contorno.representative_point()
            if args.lat is not None or args.lon is not None:
                if len(codigos) != 1:
                    raise ValueError("Coordenadas manuais exigem um único município.")
                ponto = ponto_valido(args.lat, args.lon)
                referencia = Point(ponto["lon"], ponto["lat"])
                if not contorno.covers(referencia):
                    raise ValueError("O ponto climático fica fora da malha do município.")
            diaria, grade = clima.baixar_open_meteo(referencia.y, referencia.x, inicio, fim)
            clima_dados[codigo] = (diaria, grade)
    publicados = []
    with sessao.begin() as s:
        for codigo, (nome, uf, geometria, url) in malhas.items():
            catalogo.cadastrar_municipio(s, codigo, nome, uf, geometria, f"IBGE {args.ano_malha}")
            publicados.append(catalogo.publicar(s, "malha", codigo, {"geometria": geometria, "nome": nome, "uf": uf}, fonte="IBGE",
                              versao=str(args.ano_malha), url=url, licenca="Dados públicos do IBGE"))
        for codigo in codigos:
            for tabela, (lotes, url) in pam.items():
                if lotes[codigo]:
                    publicados.append(catalogo.publicar(s, "pam", codigo, {"series": lotes[codigo]},
                                      fonte="IBGE · PAM/SIDRA", versao=f"Tabela {tabela}, {anos[0]}–{anos[-1]}",
                                      url=url, licenca="Dados públicos do IBGE", recorte=tabela))
            if tabua[codigo]:
                publicados.append(catalogo.publicar(s, "zarc", codigo, {"regras": tabua[codigo]},
                                  fonte="MAPA · Tábua de risco ZARC", versao=f"{safra} · {versao_zarc}",
                                  url=url_zarc, licenca="Creative Commons Atribuição", recorte=safra))
            if codigo in clima_dados:
                diaria, ponto = clima_dados[codigo]
                publicados.append(catalogo.publicar(s, "clima", codigo, {"dias": diaria},
                                  fonte="Open-Meteo · ERA5", versao="ERA5 via Archive API v1",
                                  url=clima.ARQUIVO, licenca="CC BY 4.0", recorte=clima.RECORTE_ARQUIVO,
                                  ponto=ponto, fuso="UTC", natureza="reanálise de grade ~25 km",
                                  periodo={"inicio": min(diaria), "fim": max(diaria)}))
    print(f"{len(publicados)} publicações ativas em {len(codigos)} município(s).")


def complementar(args, sessao):
    codigo = codigo_ibge(args.municipio)
    with sessao() as s:
        if s.get(Municipio, codigo) is None:
            raise ValueError("Carregue a malha e o cadastro do município pelo comando piloto.")
    if args.comando == "inmet":
        serie, ponto = clima.ler_inmet(args.arquivo.read_bytes())
        detalhes = {"fonte": "INMET · Estação automática", "versao": args.versao, "url": clima.INMET,
                    "licenca": "Dados públicos INMET", "recorte": f"inmet-{ponto['estacao']}", "ponto": ponto,
                    "fuso": "UTC", "natureza": "observação horária agregada"}
        tipo, dados = "clima", {"dias": serie}
    elif args.comando == "chirps":
        ponto = ponto_valido(args.lat, args.lon)
        if args.arquivo:
            with args.arquivo.open(encoding="utf-8-sig", newline="") as arquivo:
                serie = clima.ler_chirps_csv(arquivo)
            periodo(date.fromisoformat(min(serie)), date.fromisoformat(max(serie)))
        else:
            if not args.inicio or not args.fim or args.edicao != "final":
                raise ValueError("Para amostragem Earth Engine, informe início, fim e edição final.")
            serie = clima.baixar_chirps_gee(ponto["lat"], ponto["lon"], *periodo(args.inicio, args.fim))
        detalhes = {"fonte": "CHIRPS v3 · RNL", "versao": f"3.0 · {args.edicao} · {args.versao}",
                    "url": clima.CHIRPS, "licenca": "Domínio público", "recorte": f"chirps-rnl-{args.edicao}",
                    "ponto": ponto, "fuso": "UTC", "natureza": "estimativa em grade 0,05°", "edicao": args.edicao}
        tipo, dados = "clima", {"dias": serie}
    else:
        ponto = ponto_valido(args.lat, args.lon)
        dados = mapbiomas.amostrar_solo(ponto["lat"], ponto["lon"], args.profundidade)
        detalhes = {"fonte": "MapBiomas Solo · Granulometria", "versao": "Coleção 3 beta · v1",
                    "url": mapbiomas.URL, "licenca": "MapBiomas · atribuição da fonte",
                    "recorte": f"{args.profundidade:02d}-{args.profundidade + 10:02d}cm",
                    "ponto": ponto, "natureza": "estimativa pontual de textura"}
        tipo = "mapbiomas"
    with sessao.begin() as s:
        if tipo == "clima":
            detalhes["periodo"] = {"inicio": min(serie), "fim": max(serie)}
        print(catalogo.publicar(s, tipo, codigo, dados, **detalhes))


def main():
    hoje = hoje_local()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banco", help="URL do banco. Usa DATABASE_URL ou SQLite local por padrão.")
    comandos = parser.add_subparsers(dest="comando", required=True)
    carregar = comandos.add_parser("piloto", help="Malha, PAM, ZARC e Open-Meteo.")
    carregar.add_argument("--municipios", nargs="+", default=["5107925"])
    carregar.add_argument("--ano-malha", type=int, default=2024)
    carregar.add_argument("--primeiro-ano", type=int, default=2020)
    carregar.add_argument("--ultimo-ano", type=int, default=2024)
    carregar.add_argument("--safra", default=f"{hoje.year}/{hoje.year + 1}")
    carregar.add_argument("--zarc-csv", type=Path)
    carregar.add_argument("--sem-clima", action="store_true")
    carregar.add_argument("--clima-inicio", type=date.fromisoformat, default=date(hoje.year - 10, 1, 1))
    carregar.add_argument("--clima-fim", type=date.fromisoformat, default=hoje - timedelta(days=7))
    carregar.add_argument("--lat", type=float)
    carregar.add_argument("--lon", type=float)
    inmet = comandos.add_parser("inmet", help="Importa o CSV horário original de uma estação.")
    inmet.add_argument("--municipio", required=True)
    inmet.add_argument("--arquivo", type=Path, required=True)
    inmet.add_argument("--versao", required=True, help="Ano ou edição do arquivo.")
    for nome in ("chirps", "mapbiomas"):
        coleta = comandos.add_parser(nome)
        coleta.add_argument("--municipio", required=True)
        coleta.add_argument("--lat", type=float, required=True)
        coleta.add_argument("--lon", type=float, required=True)
        if nome == "chirps":
            coleta.add_argument("--inicio", type=date.fromisoformat)
            coleta.add_argument("--fim", type=date.fromisoformat)
            coleta.add_argument("--arquivo", type=Path, help="Recorte CSV com data,precipitacao_mm.")
            coleta.add_argument("--edicao", choices=["preliminar", "final"], default="final")
            coleta.add_argument("--versao", required=True)
        else:
            coleta.add_argument("--profundidade", type=int, default=0)
    comandos.add_parser("listar")
    comandos.add_parser("ativar").add_argument("id")
    args = parser.parse_args()
    engine = None
    try:
        migrar(args.banco)
        engine = criar_engine(args.banco)
        sessao = sessoes(engine)
        if args.comando == "piloto":
            piloto(args, sessao)
        elif args.comando == "ativar":
            with sessao.begin() as s:
                catalogo.ativar(s, args.id)
            print("Publicação reativada.")
        elif args.comando == "listar":
            with sessao() as s:
                consulta = select(Importacao, FonteDados.importacao_id).join(
                    FonteDados, FonteDados.chave == Importacao.chave).order_by(Importacao.chave, Importacao.criado_em)
                for publicacao, ativa in s.execute(consulta):
                    status = "ativa" if publicacao.id == ativa else "anterior"
                    print(publicacao.chave, publicacao.id, status, publicacao.metadados["versao"])
        else:
            complementar(args, sessao)
    except (ValueError, OSError, KeyError, requests.RequestException) as erro:
        parser.exit(1, f"Importação interrompida. {erro}\n")
    except (RuntimeError, ImportError, SQLAlchemyError) as erro:
        parser.exit(1, f"Importação interrompida ({type(erro).__name__}). Confira a configuração da fonte e do banco.\n")
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
