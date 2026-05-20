import chess

from engine.search.heuristic.interface import BaseHeuristic

class CaptureHeuristic(BaseHeuristic):

    def score_move(
        self,
        board: chess.Board,
        move: chess.Move,
        depth: int,
    ) -> int:

        if board.is_capture(move):
            return 1000

        return 0