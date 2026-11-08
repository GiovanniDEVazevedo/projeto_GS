"""Consultas somente leitura sobre as publicações regionais ativas."""

from flask import jsonify, request
from sqlalchemy import select

from ..db import Municipio
from ..validacao import EntradaInvalida, codigo_ibge, data_iso, numero, validar_opcao_zarc
from . import catalogo, perfil, zarc


def registrar_rotas(app, repo):
    def cultura():
        valor = request.args.get("cultura")
        if valor not in {"milho", "soja"}:
            raise EntradaInvalida("Selecione milho ou soja.")
        return valor

    @app.get("/api/regional/municipios")
    def municipios_regionais():
        with repo.session() as s:
            consulta = select(Municipio.codigo, Municipio.nome, Municipio.uf).order_by(Municipio.uf, Municipio.nome)
            return jsonify([dict(linha._mapping) for linha in s.execute(consulta)])

    @app.get("/api/regional/producao")
    def producao_regional():
        codigo = codigo_ibge(request.args.get("municipio"))
        with repo.session() as s:
            return jsonify(perfil.producao(s, codigo, cultura()))

    @app.get("/api/regional/zarc")
    def zarc_regional():
        safra = request.args.get("safra", "")
        regra = request.args.get("regra")
        try:
            zarc.nome_safra(safra)
        except ValueError as erro:
            raise EntradaInvalida(str(erro)) from None
        if regra:
            validar_opcao_zarc({"safra": safra, "regra": regra})
        codigo = request.args.get("municipio")
        with repo.session() as s:
            if codigo:
                codigo_ibge(codigo)
            else:
                lat = numero(request.args.get("lat"), "latitude", -90, 90)
                lon = numero(request.args.get("lon"), "longitude", -180, 180)
                municipio, status = catalogo.localizar_municipio(s, lat, lon)
                if municipio is None:
                    return jsonify(status=status, opcoes=[])
                codigo = municipio.codigo
            resultado = perfil.consulta_zarc(s, codigo, cultura(), safra, regra, request.args.get("irrigacao"))
            return jsonify(municipio=codigo, **resultado)

    @app.get("/api/regional/casos-semelhantes")
    def casos_regionais():
        codigo = codigo_ibge(request.args.get("municipio"))
        referencia = data_iso(request.args.get("referencia"), "Data de referência")
        with repo.session() as s:
            fontes = catalogo.publicacoes_ativas(s, "clima", codigo)
            return jsonify(status="disponivel" if fontes else "sem_serie",
                           tipo="anos_agroclimaticos_analogos",
                           fontes=[perfil.resumir_clima(fonte, referencia) for fonte in fontes])
