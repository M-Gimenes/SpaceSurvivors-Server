"""Rotas HTTP da API. Os caminhos e formatos de resposta são consumidos pelo
executável do jogo já distribuído — não altere sem publicar um novo cliente."""
from flask import Blueprint, current_app, jsonify, request, send_file

bp = Blueprint('api', __name__)


@bp.route('/get_encrypted_key', methods=['GET'])
def get_encrypted_key():
    return jsonify({'key': current_app.crypto.encrypted_key})


@bp.route('/download_update')
def download_update():
    return send_file(current_app.config['BUILD_PATH'], as_attachment=True)


@bp.route('/access_data', methods=['GET', 'POST'])
def access_data():
    key_player = request.headers.get('key-API', '0')
    if key_player != current_app.crypto.key:
        return jsonify({'error': 'Invalid key-API'}), 401

    action = request.headers.get('action')

    if action == 'get_data':
        return jsonify({'data': current_app.ranking.get_all_data()})

    if action == 'set_data':
        result = current_app.ranking.process_player_input(request.get_json(silent=True) or {})
        return jsonify({'result': result})

    if action == 'get_signature':
        signature = current_app.crypto.get_signature(request.data)
        if signature is None:
            return jsonify({'error': 'Could not sign data'}), 500
        return signature

    if action == 'get_public_key':
        public_key = current_app.crypto.get_public_key()
        if public_key is None:
            return jsonify({'error': 'Could not load public key'}), 500
        return public_key

    if action == 'get_version':
        return jsonify({'version': current_app.config['VERSION']})

    return jsonify({'error': 'Unknown action'}), 400
