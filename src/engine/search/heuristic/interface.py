from abc import ABC, abstractmethod

import chess

class BaseHeuristic(ABC):

    @abstractmethod
    def score_move(
        self,
        board: chess.Board,
        move: chess.Move,
        depth: int,
    ) -> int:
        """
        Return heuristic score for move ordering.
        Higher score = searched earlier.
        """
        raise NotImplementedError
