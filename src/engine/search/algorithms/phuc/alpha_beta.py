from logging import Logger
import time
from typing import Optional, Tuple

import chess

from engine.evaluation.eval import Evaluator
from engine.search.heuristic.manager import HeuristicManager
from engine.search.interface import BaseSearch

class AlphaBetaSearcher(BaseSearch):
    
    INF = 999999

    def __init__(self, evaluator, logger, heuristics):
        super().__init__(evaluator, logger, heuristics)
        
        self.evaluator:  Evaluator           = evaluator
        self.logger:     Logger              = logger
        self.heuristics: HeuristicManager    = heuristics
    
    def search(
        self,
        board: chess.Board,
        depth: int,
        time_limit: float = None
    ) -> Tuple[int, Optional[chess.Move]]:

        self.nodes = 0
        start_time = time.time()

        best_score = -self.INF
        best_move = None

        moves = self.heuristics.order_moves(
            board,
            board.legal_moves,
            depth,
        )

        for move in moves:

            board.push(move)

            score = -self.negamax(
                board,
                depth - 1,
                -self.INF,
                self.INF
            )

            board.pop()

            self.logger.log_search(
                move=move,
                score=score,
                depth=depth,
                time=round(time.time() - start_time, 4)
            )

            if score > best_score:
                best_score = score
                best_move = move

        elapsed = round(time.time() - start_time, 4)

        print(
            f"[RESULT] "
            f"best_move={best_move} "
            f"best_score={best_score} "
            f"nodes={self.nodes} "
            f"time={elapsed}s"
        )

        return best_score, best_move
    
    def negamax(
        self,
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int
    ):
        
        self.nodes += 1 # Counter

        # Terminal node or depth reached
        if depth == 0 or board.is_game_over():

            if board.is_checkmate():
                return -self.INF

            if (
                board.is_stalemate()
                or board.is_insufficient_material()
                or board.can_claim_draw()
            ):
                return 0

            return self.evaluator.evaluate(board)

        best_score = -self.INF

        moves = self.heuristics.order_moves(
            board,
            board.legal_moves,
            depth,
        )

        for move in moves:

            board.push(move)

            score = -self.negamax(
                board,
                depth - 1,
                -beta,
                -alpha
            )

            board.pop()

            best_score = max(best_score, score)
            alpha = max(alpha, score)

            # Beta cutoff
            if alpha >= beta:
                break

        return best_score
