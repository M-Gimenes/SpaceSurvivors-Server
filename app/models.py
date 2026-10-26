"""Modelos do banco de dados."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Rank(db.Model):

    __tablename__ = 'ranking'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nickname = db.Column(db.String(12), unique=True, nullable=False)
    # Melhor tempo sobrevivido, em segundos. Só o servidor altera.
    score = db.Column(db.Integer, nullable=False)
    # SHA-256 do token do jogador. NULL = nick da 1.0.0 ainda não reivindicado.
    token_hash = db.Column(db.String(64), nullable=True)
    # Início da partida em andamento, no relógio do servidor (UTC). NULL = nenhuma.
    run_started_at = db.Column(db.DateTime, nullable=True)
