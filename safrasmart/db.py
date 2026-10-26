"""Modelos portáveis SQLite/PostgreSQL. Criar tabelas somente por migrações."""
import argparse
from datetime import datetime, timezone

from sqlalchemy import (JSON, Date, DateTime, Float, ForeignKey, Index, Integer,
                        String, Text, UniqueConstraint, create_engine, event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import ROOT, database_url


def agora():
    # UTC sem timezone no armazenamento, para comparação idêntica nos dois bancos.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Propriedade(Base):
    __tablename__ = "propriedades"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dono: Mapped[str] = mapped_column(String(64), index=True)
    nome: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    precisao_m: Mapped[float | None] = mapped_column(Float)
    origem_localizacao: Mapped[str] = mapped_column(String(20))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Safra(Base):
    __tablename__ = "safras"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    propriedade_id: Mapped[str] = mapped_column(ForeignKey("propriedades.id"), index=True)
    cultura: Mapped[str] = mapped_column(String(20))
    data_plantio: Mapped[datetime] = mapped_column(Date)
    solo: Mapped[str] = mapped_column(String(20))
    irrigacao: Mapped[str] = mapped_column(String(20))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Analise(Base):
    # O UUID também é a chave de idempotência da operação offline.
    __tablename__ = "analises"
    __table_args__ = (
        UniqueConstraint("dono", "operacao_id", name="uq_analise_operacao"),
        Index("ix_analises_fila", "status", "disponivel_em"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operacao_id: Mapped[str] = mapped_column(String(36))
    dono: Mapped[str] = mapped_column(String(64), index=True)
    safra_id: Mapped[str] = mapped_column(ForeignKey("safras.id"), index=True)
    assinatura: Mapped[str] = mapped_column(String(64))
    entrada: Mapped[dict] = mapped_column(JSON)
    resultado: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pendente")
    erro: Mapped[str | None] = mapped_column(Text)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    disponivel_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    lease_ate: Mapped[datetime | None] = mapped_column(DateTime)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    versao_motor: Mapped[str] = mapped_column(String(40), default="2.0.0")


class CacheDado(Base):
    __tablename__ = "cache_dados"
    chave: Mapped[str] = mapped_column(String(64), primary_key=True)
    conteudo: Mapped[dict] = mapped_column(JSON)
    expira_em: Mapped[datetime] = mapped_column(DateTime, index=True)


def criar_engine(url=None):
    url = url or database_url()
    opts = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        (ROOT / "instance").mkdir(exist_ok=True)
        opts["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if ":memory:" in url:
            opts["poolclass"] = StaticPool
    engine = create_engine(url, **opts)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def configurar_sqlite(conexao, _):
            conexao.execute("PRAGMA foreign_keys=ON")
            conexao.execute("PRAGMA busy_timeout=30000")
    return engine


def sessoes(engine):
    return sessionmaker(engine, expire_on_commit=False)


def migrar(url=None, revision="head"):
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["database_url"] = url or database_url()
    command.upgrade(cfg, revision)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("comando", choices=["upgrade"])
    parser.parse_args()
    migrar()
    print("Banco atualizado.")
