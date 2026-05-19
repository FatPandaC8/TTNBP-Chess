import chess

from engine.search.heuristic.interface import BaseHeuristic

class HeuristicManager:

    def __init__(self, heuristics: list[BaseHeuristic]):
        self.heuristics = heuristics

    def order_moves(
        self,
        board: chess.Board,
        moves,
        depth: int,
    ):

        moves = list(moves)

        def score(move):

            total = 0

            for heuristic in self.heuristics:
                total += heuristic.score_move(
                    board,
                    move,
                    depth,
                )

            return total

        return sorted(
            moves,
            key=score,
            reverse=True
        )