import chess
from abc import ABC, abstractmethod
class Search(ABC):
    @abstractmethod
    def search(self, board: chess.Board, depth: int, timelimit: float = None) -> tuple[int, chess.Move]:
        raise NotImplementedError("Search method must be implemented by subclasses.")