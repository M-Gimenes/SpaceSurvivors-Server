"""Fixtures dos testes: app com SQLite temporário, par de chaves RSA e relógio controlável."""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# config.py exige estas variáveis na importação; nos testes o banco é SQLite.
for name in ('DB_USERNAME', 'DB_PASSWORD', 'DB_HOSTNAME', 'DB_NAME'):
    os.environ.setdefault(name, 'test')

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.models import db  # noqa: E402
import app.services.ranking as ranking_module  # noqa: E402


@pytest.fixture
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def app(tmp_path, private_key):
    key_path = tmp_path / 'private_key'
    key_path.write_bytes(private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    build = tmp_path / 'game.exe'
    build.write_bytes(b'MZ fake exe')

    class TestConfig(Config):
        TESTING = True
        VERSION = '9.9.9'
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
        SQLALCHEMY_ENGINE_OPTIONS = {}
        PRIVATE_KEY_PATH = key_path
        BUILD_PATH = build
        LOG_PATH = tmp_path / 'test.log'

    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 26, 12, 0, 0)

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(ranking_module, '_now', lambda: c.now)
    return c
