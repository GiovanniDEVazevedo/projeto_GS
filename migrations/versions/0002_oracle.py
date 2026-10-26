"""JSON validado e timestamps com microssegundos no Oracle.

SQLite/PostgreSQL não mudam de armazenamento. Esta revisão também registra
o upgrade em instalações existentes, preservando seus dados e sua revisão 0001.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

COLUNAS_TEMPO = {
    "propriedades": ("criado_em",),
    "safras": ("criado_em",),
    "analises": ("disponivel_em", "lease_ate", "criado_em", "atualizado_em"),
    "cache_dados": ("expira_em",),
}
CONSTRAINTS = (
    ("analises", "entrada", "ck_analises_entrada_json"),
    ("analises", "resultado", "ck_analises_resultado_json"),
    ("cache_dados", "conteudo", "ck_cache_conteudo_json"),
)


def upgrade():
    if op.get_bind().dialect.name != "oracle":
        return
    for tabela, colunas in COLUNAS_TEMPO.items():
        for coluna in colunas:
            op.alter_column(tabela, coluna, existing_type=sa.DateTime(), type_=sa.TIMESTAMP())
    for tabela, coluna, nome in CONSTRAINTS:
        op.create_check_constraint(nome, tabela, f"{coluna} IS JSON")


def downgrade():
    if op.get_bind().dialect.name != "oracle":
        return
    for tabela, _, nome in reversed(CONSTRAINTS):
        op.drop_constraint(nome, tabela, type_="check")
    for tabela, colunas in COLUNAS_TEMPO.items():
        for coluna in colunas:
            op.alter_column(tabela, coluna, existing_type=sa.TIMESTAMP(), type_=sa.DateTime())
