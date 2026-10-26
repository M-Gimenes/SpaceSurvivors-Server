"""Teste de fumaça: confere se o servidor responde como o cliente 1.0.1 espera.

Uso:
    python scripts/smoke_test.py <url_base>            só leituras e chamadas recusadas
    python scripts/smoke_test.py <url_base> --write    também cadastra um jogador de teste

Com --write é criado um jogador zzsmokeNNNNN. Apague depois:
    DELETE FROM ranking WHERE nickname LIKE 'zzsmoke%';
Só usa a biblioteca padrão, então roda em qualquer Python 3.
"""
import json
import random
import sys
import time
import urllib.error
import urllib.request

base = sys.argv[1].rstrip('/')
write = '--write' in sys.argv
ok = True


def call(method, path, body=None, partial=False):
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Content-Type': 'application/json'} if data else {}
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.headers, (r.read(1024) if partial else r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def as_json(raw):
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def check(label, cond, extra=''):
    global ok
    ok = ok and bool(cond)
    print('PASS' if cond else 'FAIL', '-', label, extra)


s, _, raw = call('GET', '/version')
check('versão', s == 200 and 'version' in as_json(raw), raw.decode(errors='replace').strip())

s, _, raw = call('GET', '/ranking')
data = as_json(raw).get('data')
check('ranking', s == 200 and isinstance(data, list), f'{len(data or [])} jogadores')

s, _, _ = call('GET', '/get_encrypted_key')
check('camada de chave antiga removida', s == 404, f'HTTP {s}')

s, _, raw = call('POST', '/register', {'nickname': 'nick inválido!'})
check('cadastro recusa nick inválido', as_json(raw) == {'result': 3})

s, _, _ = call('POST', '/run/start', {'nickname': 'Ninguem', 'token': 'chute'})
check('partida exige token válido', s == 401, f'HTTP {s}')

s, _, raw = call('POST', '/claim', {'save': 'AAAA', 'signature': 'AAAA'})
check('migração recusa save sem assinatura válida', as_json(raw).get('result') == 3 or s == 503, f'HTTP {s}')

s, hd, _ = call('GET', '/download_update', partial=True)
size = int(hd.get('Content-Length', 0) or 0)
check('download do jogo', s == 200 and size > 1_000_000, f'{size / 1e6:.1f} MB')

if write:
    nickname = f'zzsmoke{random.randint(10000, 99999)}'
    s, _, raw = call('POST', '/register', {'nickname': nickname})
    token = as_json(raw).get('token')
    check('cadastro devolve token', bool(token), nickname)
    me = {'nickname': nickname, 'token': token}

    call('POST', '/run/start', me)
    time.sleep(3)
    s, _, raw = call('POST', '/run/finish', {**me, 'score': 2})
    check('score dentro do tempo real é aceito', as_json(raw) == {'accepted': True, 'best': 2}, raw.decode().strip())

    call('POST', '/run/start', me)
    s, _, raw = call('POST', '/run/finish', {**me, 'score': 5000})
    check('score maior que o tempo real é recusado', as_json(raw) == {'accepted': False, 'best': 2}, raw.decode().strip())

    s, _, raw = call('POST', '/register', {'nickname': nickname.upper()})
    check('nick já tem dono', as_json(raw) == {'result': 2})

print('RESULTADO:', 'TUDO OK' if ok else 'TEM FALHA')
sys.exit(0 if ok else 1)
