import chess
from typing import Optional, Tuple
from abc import ABC, abstractmethod
from engine.search.timer import SearchTimer

class BaseSearch(ABC):
    def __init__(self, evaluator, logger, heuristics=None):
        self.evaluator = evaluator
        self.logger = logger
        self.heuristics = heuristics
        self.timer = SearchTimer()
        self._last_best_move: Optional[chess.Move] = None
        self._last_best_score: int = 0

    def _save_best(self, move: Optional[chess.Move], score: int):
        """Call after each completed depth to checkpoint the best result so far."""
        if move is not None:
            self._last_best_move = move
            self._last_best_score = score

    def safe_search(
        self,
        board: chess.Board,
        depth: int,
        time_limit: Optional[float] = None,
    ) -> Tuple[int, Optional[chess.Move]]:
        """Calls search() and returns the last checkpoint on TimeoutError."""
        try:
            return self.search(board, depth, time_limit)
        except TimeoutError:
            return self._last_best_score, self._last_best_move

    @abstractmethod
    def search(
        self,
        board: chess.Board,
        depth: int,
        time_limit: Optional[float] = None,
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
