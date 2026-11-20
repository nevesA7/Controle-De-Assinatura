"""Aqui fica todo o SQL do app. Os outros arquivos só chamam estas funções."""

import os

import psycopg2
from psycopg2.extras import RealDictCursor

# Valores aceitos no campo status
STATUS_VALIDOS = ("ativa", "cancelada")

COLUNAS = "id, servico, categoria, valor_mensal, dia_cobranca, status, criado_em"

_schema_ready = False


def get_connection():
    """Abre uma conexão nova usando a URI que está na variável AIVEN_DB_URL."""
    url = os.environ.get("AIVEN_DB_URL")
    if not url:
        raise RuntimeError("AIVEN_DB_URL não configurada")
    return psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=10)


def ensure_schema():
    """Cria a tabela se ela ainda não existir (só roda uma vez por execução)."""
    global _schema_ready
    if _schema_ready:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS assinaturas (
                    id           SERIAL PRIMARY KEY,
                    servico      TEXT NOT NULL,
                    categoria    TEXT NOT NULL DEFAULT '',
                    valor_mensal NUMERIC(10, 2) NOT NULL CHECK (valor_mensal >= 0),
                    dia_cobranca INTEGER NOT NULL CHECK (dia_cobranca BETWEEN 1 AND 31),
                    status       TEXT NOT NULL DEFAULT 'ativa'
                        CHECK (status IN ('ativa', 'cancelada')),
                    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
    _schema_ready = True


def listar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            # as ativas primeiro, depois por dia de cobrança
            cur.execute(
                f"SELECT {COLUNAS} FROM assinaturas "
                "ORDER BY (status = 'cancelada'), dia_cobranca, id;"
            )
            return cur.fetchall()


def total_mensal():
    """Soma só as assinaturas ativas."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(valor_mensal), 0) AS total "
                "FROM assinaturas WHERE status = 'ativa';"
            )
            return cur.fetchone()["total"]


def buscar(assinatura_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {COLUNAS} FROM assinaturas WHERE id = %s;", (assinatura_id,))
            return cur.fetchone()


def criar(servico, categoria, valor_mensal, dia_cobranca, status):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO assinaturas (servico, categoria, valor_mensal, dia_cobranca, status)
                VALUES (%s, %s, %s, %s, %s) RETURNING id;
                """,
                (servico, categoria, valor_mensal, dia_cobranca, status),
            )
            return cur.fetchone()["id"]


def atualizar(assinatura_id, servico, categoria, valor_mensal, dia_cobranca, status):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE assinaturas
                SET servico = %s, categoria = %s, valor_mensal = %s,
                    dia_cobranca = %s, status = %s
                WHERE id = %s;
                """,
                (servico, categoria, valor_mensal, dia_cobranca, status, assinatura_id),
            )
            return cur.rowcount > 0


def excluir(assinatura_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM assinaturas WHERE id = %s;", (assinatura_id,))
            return cur.rowcount > 0


def ping():
    """Usado pelo /healthz: dá erro se o banco não responder."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
