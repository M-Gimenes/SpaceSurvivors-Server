# SpaceSurvivors-Server

Backend do jogo Space Survivors: ranking de jogadores, entrega de atualizações e
assinatura RSA das respostas. Hospedado no PythonAnywhere.

## Estrutura

```
├── wsgi.py                  # ponto de entrada WSGI
├── requirements.txt
├── .env.example             # modelo de configuração (copie para .env)
├── app/
│   ├── __init__.py          # application factory
│   ├── config.py            # config via variáveis de ambiente
│   ├── models.py            # modelo Rank (tabela `ranking`)
│   ├── routes.py            # rotas HTTP
│   └── services/
│       ├── crypto.py        # chave de API e assinatura RSA
│       └── ranking.py       # regras do ranking e acesso ao banco
├── instance/                # SEGREDOS — fora do git
│   ├── key_master           # chave Fernet
│   └── private_key          # chave privada RSA (PEM)
└── builds/                  # binário do jogo — fora do git
    └── Space Survivors.exe
```

## Configuração local

```bash
python -m venv .venv
.venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # preencha com as credenciais reais
python wsgi.py
```

Os arquivos `instance/key_master` e `instance/private_key` não estão no
repositório. Copie-os do servidor ou gere novos (ver "Rotação de chaves").

## API

Todas as rotas de dados exigem o header `key-API`, obtido cifrado em
`/get_encrypted_key` e decifrado pelo cliente com a chave Fernet embutida.

| Rota                   | Método  | Descrição                               |
| ---------------------- | -------- | ----------------------------------------- |
| `/get_encrypted_key` | GET      | Devolve a chave de API cifrada com Fernet |
| `/download_update`   | GET      | Baixa o executável mais recente do jogo  |
| `/access_data`       | GET/POST | Roteia por header`action` (abaixo)      |

Valores de `action` em `/access_data`:

| action             | Descrição                                    |
| ------------------ | ---------------------------------------------- |
| `get_data`       | Ranking completo, ordenado por score           |
| `set_data`       | Envia`{nickname, score}` no corpo JSON       |
| `get_signature`  | Assina o corpo da requisição com a chave RSA |
| `get_public_key` | Devolve a chave pública em PEM                |
| `get_version`    | Versão atual do jogo                          |

Códigos de retorno de `set_data`: `0` atualizado, `1` aceito, `2` nickname em
uso, `3` entrada inválida. **O executável distribuído depende desses valores** —
não altere sem publicar um novo cliente.

## Deploy no PythonAnywhere

1. Aponte o WSGI configuration file para `wsgi.py` (variável `application`).
2. Envie `instance/key_master`, `instance/private_key` e o `.env` manualmente —
   eles não vêm pelo git.
3. Coloque o build do jogo em `builds/Space Survivors.exe`.
4. Mantenha `FLASK_DEBUG=0`.

## Rotação de chaves

```python
# Fernet (instance/key_master)
from cryptography.fernet import Fernet
open('instance/key_master','wb').write(Fernet.generate_key())
```

```bash
# RSA (instance/private_key)
openssl genrsa -out instance/private_key 2048
```

Trocar qualquer uma das duas exige republicar o cliente do jogo, que embute a
chave Fernet e valida assinaturas com a chave pública correspondente.
