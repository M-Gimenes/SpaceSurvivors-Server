"""Application factory."""
import logging

from flask import Flask

from app.config import Config
from app.models import db
from app.routes import bp
from app.services.legacy_save import LegacySaves
from app.services.ranking import RankingService


def _setup_logging(path):
    """Grava avisos e erros do app (inclusive scores recusados) no erros.log."""
    logger = logging.getLogger('spacesurvivors')
    logger.setLevel(logging.WARNING)
    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)
            handler.close()
    handler = logging.FileHandler(path, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    _setup_logging(app.config['LOG_PATH'])

    db.init_app(app)

    app.legacy_saves = LegacySaves(app.config['PRIVATE_KEY_PATH'])
    app.ranking = RankingService(app.config['MAX_SCORE'], app.config['RUN_TOLERANCE_SECONDS'])

    app.register_blueprint(bp)

    return app
