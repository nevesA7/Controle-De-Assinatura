"""
Controle de assinaturas (CRUD em Flask + PostgreSQL na Aiven).

Cada assinatura tem serviço, categoria, valor mensal, dia da cobrança e status.
A tela principal mostra o total mensal das assinaturas ativas.
"""

import logging
from decimal import Decimal, InvalidOperation

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

import db

app = Flask(__name__)
app.logger.setLevel(logging.INFO)


@app.before_request
def preparar_banco():
    # o /healthz testa o banco sozinho, então fica de fora
    if request.path != "/healthz":
        db.ensure_schema()


def ler_formulario():
    """Pega os campos do formulário e confere se estão certos. Se não, erro 400."""
    servico = request.form.get("servico", "").strip()
    categoria = request.form.get("categoria", "").strip()
    status = request.form.get("status", "ativa")

    if not servico:
        abort(400, "O nome do serviço é obrigatório.")

    # aceita 29,90 e 29.90
    texto_valor = request.form.get("valor_mensal", "").strip().replace(",", ".")
    try:
        valor = Decimal(texto_valor)
    except InvalidOperation:
        abort(400, "O valor mensal precisa ser um número.")
    if not valor.is_finite() or valor < 0:
        abort(400, "O valor mensal não pode ser negativo.")
    valor = valor.quantize(Decimal("0.01"))

    try:
        dia = int(request.form.get("dia_cobranca", ""))
    except ValueError:
        abort(400, "O dia da cobrança precisa ser um número.")
    if not 1 <= dia <= 31:
        abort(400, "O dia da cobrança precisa estar entre 1 e 31.")

    if status not in db.STATUS_VALIDOS:
        abort(400, "Status inválido.")

    return servico, categoria, valor, dia, status


@app.route("/")
def index():
    return render_template(
        "index.html", assinaturas=db.listar(), total=db.total_mensal()
    )


@app.route("/assinaturas", methods=["POST"])
def criar():
    db.criar(*ler_formulario())
    return redirect(url_for("index"))


@app.route("/assinaturas/<int:assinatura_id>/editar")
def editar(assinatura_id):
    assinatura = db.buscar(assinatura_id)
    if assinatura is None:
        abort(404)
    return render_template("editar.html", a=assinatura)


@app.route("/assinaturas/<int:assinatura_id>", methods=["POST"])
def atualizar(assinatura_id):
    if not db.atualizar(assinatura_id, *ler_formulario()):
        abort(404)
    return redirect(url_for("index"))


@app.route("/assinaturas/<int:assinatura_id>/excluir", methods=["POST"])
def excluir(assinatura_id):
    if not db.excluir(assinatura_id):
        abort(404)
    return redirect(url_for("index"))


@app.route("/api/assinaturas")
def api_assinaturas():
    return jsonify(
        {
            "total_mensal": str(db.total_mensal()),
            "assinaturas": [
                {
                    "id": a["id"],
                    "servico": a["servico"],
                    "categoria": a["categoria"],
                    "valor_mensal": str(a["valor_mensal"]),
                    "dia_cobranca": a["dia_cobranca"],
                    "status": a["status"],
                }
                for a in db.listar()
            ],
        }
    )


@app.route("/healthz")
def healthz():
    """Responde 200 se o banco está ativo e 503 se não conectar."""
    try:
        db.ping()
        return jsonify({"status": "ok"}), 200
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("Health check falhou: %s", exc)
        return jsonify({"status": "erro", "detalhe": "banco indisponível"}), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
