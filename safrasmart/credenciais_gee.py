"""Credenciais Earth Engine por JSON no .env ou arquivo, sem expor segredos."""
import json
import os
from pathlib import Path

from .config import ROOT


def gee_configurado():
    return bool(os.getenv("GEE_SERVICE_ACCOUNT_JSON", "").strip() or os.getenv("GEE_KEY_PATH", "").strip())


def carregar_dados_gee(caminho_chave=None):
    """Um caminho explícito tem prioridade; no ambiente, JSON vem antes do arquivo."""
    texto = None if caminho_chave else os.getenv("GEE_SERVICE_ACCOUNT_JSON", "").strip()
    if not texto:
        caminho = caminho_chave or os.getenv("GEE_KEY_PATH", "").strip()
        if not caminho:
            raise RuntimeError("Configure GEE_SERVICE_ACCOUNT_JSON ou GEE_KEY_PATH no .env.")
        try:
            caminho = Path(caminho).expanduser()
            if not caminho.is_absolute():
                caminho = ROOT / caminho
            texto = caminho.read_text(encoding="utf-8-sig")
        except (OSError, ValueError):
            raise RuntimeError("Não foi possível ler o arquivo definido em GEE_KEY_PATH.") from None
    try:
        dados = json.loads(texto)
    except (ValueError, TypeError):
        raise RuntimeError("Credencial GEE inválida: cole o JSON completo da conta de serviço, não uma chave de API.") from None
    if not isinstance(dados, dict) or dados.get("type") != "service_account":
        raise RuntimeError("O JSON GEE deve ser uma credencial do tipo service_account.")
    for campo in ("client_email", "private_key", "token_uri"):
        if not isinstance(dados.get(campo), str) or not dados[campo].strip():
            raise RuntimeError(f"O JSON GEE precisa conter o campo {campo}.")
    return dados
