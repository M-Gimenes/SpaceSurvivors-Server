"""Acesso ao ranking: leitura, escrita e validação de entrada do jogador."""
import logging
import re

from sqlalchemy import func

from app.models import Rank, db

MAX_RETRY_ATTEMPTS = 2

# Códigos devolvidos ao cliente do jogo. Não altere os valores:
# o executável compilado depende deles.
RESULT_UPDATED = 0
RESULT_ACCEPTED = 1
RESULT_NICKNAME_IN_USE = 2
RESULT_INVALID = 3


class RankingService():

    def _retry(self, operation, argument=None, fallback=False):
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                return operation(argument)
            except Exception as e:
                logging.error(f"Error in {operation.__name__} (attempt {attempt}): {e}")
                db.session.rollback()
            finally:
                db.session.close()
        logging.error(f"Max attempts for {operation.__name__}")
        return fallback

    #Database methods

    def get_info(self, _=None):
        data = []
        players = db.session.execute(db.select(Rank).order_by(Rank.score.desc())).scalars()
        for i, player in enumerate(players.all(), 1):
            data.append(dict(pos=i, nickname=player.nickname, score=player.score))
        return data

    def set_info(self, player_info):
        player = Rank(nickname=player_info['nickname'], score=player_info['score'])
        db.session.add(player)
        db.session.commit()
        return True

    def change_info(self, player_info):
        player = db.session.execute(
            db.select(Rank).filter_by(nickname=player_info['nickname'])
        ).scalar_one()
        player.score = player_info['score']
        db.session.commit()
        return True

    def nickname_exists(self, nickname):
        player = db.session.execute(
            db.select(Rank).filter(func.lower(Rank.nickname) == func.lower(nickname))
        ).scalars()
        return player.all()

    #Data methods

    def get_all_data(self):
        return self._retry(self.get_info) or []

    def process_player_input(self, data):
        result = RESULT_UPDATED
        if self.is_valid_input(data):
            # Em caso de falha assume que o nickname existe, para nunca criar duplicata.
            if not self._retry(self.nickname_exists, data['nickname'], fallback=True):
                if self._retry(self.set_info, data):
                    result = RESULT_ACCEPTED
            elif data['score'] > 0:
                self._retry(self.change_info, data)
            else:
                result = RESULT_NICKNAME_IN_USE
        else:
            result = RESULT_INVALID

        return result

    def is_valid_input(self, input_data):
        nickname = input_data.get('nickname', '')
        score = input_data.get('score', 0)

        if not re.match("^[a-zA-Z0-9]{1,12}$", nickname): return False
        if not isinstance(score, int) or not (0 <= score <= 99999): return False

        return True
