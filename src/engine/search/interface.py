import chess
from typing import Optional, Tuple
from abc import ABC, abstractmethod

class BaseSearch(ABC):
    def __init__(self, evaluator, logger, heuristics = None):
        self.evaluator = evaluator
        self.logger = logger
        self.heuristics = heuristics

    @abstractmethod
    def search(
        self,
        board: chess.Board,
        depth: int,
        time_limit: Optional[float] = None
    ) -> Tuple[int, Optional[chess.Move]]:
        """
        Args:
            board: current chess position
            depth: max search depth
            time_limit: max time in seconds (None = no limit)

        Returns:
            (score, best_move)
        """
        raise NotImplementedError