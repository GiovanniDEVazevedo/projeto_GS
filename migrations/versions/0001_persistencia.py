"""Propriedades, safras, fila idempotente de análises e cache."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Mantém o DDL existente em SQLite/PostgreSQL. Oracle no SQLAlchemy 2.0
    # precisa de armazenamento textual; a revisão 0002 acrescenta IS JSON.
    documento = sa.JSON().with_variant(sa.CLOB(), "oracle")
    op.create_table("propriedades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dono", sa.String(64), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("lat", sa.Float, nullable=False), sa.Column("lon", sa.Float, nullable=False),
        sa.Column("precisao_m", sa.Float), sa.Column("origem_localizacao", sa.String(20), nullable=False),
        sa.Column("criado_em", sa.DateTime, nullable=False))
    op.create_index("ix_propriedades_dono", "propriedades", ["dono"])
    op.create_table("safras",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("propriedade_id", sa.String(36), sa.ForeignKey("propriedades.id"), nullable=False),
        sa.Column("cultura", sa.String(20), nullable=False), sa.Column("data_plantio", sa.Date, nullable=False),
        sa.Column("solo", sa.String(20), nullable=False), sa.Column("irrigacao", sa.String(20), nullable=False),
        sa.Column("criado_em", sa.DateTime, nullable=False))
    op.create_index("ix_safras_propriedade_id", "safras", ["propriedade_id"])
    op.create_table("analises",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("operacao_id", sa.String(36), nullable=False),
        sa.Column("dono", sa.String(64), nullable=False),
        sa.Column("safra_id", sa.String(36), sa.ForeignKey("safras.id"), nullable=False),
        sa.Column("assinatura", sa.String(64), nullable=False),
        sa.Column("entrada", documento, nullable=False), sa.Column("resultado", documento),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("erro", sa.Text),
        sa.Column("tentativas", sa.Integer, nullable=False),
        sa.Column("disponivel_em", sa.DateTime, nullable=False),
        sa.Column("lease_ate", sa.DateTime), sa.Column("lease_token", sa.String(36)),
        sa.Column("criado_em", sa.DateTime, nullable=False), sa.Column("atualizado_em", sa.DateTime, nullable=False),
        sa.Column("versao_motor", sa.String(40), nullable=False),
        sa.UniqueConstraint("dono", "operacao_id", name="uq_analise_operacao"))
    op.create_index("ix_analises_dono", "analises", ["dono"])
    op.create_index("ix_analises_safra_id", "analises", ["safra_id"])
    op.create_index("ix_analises_fila", "analises", ["status", "disponivel_em"])
    op.create_table("cache_dados", sa.Column("chave", sa.String(64), primary_key=True),
        sa.Column("conteudo", documento, nullable=False), sa.Column("expira_em", sa.DateTime, nullable=False))
    op.create_index("ix_cache_dados_expira_em", "cache_dados", ["expira_em"])


def downgrade():
    for tabela in ["cache_dados", "analises", "safras", "propriedades"]:
        op.drop_table(tabela)
