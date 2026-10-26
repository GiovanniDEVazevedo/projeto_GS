"""Configuração compartilhada pela API, migrações e worker."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def database_url():
    url = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'instance' / 'safrasmart.db'}")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url
