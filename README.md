# SpaceSurvivors-Server

Backend do jogo [Space Survivors](https://github.com/M-Gimenes/SpaceSurvivors): ranking de
jogadores e entrega de atualizações. Roda numa VM da Oracle Cloud (Always Free) com
nginx, gunicorn e MySQL.

## Anti-cheat

O cliente é open source, então nenhum segredo fica dentro dele. A proteção está no servidor:

1. **Nick com dono.** Ao cadastrar o nick, o jogador recebe um token secreto; o banco guarda
   só o SHA-256 dele. Sem o token ninguém inicia partida nem envia score com aquele nick.
2. **Prova de tempo.** O score é o tempo sobrevivido, em segundos. O servidor anota quando a
   partida começa (`/run/start`) e só aceita um score menor ou igual ao tempo real que passou
   até `/run/finish`, com folga de `RUN_TOLERANCE_SECONDS` (padrão 5). Scores recusados ficam
   registrados no `erros.log`.
3. **Recorde no servidor.** O melhor score só sobe, e cada partida aceita um único envio.
4. **Limite de requisições** no nginx: 30/min por IP em geral e 3/min em `/register`.

O que isso não impede: alguém que modifique o jogo (god mode, por exemplo) e deixe uma partida
rodando de verdade. Para isso seria preciso gravar e re-simular a partida no servidor.

## Estrutura

```
├── wsgi.py                     # ponto de entrada WSGI (gunicorn wsgi:application)
├── requirements.txt            # requirements-dev.txt adiciona o pytest
├── .env.example                # modelo de configuração (copie para .env)
├── app/
│   ├── __init__.py             # application factory
│   ├── config.py               # config via variáveis de ambiente
│   ├── models.py               # modelo Rank (tabela `ranking`)
│   ├── routes.py               # rotas HTTP
│   └── services/
│       ├── ranking.py          # nick com dono, partidas, recorde
│       └── legacy_save.py      # valida saves assinados da 1.0.0 (/claim)
├── migrations/                 # alterações do banco, aplicadas por deploy/migrate.sh
├── deploy/                     # setup.sh, update.sh, https.sh, migrate.sh, limite do nginx
├── scripts/smoke_test.py       # teste rápido contra um servidor rodando
├── tests/                      # testes automatizados (pytest, SQLite)
├── instance/private_key        # fora do git; só para /claim
└── builds/Space Survivors.exe  # fora do git; entregue em /download_update
```

## API

Corpo e respostas em JSON. Nicks: 1 a 12 letras ou números, únicos sem diferenciar maiúsculas.

| Rota | Método | Corpo | Resposta |
| --- | --- | --- | --- |
| `/version` | GET | | `{"version": "1.0.1"}` |
| `/ranking` | GET | | `{"data": [{"pos", "nickname", "score"}]}` |
| `/register` | POST | `{"nickname"}` | `{"result": 1, "token"}` · `2` nick em uso · `3` nick inválido |
| `/claim` | POST | `{"save", "signature"}` em base64 | `{"result": 1, "token", "nickname"}` · `2` nick já tem dono · `3` save inválido |
| `/run/start` | POST | `{"nickname", "token"}` | `{"ok": true}` · 401 token inválido |
| `/run/finish` | POST | `{"nickname", "token", "score"}` | `{"accepted", "best"}` · 401 · 409 sem partida aberta |
| `/download_update` | GET | | executável do jogo |

`/claim` existe para a migração da 1.0.0: o jogador antigo envia o save e a assinatura RSA que
tem no PC, e se o nick ainda não tiver dono recebe o token. Nick que não está no banco é
criado com score 0, porque o servidor antigo assinava qualquer conteúdo e o score do save não é confiável. O pickle só é aberto depois da
assinatura conferida, e mesmo assim sem permitir classes ou funções.

## Rodando localmente

```bash
python -m venv .venv
.venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # aponte para um MySQL
python -m pytest              # testes, não precisam de MySQL
python wsgi.py
```

## Deploy

Numa VM Ubuntu 24.04 com o repo em `/home/ubuntu/SpaceSurvivors-Server`:

```bash
bash deploy/setup.sh                      # instala tudo e roda o teste de fumaça
bash deploy/https.sh seu.dominio.com      # certificado Let's Encrypt + backup diário
bash deploy/update.sh                     # depois: git pull, migrações, restart e teste
```

Liberar as portas 80 e 443 também no firewall da nuvem (na Oracle, a Security List da VCN).
Uma versão nova do jogo vai em `builds/Space Survivors.exe` junto com `APP_VERSION` no `.env`,
seguida de `sudo systemctl restart spacesurvivors`.
