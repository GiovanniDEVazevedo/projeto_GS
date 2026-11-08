"""Limites opcionais de talhões e publicações regionais versionadas."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "talhoes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("propriedade_id", sa.String(36), sa.ForeignKey("propriedades.id"), nullable=False),
        sa.Column("dados", sa.JSON, nullable=False),
        sa.Column("criado_em", sa.DateTime, nullable=False),
    )
    op.create_index("ix_talhoes_propriedade_id", "talhoes", ["propriedade_id"])
    op.create_table(
        "safras_talhoes",
        sa.Column("safra_id", sa.String(36), sa.ForeignKey("safras.id"), primary_key=True),
        sa.Column("talhao_id", sa.String(36), sa.ForeignKey("talhoes.id"), nullable=False),
    )
    op.create_index("ix_safras_talhoes_talhao_id", "safras_talhoes", ["talhao_id"])
    op.create_table(
        "municipios",
        sa.Column("codigo", sa.String(7), primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("uf", sa.String(2), nullable=False),
        sa.Column("geometria", sa.JSON),
        sa.Column("malha_versao", sa.String(60)),
    )
    op.create_table(
        "importacoes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("chave", sa.String(120), nullable=False),
        sa.Column("metadados", sa.JSON, nullable=False),
        sa.Column("dados", sa.JSON, nullable=False),
        sa.Column("criado_em", sa.DateTime, nullable=False),
    )
    op.create_index("ix_importacoes_chave", "importacoes", ["chave"])
    op.create_table(
        "fontes_dados",
        sa.Column("chave", sa.String(120), primary_key=True),
        sa.Column("importacao_id", sa.String(64), sa.ForeignKey("importacoes.id"), nullable=False),
    )


def downgrade():
    op.drop_table("fontes_dados")
    op.drop_table("importacoes")
    op.drop_table("municipios")
    op.drop_table("safras_talhoes")
    op.drop_table("talhoes")
