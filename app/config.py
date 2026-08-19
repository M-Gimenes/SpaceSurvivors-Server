"""Configuração da aplicação, carregada de variáveis de ambiente."""
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Variável de ambiente obrigatória ausente: {name}. "
            f"Copie .env.example para .env e preencha os valores."
        )
    return value


class Config:
    VERSION = os.environ.get('APP_VERSION', '1.0.0')
    DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'

    INSTANCE_DIR = BASE_DIR / os.environ.get('INSTANCE_DIR', 'instance')
    KEY_MASTER_PATH = INSTANCE_DIR / 'key_master'
    PRIVATE_KEY_PATH = INSTANCE_DIR / 'private_key'

    BUILD_PATH = BASE_DIR / os.environ.get('BUILD_PATH', 'builds/Space Survivors.exe')
    LOG_PATH = BASE_DIR / os.environ.get('LOG_PATH', 'erros.log')

    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://{username}:{password}@{hostname}/{databasename}'.format(
        username=quote_plus(required('DB_USERNAME')),
        password=quote_plus(required('DB_PASSWORD')),
        hostname=required('DB_HOSTNAME'),
        databasename=required('DB_NAME'),
    )
    SQLALCHEMY_POOL_RECYCLE = 299
    SQLALCHEMY_TRACK_MODIFICATIONS = False
