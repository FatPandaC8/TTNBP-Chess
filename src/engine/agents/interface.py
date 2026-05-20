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

    def get_move(self, board: chess.Board, time_limit: float = None) -> chess.Move:
        if self.search is None:
            raise RuntimeError("Agent is missing search algorithm")
        if self.depth is None:
            raise RuntimeError("Agent depth is not set")

        # Ưu tiên time_limit truyền vào, fallback về self.time_limit
        effective_time = time_limit if time_limit is not None else self.time_limit

        board_copy = board.copy()
        _, move = self.search.search(board_copy, self.depth, effective_time)

        if move is None:
            # Fallback thay vì crash
            legal = list(board.legal_moves)
            return legal[0] if legal else None

        return move