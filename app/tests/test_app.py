"""Testes de integração: precisam de um PostgreSQL em AIVEN_DB_URL.
No GitHub Actions, o workflow sobe um PostgreSQL de teste sozinho."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

pytestmark = pytest.mark.skipif(
    not os.environ.get("AIVEN_DB_URL"), reason="AIVEN_DB_URL não definida"
)

# uma assinatura válida para reaproveitar nos testes
ASSINATURA = {
    "servico": "Spotify",
    "categoria": "música",
    "valor_mensal": "21,90",
    "dia_cobranca": "10",
    "status": "ativa",
}


@pytest.fixture()
def client():
    import app as app_module
    import db

    db.ensure_schema()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE assinaturas RESTART IDENTITY;")
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_healthz_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_crud_completo(client):
    # criar (o valor com vírgula também vale)
    resp = client.post("/assinaturas", data=ASSINATURA)
    assert resp.status_code == 302

    # listar: confere todos os campos
    dados = client.get("/api/assinaturas").get_json()
    assert len(dados["assinaturas"]) == 1
    a = dados["assinaturas"][0]
    assert a["servico"] == "Spotify"
    assert a["categoria"] == "música"
    assert a["valor_mensal"] == "21.90"
    assert a["dia_cobranca"] == 10
    assert a["status"] == "ativa"
    assert dados["total_mensal"] == "21.90"
    assinatura_id = a["id"]
    assert client.get("/").status_code == 200
    assert client.get(f"/assinaturas/{assinatura_id}/editar").status_code == 200

    # editar
    novos = dict(ASSINATURA, servico="Spotify Duo", valor_mensal="27.90", dia_cobranca="15")
    resp = client.post(f"/assinaturas/{assinatura_id}", data=novos)
    assert resp.status_code == 302
    editada = client.get("/api/assinaturas").get_json()["assinaturas"][0]
    assert editada["servico"] == "Spotify Duo"
    assert editada["valor_mensal"] == "27.90"
    assert editada["dia_cobranca"] == 15

    # excluir
    resp = client.post(f"/assinaturas/{assinatura_id}/excluir")
    assert resp.status_code == 302
    assert client.get("/api/assinaturas").get_json()["assinaturas"] == []


def test_total_ignora_canceladas(client):
    client.post("/assinaturas", data=ASSINATURA)
    client.post("/assinaturas", data=dict(ASSINATURA, servico="Netflix", valor_mensal="39.90"))
    client.post(
        "/assinaturas",
        data=dict(ASSINATURA, servico="Antiga", valor_mensal="100", status="cancelada"),
    )
    dados = client.get("/api/assinaturas").get_json()
    assert len(dados["assinaturas"]) == 3
    assert dados["total_mensal"] == "61.80"


def test_servico_obrigatorio(client):
    resp = client.post("/assinaturas", data=dict(ASSINATURA, servico="   "))
    assert resp.status_code == 400


def test_valor_invalido(client):
    assert client.post("/assinaturas", data=dict(ASSINATURA, valor_mensal="abc")).status_code == 400
    assert client.post("/assinaturas", data=dict(ASSINATURA, valor_mensal="-5")).status_code == 400


def test_dia_e_status_invalidos(client):
    assert client.post("/assinaturas", data=dict(ASSINATURA, dia_cobranca="32")).status_code == 400
    assert client.post("/assinaturas", data=dict(ASSINATURA, dia_cobranca="x")).status_code == 400
    assert client.post("/assinaturas", data=dict(ASSINATURA, status="pausada")).status_code == 400


def test_assinatura_inexistente(client):
    assert client.get("/assinaturas/9999/editar").status_code == 404
    assert client.post("/assinaturas/9999/excluir").status_code == 404


def test_healthz_sem_banco(client, monkeypatch):
    monkeypatch.setenv("AIVEN_DB_URL", "postgres://x:y@127.0.0.1:1/nada")
    resp = client.get("/healthz")
    assert resp.status_code == 503
