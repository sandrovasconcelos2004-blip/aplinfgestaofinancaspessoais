"""Web Service externo de Avaliação de Saúde Financeira (porta 5001).

Comunica com a aplicação Finances4You através de:
    1. Receção de pedido POST /api/v1/avaliar (JSON: id_utilizador, data_inicio, data_fim)
    2. Consulta GET ao endpoint JSON da Finances4You (com header X-API-Key)
    3. Cálculo do Score Financeiro (0–100, Rating A–E, 4 pilares + recomendações)
    4. Devolução de documento XML validado contra schemas/avaliacao_financeira.xsd
"""

import json
import os
from datetime import datetime
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request

from scoring import calcular_avaliacao
from xml_builder import ErroValidacaoXML, gerar_xml_avaliacao


load_dotenv()

app = Flask(__name__)

FINANCES4YOU_API_URL = os.environ.get(
    "FINANCES4YOU_API_URL",
    "http://127.0.0.1:5000/api/v1/transacoes",
)
API_KEY_INTEROP = os.environ.get("API_KEY_INTEROP", "")


def _obter_transacoes_finances4you(id_utilizador, data_inicio, data_fim):
    """Faz GET ao endpoint JSON da Finances4You para recolher os dados do utilizador."""
    query = urllib_parse.urlencode(
        {
            "id_utilizador": id_utilizador,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        }
    )
    url = f"{FINANCES4YOU_API_URL}?{query}"
    pedido = urllib_request.Request(
        url,
        headers={
            "X-API-Key": API_KEY_INTEROP,
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib_request.urlopen(pedido, timeout=10) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


@app.route("/health", methods=["GET"])
def health():
    """Verificação rápida de estado do serviço."""
    return jsonify({"estado": "ok", "servico": "app_scorefinancas"}), 200


@app.route("/api/v1/avaliar", methods=["POST"])
def avaliar():
    """Recebe o pedido da Finances4You, recolhe o JSON, calcula o score e devolve XML validado."""
    chave_recebida = request.headers.get("X-API-Key", "")
    if not API_KEY_INTEROP or chave_recebida != API_KEY_INTEROP:
        return jsonify({"erro": "Chave de API inválida ou em falta."}), 401

    payload = request.get_json(silent=True) or {}
    id_utilizador = payload.get("id_utilizador")
    data_inicio = str(payload.get("data_inicio", "")).strip()
    data_fim = str(payload.get("data_fim", "")).strip()

    if not isinstance(id_utilizador, int) or id_utilizador <= 0:
        return jsonify({"erro": "Campo 'id_utilizador' inválido ou em falta."}), 400

    try:
        dt_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"erro": "Datas inválidas. Utilize o formato YYYY-MM-DD."}), 400

    if dt_fim < dt_inicio:
        return jsonify({"erro": "'data_fim' tem de ser igual ou posterior a 'data_inicio'."}), 400

    try:
        dados_json = _obter_transacoes_finances4you(id_utilizador, data_inicio, data_fim)
    except urllib_error.HTTPError as erro:
        app.logger.exception("Erro HTTP ao consultar a API JSON da Finances4You.")
        return jsonify({"erro": f"Erro ao obter dados da Finances4You (HTTP {erro.code})."}), 502
    except (urllib_error.URLError, TimeoutError):
        app.logger.exception("Não foi possível contactar a API JSON da Finances4You.")
        return jsonify({"erro": "Não foi possível contactar a Finances4You."}), 502

    avaliacao = calcular_avaliacao(dados_json)

    try:
        xml_bytes = gerar_xml_avaliacao(dados_json, avaliacao)
    except ErroValidacaoXML:
        app.logger.exception("O XML de avaliação gerado falhou a validação XSD.")
        return jsonify({"erro": "Falha interna ao validar o XML de avaliação."}), 500

    return Response(
        xml_bytes,
        status=200,
        mimetype="application/xml; charset=utf-8",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
