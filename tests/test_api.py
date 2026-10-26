"""Testes da API 1.0.1. Rodar com: python -m pytest"""
import base64
import pickle

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from app.models import Rank, db


def register(client, nickname):
    return client.post('/register', json={'nickname': nickname}).get_json()


def start(client, nickname, token):
    return client.post('/run/start', json={'nickname': nickname, 'token': token})


def finish(client, nickname, token, score):
    return client.post('/run/finish', json={'nickname': nickname, 'token': token, 'score': score})


def sign(private_key, data):
    return private_key.sign(
        data,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )


def add_legacy_player(app, nickname, score):
    """Jogador vindo do dump da 1.0.0: sem token."""
    with app.app_context():
        db.session.add(Rank(nickname=nickname, score=score))
        db.session.commit()


# Básico

def test_version(client):
    assert client.get('/version').get_json() == {'version': '9.9.9'}


def test_old_key_endpoints_are_gone(client):
    assert client.get('/get_encrypted_key').status_code == 404
    assert client.get('/access_data').status_code == 404


def test_download_update(client):
    response = client.get('/download_update')
    assert response.status_code == 200
    assert response.data == b'MZ fake exe'


# Cadastro: o nick passa a ter dono

def test_register_returns_token(client):
    body = register(client, 'Ana')
    assert body['result'] == 1
    assert len(body['token']) >= 40


def test_register_blocks_taken_nickname_case_insensitive(client):
    register(client, 'Ana')
    assert register(client, 'ana') == {'result': 2}


def test_register_rejects_invalid_nickname(client):
    for bad in ['', 'a' * 13, 'com espaco', 'x!', None, 123]:
        assert register(client, bad) == {'result': 3}


def test_token_is_stored_hashed(app, client):
    token = register(client, 'Ana')['token']
    with app.app_context():
        stored = db.session.execute(db.select(Rank)).scalar_one().token_hash
    assert stored != token and len(stored) == 64


def test_nobody_can_touch_another_players_score(client, clock):
    token = register(client, 'Ana')['token']
    register(client, 'Bia')
    assert start(client, 'Ana', 'token-chutado').status_code == 401
    assert start(client, 'Ana', None).status_code == 401
    assert finish(client, 'Ana', 'token-chutado', 10).status_code == 401
    assert start(client, 'Ana', token).status_code == 200


# Partida: score limitado pelo tempo real

def test_score_within_real_time_is_accepted(client, clock):
    token = register(client, 'Ana')['token']
    start(client, 'Ana', token)
    clock.advance(120)
    assert finish(client, 'Ana', token, 118).get_json() == {'accepted': True, 'best': 118}
    assert client.get('/ranking').get_json()['data'][0] == {'pos': 1, 'nickname': 'Ana', 'score': 118}


def test_score_above_real_time_is_refused(app, client, clock):
    token = register(client, 'Ana')['token']
    start(client, 'Ana', token)
    clock.advance(10)
    assert finish(client, 'Ana', token, 99999).get_json() == {'accepted': False, 'best': 0}
    log = (app.config['LOG_PATH']).read_text(encoding='utf-8')
    assert 'Score recusado: Ana enviou 99999' in log


def test_tolerance_of_five_seconds(client, clock):
    token = register(client, 'Ana')['token']
    start(client, 'Ana', token)
    clock.advance(100)
    assert finish(client, 'Ana', token, 106).get_json()['accepted'] is False
    start(client, 'Ana', token)
    clock.advance(100)
    assert finish(client, 'Ana', token, 105).get_json()['accepted'] is True


def test_best_never_goes_down(client, clock):
    token = register(client, 'Ana')['token']
    start(client, 'Ana', token)
    clock.advance(300)
    finish(client, 'Ana', token, 300)
    start(client, 'Ana', token)
    clock.advance(60)
    assert finish(client, 'Ana', token, 50).get_json() == {'accepted': True, 'best': 300}


def test_finish_needs_an_open_run_and_closes_it(client, clock):
    token = register(client, 'Ana')['token']
    assert finish(client, 'Ana', token, 0).status_code == 409
    start(client, 'Ana', token)
    clock.advance(30)
    assert finish(client, 'Ana', token, 30).status_code == 200
    assert finish(client, 'Ana', token, 30).status_code == 409


def test_new_start_replaces_abandoned_run(client, clock):
    token = register(client, 'Ana')['token']
    start(client, 'Ana', token)
    clock.advance(1000)
    start(client, 'Ana', token)  # abandonou a anterior e começou outra
    clock.advance(10)
    assert finish(client, 'Ana', token, 900).get_json()['accepted'] is False


def test_score_type_and_range(client, clock):
    token = register(client, 'Ana')['token']
    for bad in ['100', 10.5, True, -1, 100000, None]:
        start(client, 'Ana', token)
        clock.advance(200000)
        assert finish(client, 'Ana', token, bad).get_json()['accepted'] is False, bad


def test_ranking_order(client, clock):
    for nickname, score in [('Ana', 50), ('Bia', 200), ('Caio', 120)]:
        token = register(client, nickname)['token']
        start(client, nickname, token)
        clock.advance(score)
        finish(client, nickname, token, score)
    names = [p['nickname'] for p in client.get('/ranking').get_json()['data']]
    assert names == ['Bia', 'Caio', 'Ana']


# Migração dos saves da 1.0.0

def claim(client, save_bytes, signature):
    return client.post('/claim', json={
        'save': base64.b64encode(save_bytes).decode(),
        'signature': base64.b64encode(signature).decode(),
    }).get_json()


def test_legacy_player_claims_nickname_with_signed_save(app, client, private_key, clock):
    add_legacy_player(app, 'Velho', 450)
    save = pickle.dumps({'nickname': 'Velho', 'score': 450, 'language': 'pt_BR'}, protocol=4)
    body = claim(client, save, sign(private_key, save))
    assert body['result'] == 1 and body['nickname'] == 'Velho'
    token = body['token']
    start(client, 'Velho', token)
    clock.advance(20)
    assert finish(client, 'Velho', token, 20).get_json() == {'accepted': True, 'best': 450}


def test_claim_only_once(app, client, private_key):
    add_legacy_player(app, 'Velho', 450)
    save = pickle.dumps({'nickname': 'Velho', 'score': 450}, protocol=4)
    signature = sign(private_key, save)
    assert claim(client, save, signature)['result'] == 1
    assert claim(client, save, signature) == {'result': 2}


def test_unclaimed_legacy_nickname_cannot_be_registered_again(app, client):
    add_legacy_player(app, 'Velho', 450)
    assert register(client, 'velho') == {'result': 2}


def test_claim_rejects_bad_signature(app, client, private_key):
    add_legacy_player(app, 'Velho', 450)
    save = pickle.dumps({'nickname': 'Velho', 'score': 450}, protocol=4)
    forged = pickle.dumps({'nickname': 'Velho', 'score': 99999}, protocol=4)
    assert claim(client, forged, sign(private_key, save)) == {'result': 3}
    assert client.post('/claim', json={'save': '%%%', 'signature': 'x'}).get_json() == {'result': 3}


def test_claim_never_executes_code_from_a_pickle(app, client, private_key, tmp_path):
    marker = tmp_path / 'pwned'

    class Evil:
        def __reduce__(self):
            return (open, (str(marker), 'w'))

    payload = pickle.dumps({'nickname': 'Velho', 'x': Evil()}, protocol=4)
    assert claim(client, payload, sign(private_key, payload)) == {'result': 3}
    assert not marker.exists()


def test_claim_creates_nickname_registered_after_the_dump(client, private_key):
    save = pickle.dumps({'nickname': 'Novato', 'score': 300}, protocol=4)
    body = claim(client, save, sign(private_key, save))
    assert body['result'] == 1 and body['nickname'] == 'Novato'
    # o score do save não é confiável (o servidor antigo assinava qualquer coisa): começa em 0
    assert client.get('/ranking').get_json()['data'] == [{'pos': 1, 'nickname': 'Novato', 'score': 0}]


def test_claim_with_invalid_nickname_in_save(client, private_key):
    save = pickle.dumps({'nickname': 'nome com espaço', 'score': 1}, protocol=4)
    assert claim(client, save, sign(private_key, save)) == {'result': 3}
