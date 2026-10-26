"""Configuração compartilhada pela API, migrações e worker."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def database_url(url=None):
    """Uma única configuração para API, migrações e subprocessos do worker.

    URL.create preserva senhas com @, /, %, #, etc. sem interpolar uma URL.
    DATABASE_URL explícita tem precedência sobre as variáveis ORACLE_*.
    """
    if url is None:
        url = os.getenv("DATABASE_URL")
        if not url and any(os.getenv(k) for k in ("ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_DSN")):
            campos = ("ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_DSN")
            if not all(os.getenv(k) for k in campos):
                raise ValueError("Configure ORACLE_USER, ORACLE_PASSWORD e ORACLE_DSN juntos.")
            return URL.create("oracle+oracledb", username=os.environ["ORACLE_USER"],
                              password=os.environ["ORACLE_PASSWORD"], query={"dsn": os.environ["ORACLE_DSN"]})
        if not url:
            return URL.create("sqlite", database=str(ROOT / "instance" / "safrasmart.db"))
    url = make_url(url)
    driver = {"oracle": "oracle+oracledb", "postgres": "postgresql+psycopg",
              "postgresql": "postgresql+psycopg"}.get(url.drivername, url.drivername)
    return url.set(drivername=driver)


def oracle_connect_args():
    """Thin mode; os diretórios e a senha do wallet não entram no repositório."""
    opcoes = {"tcp_connect_timeout": 10, "retry_count": 0}
    for variavel, parametro in (("ORACLE_CONFIG_DIR", "config_dir"),
                                ("ORACLE_WALLET_LOCATION", "wallet_location"),
                                ("ORACLE_WALLET_PASSWORD", "wallet_password")):
        valor = os.getenv(variavel)
        if valor:
            opcoes[parametro] = valor
    return opcoes
