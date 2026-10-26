"""Documentos JSON portáveis sem depender do tipo JSON nativo do Oracle 21c.

SQLAlchemy 2.0 não implementa JSON para Oracle. No Oracle, o documento fica em
CLOB com validação IS JSON. SQLite/PostgreSQL mantêm seu tipo JSON existente.
"""
import json
from decimal import Decimal

from sqlalchemy import JSON, DateTime
from sqlalchemy.dialects.oracle import CLOB, TIMESTAMP
from sqlalchemy.types import TypeDecorator


def _numeros_json(valor):
    # python-oracledb pode retornar documentos IS JSON já decodificados,
    # incluindo Decimal. Manter números compatíveis com a API e com o cache.
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    if isinstance(valor, dict):
        return {k: _numeros_json(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_numeros_json(v) for v in valor]
    return valor


class DocumentoJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(CLOB() if dialect.name == "oracle" else JSON())

    def process_bind_param(self, valor, dialect):
        if dialect.name == "oracle" and valor is not None:
            return json.dumps(valor, ensure_ascii=False, allow_nan=False)
        return valor

    def process_result_value(self, valor, dialect):
        if dialect.name != "oracle" or valor is None:
            return valor
        if hasattr(valor, "read"):
            valor = valor.read()
        if isinstance(valor, (str, bytes, bytearray)):
            return json.loads(valor)
        return _numeros_json(valor)


def instante_db():
    # DATE do Oracle não preserva microssegundos; leases e ordenação usam TIMESTAMP.
    return DateTime().with_variant(TIMESTAMP(), "oracle")
