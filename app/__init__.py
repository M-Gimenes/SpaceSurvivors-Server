"""Application factory."""
import logging

from flask import Flask

from app.config import Config
from app.models import db
from app.routes import bp
from app.services.crypto import CryptoService
from app.services.ranking import RankingService


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    logging.basicConfig(filename=app.config['LOG_PATH'], level=logging.ERROR)

    db.init_app(app)

    app.crypto = CryptoService(
        app.config['KEY_MASTER_PATH'],
        app.config['PRIVATE_KEY_PATH'],
    )
    app.ranking = RankingService()

    app.register_blueprint(bp)

    return app
