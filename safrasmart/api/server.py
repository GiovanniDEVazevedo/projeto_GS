"""API de persistência e consulta. O worker executa as análises fora do HTTP."""
import hashlib
import logging
import os
import re
import time
from uuid import UUID

from flask import Flask, g, jsonify, render_template, request, send_from_directory
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from safrasmart.db import Analise, criar_engine
from safrasmart.repositorio import Conflito, Repositorio
from safrasmart.validacao import EntradaInvalida, validar

log = logging.getLogger(__name__)


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=256 * 1024)
    if config:
        app.config.update(config)
    repo = Repositorio(criar_engine(app.config.get("DATABASE_URL")))
    app.extensions["repo"] = repo

    @app.before_request
    def autenticar():
        g.inicio = time.monotonic()
        if request.path.startswith("/api/") and request.path != "/api/health":
            # Credencial aleatória por dispositivo; o servidor só armazena o hash.
            # Não representa uma conta pessoal. Não aceitar identidade no body.
            header = request.headers.get("Authorization", "")
            if not re.fullmatch(r"Bearer [0-9a-f]{64}", header):
                return jsonify(erro="Credencial do dispositivo ausente ou inválida."), 401
            g.dono = hashlib.sha256(header[7:].encode()).hexdigest()

    @app.after_request
    def cabecalhos(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' https://nominatim.openstreetmap.org https://ipinfo.io; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        log.info("http method=%s endpoint=%s status=%s duracao_ms=%.1f", request.method,
                 request.endpoint, response.status_code, (time.monotonic() - g.get("inicio", time.monotonic())) * 1000)
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(erro=error.description), error.code

    @app.errorhandler(EntradaInvalida)
    def entrada_error(error):
        return jsonify(erro=str(error)), 400

    @app.errorhandler(Conflito)
    def conflito_error(error):
        return jsonify(erro=str(error)), 409

    @app.errorhandler(SQLAlchemyError)
    def banco_error(error):
        # Não registrar URL, SQL ou parâmetros (podem conter localização e texto).
        log.error("Banco indisponível: %s", type(error).__name__)
        return jsonify(erro="Banco indisponível. Os dados locais serão mantidos para reenvio."), 503

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/sw.js")
    def service_worker():
        response = send_from_directory(app.static_folder, "sw.js")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.route("/api/health")
    def health():
        with repo.session() as s:
            # Também detecta banco sem migrações, e não somente conexão aberta.
            s.execute(select(Analise.id).limit(1))
        return jsonify(status="ok", worker=repo.status_worker())

    @app.route("/api/analises", methods=["POST"])
    @app.route("/api/analisar", methods=["POST"])
    def criar_analise():
        resultado = repo.registrar(g.dono, validar(request.get_json()))
        return jsonify(resultado), 200 if resultado["status"] == "ok" else 202

    @app.route("/api/sync", methods=["POST"])
    def sincronizar():
        itens = request.get_json()
        if not isinstance(itens, list) or not 1 <= len(itens) <= 50:
            raise EntradaInvalida("Envie uma lista com 1 a 50 operações.")
        resultados = []
        for item in itens:
            try:
                resultados.append(repo.registrar(g.dono, validar(item)))
            except (EntradaInvalida, Conflito) as error:
                resultados.append({"id": item.get("id") if isinstance(item, dict) else None,
                    "status": "conflito" if isinstance(error, Conflito) else "invalido",
                    "persistido": False, "erro": str(error)})
        return jsonify(resultados)

    @app.route("/api/analises/<operacao_id>")
    def consultar_analise(operacao_id):
        try:
            operacao_id = str(UUID(operacao_id))
        except ValueError:
            raise EntradaInvalida("Identificador inválido.") from None
        item = repo.obter(g.dono, operacao_id)
        if item is None:
            return jsonify(erro="Análise não encontrada."), 404
        return jsonify(item)

    @app.route("/api/analises")
    def historico():
        try:
            pagina = max(1, int(request.args.get("pagina", 1)))
        except ValueError:
            raise EntradaInvalida("Página inválida.") from None
        return jsonify(repo.listar(g.dono, pagina=pagina))

    @app.route("/api/propriedades")
    def propriedades():
        return jsonify(repo.propriedades(g.dono))

    @app.route("/api/safras")
    def safras():
        return jsonify(repo.safras(g.dono))

    return app


app = create_app()


def iniciar_servidor():
    from safrasmart.runtime import worker_local
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    print(f"SafraSmart: http://{host}:{port}")
    with worker_local(app):
        app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    iniciar_servidor()
