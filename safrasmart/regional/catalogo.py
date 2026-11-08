"""Publicações imutáveis por fonte e recorte. A ativação é transacional."""

import hashlib
import json

from shapely.geometry import Point, shape
from sqlalchemy import select

from ..db import FonteDados, Importacao, Municipio, agora
from ..validacao import codigo_ibge


def publicar(sessao, tipo, codigo, dados, *, fonte, versao, url, licenca, recorte="", **detalhes):
    codigo_ibge(codigo)
    if not dados or not versao or not fonte:
        raise ValueError("A publicação precisa de dados, fonte e versão.")
    chave = ":".join((tipo, codigo, recorte))
    metadados = {"tipo": tipo, "municipio": codigo, "recorte": recorte, "fonte": fonte,
                 "versao": versao, "url": url, "licenca": licenca, **detalhes}
    conteudo = json.dumps([metadados, dados], ensure_ascii=False, sort_keys=True, allow_nan=False)
    identificador = hashlib.sha256(conteudo.encode("utf-8")).hexdigest()
    ativo = sessao.get(FonteDados, chave, with_for_update=True)
    if sessao.get(Importacao, identificador) is None:
        sessao.add(Importacao(id=identificador, chave=chave, metadados=metadados, dados=dados))
        sessao.flush()
    if ativo is None:
        sessao.add(FonteDados(chave=chave, importacao_id=identificador))
    else:
        ativo.importacao_id = identificador
    return identificador


def ativar(sessao, identificador):
    publicacao = sessao.get(Importacao, identificador)
    if publicacao is None:
        raise ValueError("Identificador de publicação desconhecido.")
    if publicacao.metadados["tipo"] == "malha":
        municipio = sessao.get(Municipio, publicacao.metadados["municipio"])
        dados = publicacao.dados
        if municipio is None:
            raise ValueError("O cadastro do município da malha não está disponível.")
        cadastrar_municipio(sessao, publicacao.metadados["municipio"], dados.get("nome", municipio.nome),
                            dados.get("uf", municipio.uf), dados["geometria"], "IBGE " + publicacao.metadados["versao"])
    atual = sessao.get(FonteDados, publicacao.chave, with_for_update=True)
    if atual is None:
        sessao.add(FonteDados(chave=publicacao.chave, importacao_id=identificador))
    else:
        atual.importacao_id = identificador


def fonte_da(publicacao):
    return {**publicacao.metadados, "id_publicacao": publicacao.id,
            "importado_em": publicacao.criado_em.isoformat() + "Z"}


def carregar(sessao, tipo, codigo, recorte=""):
    chave = ":".join((tipo, codigo, recorte))
    consulta = select(Importacao).join(FonteDados).where(FonteDados.chave == chave)
    return sessao.scalar(consulta)


def publicacoes_ativas(sessao, tipo, codigo):
    prefixo = f"{tipo}:{codigo}:"
    consulta = select(Importacao).join(FonteDados).where(FonteDados.chave.startswith(prefixo))
    return sessao.scalars(consulta.order_by(FonteDados.chave)).all()


def cadastrar_municipio(sessao, codigo, nome, uf, geometria=None, versao=None):
    codigo_ibge(codigo)
    if not nome or len(nome) > 120 or len(uf) != 2 or not uf.isalpha():
        raise ValueError("Nome ou UF do município inválido.")
    if geometria is not None:
        contorno = shape(geometria)
        if contorno.geom_type not in {"Polygon", "MultiPolygon"} or not contorno.is_valid or contorno.is_empty:
            raise ValueError(f"Malha inválida para o município {codigo}.")
        oeste, sul, leste, norte = contorno.bounds
        if not (-180 <= oeste <= leste <= 180 and -90 <= sul <= norte <= 90):
            raise ValueError("A malha municipal deve estar em coordenadas geográficas.")
    municipio = sessao.get(Municipio, codigo)
    if municipio is None:
        municipio = Municipio(codigo=codigo)
        sessao.add(municipio)
    municipio.nome = nome
    municipio.uf = uf.upper()
    if geometria is not None:
        municipio.geometria = geometria
        municipio.malha_versao = versao
    return municipio


def localizar_municipio(sessao, lat, lon, informado=None, geometria=None):
    alvo = shape(geometria) if geometria else Point(lon, lat)
    if informado:
        municipio = sessao.get(Municipio, informado)
        if municipio is None:
            return None, "municipio_sem_cobertura"
        if municipio.geometria and not shape(municipio.geometria).covers(alvo):
            return None, "municipio_diverge_da_area"
        return municipio, "malha_ibge" if municipio.geometria else "informado"
    municipios = sessao.scalars(select(Municipio).order_by(Municipio.codigo))
    encontrados = [m for m in municipios if m.geometria and shape(m.geometria).covers(alvo)]
    return (encontrados[0], "malha_ibge") if len(encontrados) == 1 else (None, "municipio_nao_identificado")
