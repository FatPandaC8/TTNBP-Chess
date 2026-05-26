import chess
from typing import Optional, Tuple

from engine.search.interface import BaseSearch
from engine.utils.logger import Logger
from engine.evaluation.eval import Evaluator

INFINITY = 10**9


class NhuanSearch(BaseSearch):
    def __init__(self, evaluator: Evaluator, logger: Logger):
        super().__init__(evaluator, logger)
    
    def search(
        self,
        board: chess.Board,
        depth: int,
        time_limit: Optional[float] = None,
    ) -> Tuple[int, Optional[chess.Move]]:

        self.timer.start(time_limit)

        def minimax(board: chess.Board, depth: int, alpha: int, beta: int, is_max: bool) -> int:
            # optional time cutoff
            if self.timer.should_stop():
                raise TimeoutError()

            if depth == 0 or board.is_game_over():
                return self.evaluator.evaluate(board)

            if is_max:
                best = -INFINITY
                for move in board.legal_moves:
                    board.push(move)
                    score = minimax(board, depth - 1, alpha, beta, False)
                    board.pop()

                    best = max(best, score)
                    alpha = max(alpha, best)

                    if alpha >= beta:
                        break
                return best

            else:
                best = INFINITY
                for move in board.legal_moves:
                    board.push(move)
                    score = minimax(board, depth - 1, alpha, beta, True)
                    board.pop()

                    best = min(best, score)
                    beta = min(beta, best)

                    if alpha >= beta:
                        break
                return best

        best_move = None
        best_score = -INFINITY if board.turn == chess.WHITE else INFINITY

        try:
            if board.turn == chess.WHITE:
                for move in board.legal_moves:
                    if self.timer.should_stop():
                        raise TimeoutError()

                    board.push(move)
                    score = minimax(board, depth - 1, -INFINITY, INFINITY, False)
                    board.pop()

                    if score > best_score:
                        best_score = score
                        best_move = move

                    self._save_best(best_move, best_score)

            else:
                for move in board.legal_moves:
                    if self.timer.should_stop():
                        raise TimeoutError()

                    board.push(move)
                    score = minimax(board, depth - 1, -INFINITY, INFINITY, True)
                    board.pop()

                    if score < best_score:
                        best_score = score
                        best_move = move

                    self._save_best(best_move, best_score)

        except TimeoutError:
            # fallback to last safe checkpoint
            return self._last_best_score, self._last_best_move

        return best_score, best_move