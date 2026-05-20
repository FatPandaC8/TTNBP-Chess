import chess
from typing import Optional, Tuple
from abc import ABC, abstractmethod

from .context import SearchContext

class BaseSearch(ABC):
    def __init__(self, context: SearchContext):
        self.context = context

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