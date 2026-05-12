import chess
from engine.search.interface import BaseSearch

class Agent:
    def __init__(self, id: str, time_limit: float):
        self.id = id
        self.time_limit = time_limit
        self.search = None
        self.depth = None

    def with_search(self, search: BaseSearch) -> "Agent":
        self.search = search
        return self

    def with_depth(self, depth: int) -> "Agent":
        self.depth = depth
        return self

    def get_move(self, board: chess.Board) -> chess.Move:
        if self.search is None:
            raise RuntimeError("Agent is missing search algorithm")

        if self.depth is None:
            raise RuntimeError("Agent depth is not set")

        board_copy = board.copy()

        _, move = self.search.search(
            board_copy,
            self.depth,
            self.time_limit
        )

        if move is None:
            raise RuntimeError("Search returned no move")

        return move