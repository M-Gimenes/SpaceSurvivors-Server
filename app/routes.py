"""Rotas HTTP da API (versão 1.0.1).

Não existe chave de API: quem identifica o jogador é o token que ele recebe ao
cadastrar o nick (/register) ou ao migrar um save da 1.0.0 (/claim).

Fluxo do cliente:
    /version                         ao abrir o jogo
    /register ou /claim              uma vez, para obter o token
    /run/start ... /run/finish       a cada partida
    /ranking                         na tela de ranking
"""
import base64
import binascii

from flask import Blueprint, current_app, jsonify, request, send_file

from app.services.ranking import RESULT_INVALID

bp = Blueprint('api', __name__)


def _body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _player(data):
    return current_app.ranking.authenticate(data.get('nickname'), data.get('token'))


@bp.get('/version')
def version():
    return jsonify(version=current_app.config['VERSION'])


@bp.get('/ranking')
def ranking():
    return jsonify(data=current_app.ranking.get_all_data())


@bp.post('/register')
def register():
    result, token = current_app.ranking.register(_body().get('nickname'))
    body = {'result': result}
    if token:
        body['token'] = token
    return jsonify(body)


@bp.post('/claim')
def claim():
    if not current_app.legacy_saves.enabled:
        return jsonify(error='Migração de saves desativada neste servidor'), 503
    data = _body()
    try:
        save = base64.b64decode(data.get('save', ''), validate=True)
        signature = base64.b64decode(data.get('signature', ''), validate=True)
    except (binascii.Error, TypeError, ValueError):
        return jsonify(result=RESULT_INVALID)
    content = current_app.legacy_saves.read(save, signature)
    if content is None:
        return jsonify(result=RESULT_INVALID)
    result, token, nickname = current_app.ranking.claim(content.get('nickname'))
    body = {'result': result}
    if token:
        body.update(token=token, nickname=nickname)
    return jsonify(body)


@bp.post('/run/start')
def run_start():
    player = _player(_body())
    if player is None:
        return jsonify(error='Nick ou token inválido'), 401
    current_app.ranking.start_run(player)
    return jsonify(ok=True)


@bp.post('/run/finish')
def run_finish():
    data = _body()
    player = _player(data)
    if player is None:
        return jsonify(error='Nick ou token inválido'), 401
    outcome = current_app.ranking.finish_run(player, data.get('score'))
    if outcome is None:
        return jsonify(error='Nenhuma partida em andamento'), 409
    accepted, best = outcome
    return jsonify(accepted=accepted, best=best)


@bp.get('/download_update')
def download_update():
    return send_file(current_app.config['BUILD_PATH'], as_attachment=True)
