import chess
from engine.agents.interface import Agent
from engine.search.interface import BaseSearch

class AIAgent(Agent):
    def __init__(self, id: str, time_limit: float):
        self.id = id
        self.time_limit = time_limit
        self.search: BaseSearch | None = None
        self.depth: int | None = None

    def with_search(self, search: BaseSearch) -> "Agent":
        self.search = search
        return self

    def with_depth(self, depth: int) -> "Agent":
        self.depth = depth
        return self

    def get_move(self, board: chess.Board) -> chess.Move:
        if self.search is None:
            raise RuntimeError(f"Agent {self.id} is missing search algorithm")

        if self.depth is None:
            raise RuntimeError(f"Agent {self.id} depth is not set")

        _, move = self.search.safe_search(board.copy(), self.depth, self.time_limit)

        if move is None:
            move = next(iter(board.legal_moves), None)

        if move is None:
            raise RuntimeError(f"Agent {self.id}: no legal moves available")

        return move
