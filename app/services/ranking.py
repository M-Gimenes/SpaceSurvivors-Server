"""Regras do ranking: nick com dono, partida com prova de tempo e recorde no servidor."""
import hashlib
import hmac
import logging
import re
import secrets
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.models import Rank, db

log = logging.getLogger('spacesurvivors')

NICKNAME_RE = re.compile(r'^[a-zA-Z0-9]{1,12}$')

# Códigos devolvidos por /register e /claim.
RESULT_OK = 1
RESULT_TAKEN = 2
RESULT_INVALID = 3


def _now():
    """Relógio do servidor em UTC, sem fuso (como o MySQL guarda). Isolado para os testes."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def valid_nickname(nickname):
    return isinstance(nickname, str) and bool(NICKNAME_RE.match(nickname))


def valid_score(score, max_score):
    # bool é subclasse de int em Python: True viraria score 1.
    return isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= max_score


class RankingService():
    def __init__(self, max_score, tolerance_seconds):
        self.max_score = max_score
        self.tolerance = tolerance_seconds

    # Leitura

    def get_all_data(self):
        players = db.session.execute(
            db.select(Rank).order_by(Rank.score.desc(), Rank.id)
        ).scalars().all()
        return [dict(pos=i, nickname=p.nickname, score=p.score) for i, p in enumerate(players, 1)]

    def _find(self, nickname):
        return db.session.execute(
            db.select(Rank).filter(func.lower(Rank.nickname) == func.lower(nickname))
        ).scalar_one_or_none()

    # Identidade: o token é a prova de que o nick é seu

    def register(self, nickname):
        """Cadastra um nick novo. Devolve (resultado, token)."""
        if not valid_nickname(nickname):
            return RESULT_INVALID, None
        if self._find(nickname) is not None:
            return RESULT_TAKEN, None
        token = secrets.token_urlsafe(32)
        db.session.add(Rank(nickname=nickname, score=0, token_hash=_hash(token)))
        try:
            db.session.commit()
        except IntegrityError:  # outro cadastro levou o nick no mesmo instante
            db.session.rollback()
            return RESULT_TAKEN, None
        return RESULT_OK, token

    def claim(self, nickname):
        """Entrega o token de um nick da 1.0.0. Quem chama já provou a posse (save assinado).

        - Nick no banco e sem dono: passa a ser seu, com o score que já tem.
        - Nick fora do banco (cadastrado no servidor antigo depois da migração): é criado
          com score 0, como num cadastro normal.
        - Nick que já tem dono: recusado.
        Devolve (resultado, token, nick).
        """
        if not valid_nickname(nickname):
            return RESULT_INVALID, None, None
        row = self._find(nickname)
        if row is None:
            result, token = self.register(nickname)
            return result, token, (nickname if token else None)
        if row.token_hash is not None:
            return RESULT_TAKEN, None, None
        token = secrets.token_urlsafe(32)
        # O WHERE token_hash IS NULL garante que só uma reivindicação vence.
        updated = db.session.execute(
            db.update(Rank)
            .where(Rank.id == row.id, Rank.token_hash.is_(None))
            .values(token_hash=_hash(token))
        ).rowcount
        db.session.commit()
        if updated != 1:
            return RESULT_TAKEN, None, None
        return RESULT_OK, token, row.nickname

    def authenticate(self, nickname, token):
        if not valid_nickname(nickname) or not isinstance(token, str) or not token:
            return None
        row = self._find(nickname)
        if row is None or row.token_hash is None:
            return None
        if not hmac.compare_digest(row.token_hash, _hash(token)):
            return None
        return row

    # Partidas: o score não pode passar do tempo real que a partida durou

    def start_run(self, player):
        player.run_started_at = _now()
        db.session.commit()

    def finish_run(self, player, score):
        """Fecha a partida aberta. Devolve (aceito, melhor_score) ou None se não havia partida."""
        started = player.run_started_at
        if started is None:
            return None
        player.run_started_at = None  # um envio por partida
        elapsed = (_now() - started).total_seconds()
        accepted = valid_score(score, self.max_score) and score <= elapsed + self.tolerance
        if not accepted:
            log.warning(
                f"Score recusado: {player.nickname} enviou {score!r} numa partida de {elapsed:.0f}s"
            )
        elif score > player.score:
            player.score = score
        db.session.commit()
        return accepted, player.score
