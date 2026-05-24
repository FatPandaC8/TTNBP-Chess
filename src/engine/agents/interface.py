import chess
from abc import ABC, abstractmethod

class Agent(ABC):

    @abstractmethod
    def get_move(self, board: chess.Board) -> chess.Move:
        raise NotImplementedError
