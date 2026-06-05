from flask import Flask, render_template, request, jsonify
from analisar import analisar
from datetime import datetime
import socket
import webbrowser
import os

app = Flask(__name__)


@app.route("/")
def index():
    """
    ROTA PRINCIPAL — serve a pagina web PWA do SafraSmart.
    
    PARAMETROS: nenhum (rota GET /).
    
    RETORNA: template HTML renderizado (api/templates/index.html).
    
    MOTIVO:
    Ponto de entrada para acesso via navegador. A pagina e um aplicativo
    web progressivo (PWA) com suporte offline, GPS e formulario completo.
    """
    return render_template("index.html")


@app.route("/api/analisar", methods=["POST"])
def api_analisar():
    """
    ROTA DA API — executa a analise completa e retorna JSON.
    
    PARAMETROS (via JSON no body da requisicao POST):
        lat (float): latitude da propriedade.
        lon (float): longitude da propriedade.
        cultura (str): "soja" ou "milho".
        data_plantio (str): data no formato YYYY-MM-DD.
        solo (str): tipo de solo ("argiloso", "misto", "arenoso").
        irrigacao (str): tipo de irrigacao ("sequeiro", "aspersao", "gotejo").
        prod_ant (float, opcional): produtividade anterior em sc/ha.
        observacoes (str, opcional): texto livre do agricultor.
    
    RETORNA: JSON — o dicionario completo de resultado da analisar().
        Em caso de erro, retorna {"erro": "mensagem"} com status 400.
    
    MOTIVO:
    Rota usada pelo frontend PWA para enviar os dados do formulario e
    receber os resultados da analise. Tambem pode ser consumida por
    ferramentas externas (Postman, curl, etc.).
    """
    dados = request.json
    try:
        data_plantio = datetime.strptime(dados["data_plantio"], "%Y-%m-%d")
        resultado = analisar(
            lat=float(dados["lat"]),
            lon=float(dados["lon"]),
            cultura=dados["cultura"],
            data_plantio_dt=data_plantio,
            solo=dados["solo"],
            irrigacao=dados["irrigacao"],
            prod_ant=float(dados["prod_ant"]) if dados.get("prod_ant") else None,
            observacoes=dados.get("observacoes", ""),
            usar_ndvi=True
        )
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"erro": str(e)}), 400


@app.route("/api/sync", methods=["POST"])
def api_sync():
    """
    ROTA DA API — sincroniza analises pendentes do modo offline.
    
    PARAMETROS (via JSON no body):
        list[dict] — lista de dicionarios, cada um contendo os mesmos campos
        de /api/analisar, mais um campo "id" para identificacao.
    
    RETORNA: JSON — lista de resultados, cada um com:
        {"id": id_original, "status": "ok"|"erro", "resultado": dict|"erro": str}
    
    MOTIVO:
    Quando o usuario esta offline, o frontend salva as analises em
    localStorage. Quando volta a ficar online, envia todas as analises
    pendentes de uma vez para esta rota, que processa cada uma e retorna
    os resultados. Isso implementa o padrao "offline-first".
    """
    itens = request.json
    resultados = []
    for item in itens:
        try:
            dp = datetime.strptime(item["data_plantio"], "%Y-%m-%d")
            res = analisar(
                lat=float(item["lat"]),
                lon=float(item["lon"]),
                cultura=item["cultura"],
                data_plantio_dt=dp,
                solo=item["solo"],
                irrigacao=item["irrigacao"],
                prod_ant=float(item["prod_ant"]) if item.get("prod_ant") else None,
                observacoes=item.get("observacoes", ""),
                usar_ndvi=True
            )
            resultados.append({"id": item.get("id"), "status": "ok", "resultado": res})
        except Exception as e:
            resultados.append({"id": item.get("id"), "status": "erro", "erro": str(e)})
    return jsonify(resultados)


def iniciar_servidor():
    """
    INICIA o servidor web Flask na rede local.
    
    PARAMETROS: nenhum.
    
    RETORNA: None — funcao bloqueante (app.run()).
    
    FUNCIONALIDADES:
    1. Descobre o IP local da maquina na rede (via socket para 8.8.8.8:80).
    2. Imprime os endereços de acesso (localhost + rede).
    3. Abre o navegador automaticamente na pagina inicial.
    4. Inicia o servidor Flask em 0.0.0.0:5000 (acessivel na rede local).
    
    MOTIVO:
    O servidor e iniciado em 0.0.0.0 (todas as interfaces) para permitir
    acesso pelo celular na mesma rede WiFi, essencial para demonstracoes
    em campo onde o agricultor usa o celular enquanto o notebook roda
    o servidor.
    
    POR QUE socket para 8.8.8.8:80:
    Esta tecnica descobre o IP local da maquina sem depender de DNS ou
    configuracao de rede. Conecta no Google DNS (8.8.8.8:80) e verifica
    qual interface de rede foi usada.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()

    print("\n" + "=" * 50)
    print("  SAFRASMART — Servidor Web")
    print("=" * 50)
    print(f"\n  Acesse no celular (mesma WiFi):")
    print(f"  http://{ip}:5000")
    print(f"\n  Local:")
    print(f"  http://127.0.0.1:5000")
    print("\n  Pressione Ctrl+C para parar\n")

    webbrowser.open("http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    iniciar_servidor()
