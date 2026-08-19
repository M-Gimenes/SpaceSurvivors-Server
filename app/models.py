"""Modelos do banco de dados."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Rank(db.Model):

    __tablename__ = 'ranking'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nickname = db.Column(db.String(12), unique=True, nullable=False)
    score = db.Column(db.Integer, nullable=False)
