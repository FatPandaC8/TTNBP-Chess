import chess

from engine.search.heuristic.interface import BaseHeuristic

class CheckHeuristic(BaseHeuristic):

    def score_move(
        self,
        board: chess.Board,
        move: chess.Move,
        depth: int,
    ) -> int:

        if board.gives_check(move):
            return 500

        return 0