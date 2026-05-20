import random
import chess
from engine.evaluation.eval import Evaluator
from engine.search.interface import BaseSearch
from engine.utils.logger import Logger
from typing import Optional, Tuple


class RandomSearch(BaseSearch):

    def __init__(self, evaluator: Evaluator, logger: Logger):
        super().__init__(evaluator=evaluator, logger=logger)

    def search(
        self,
        board: chess.Board,
        depth: int,
        time_limit: float = None
    ) -> Tuple[int, Optional[chess.Move]]:

        moves = list(board.legal_moves)

        if not moves:
            return 0, None

        move = random.choice(moves)

        # optional: evaluate resulting position (nice for consistency)
        board.push(move)
        score = self.evaluator.evaluate(board)
        board.pop()

        return score, move