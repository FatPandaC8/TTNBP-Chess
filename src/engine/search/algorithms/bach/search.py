import time

import chess
import math
from engine.search.algorithms.bach.entry import EXACT, LOWER, UPPER, TTEntry
from engine.search.algorithms.bach.tt import TranspositionTable
from engine.search.interface import BaseSearch

from concurrent.futures import ProcessPoolExecutor
from engine.utils.logger import Logger

PIECE_VALUE = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

def split_moves(moves, k):
    moves = list(moves)
    chunk_size = math.ceil(len(moves) / k)

    return [
        moves[i * chunk_size : (i + 1) * chunk_size]
        for i in range(k)
    ]

def helper_worker(args):
    evaluator, board_fen, depth, root_moves = args

    board = chess.Board(board_fen) # make an isolated board

    local_tt = TranspositionTable() # get isolated tt

    searcher = SimpleSearcher(
        evaluator=evaluator,
        logger=Logger(),
        tt=local_tt
    )

    searcher.helper_search(board, depth, root_moves)

    # return local_tt
    return local_tt.export_entries(min_depth=6) # return filled tt

class SimpleSearcher(BaseSearch):
    def __init__(self, evaluator, logger, tt):
        super().__init__(evaluator, logger)
        self.tt = tt

    def _order_moves(self, board,  moves: list):
        def score(move):
            if board.is_capture(move):
                victim = board.piece_at(move.to_square)
                attacker = board.piece_at(move.from_square)

                if victim is None or attacker is None:
                    return 0

                return PIECE_VALUE[victim.piece_type] - PIECE_VALUE[attacker.piece_type]

            return 0

        return sorted(moves, key=score, reverse=True)

    def minimax(self, board: chess.Board, depth: int, alpha: float, beta: float, isMax: bool):
        alpha_orig = alpha
        beta_orig = beta

        key = hash(board._transposition_key())
        tt_score, alpha, beta = self.tt.lookup(
            key,
            depth,
            alpha,
            beta
        )

        if tt_score is not None:
            return tt_score

        if depth == 0 or board.is_game_over():
            score = self.evaluator.evaluate(board)
            self.tt.store(
                TTEntry(
                    key=key,
                    depth=depth,
                    score=score,
                    flag=EXACT
                )
            )

            return score
        
        if isMax:
            best = -float("inf")

            moves = self._order_moves(board, list(board.legal_moves))

            for move in moves:
                board.push(move)

                score = self.minimax(board, depth - 1, alpha, beta, False) # False to switch turn

                board.pop()

                best = max(best, score)
                alpha = max(alpha, best) # get the best so far
                if alpha >= beta:
                    break

            if best <= alpha_orig:
                flag = UPPER

            elif best >= beta_orig:
                flag = LOWER

            else:
                flag = EXACT

            self.tt.store(
                TTEntry(
                    key=key,
                    depth=depth,
                    score=best,
                    flag=flag
                )
            )

            return best
        
        else:
            best = float("inf")

            moves = self._order_moves(board, list(board.legal_moves))

            for move in moves:
                board.push(move)

                score = self.minimax(board, depth - 1, alpha, beta, True)

                board.pop()

                best = min(best, score)
                beta = min(beta, best)
                if alpha >= beta:
                    break

            if best <= alpha_orig:
                flag = UPPER

            elif best >= beta_orig:
                flag = LOWER

            else:
                flag = EXACT

            self.tt.store(
                TTEntry(
                    key=key,
                    depth=depth,
                    score=best,
                    flag=flag
                )
            )

            return best

    def helper_search(self, board, depth, root_moves=None):
        is_max = board.turn == chess.WHITE

        alpha = -float("inf")
        beta = float("inf")

        best = -float("inf") if is_max else float("inf")

        for move in root_moves:
            board.push(move)

            score = self.minimax(
                board,
                depth - 1,
                alpha,
                beta,
                not is_max
            )

            board.pop()

            if is_max:
                best = max(best, score)
                alpha = max(alpha, best)
            else:
                best = min(best, score)
                beta = min(beta, best)

        return best

    def search(self, board, depth, time_limit=None):
        start = time.time()
        helper_depths = list(range(1, depth // 2 + 1))

        moves = list(board.legal_moves)
        if not moves:
            return 0, None
        
        num_workers = len(helper_depths)
        move_groups = split_moves(moves, num_workers)

        tasks = [
            (
                self.evaluator,
                board.fen(),
                d,
                move_groups[i]
            )
            for i, d in enumerate(helper_depths)
        ]

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            helper_tts = list(executor.map(helper_worker, tasks))

        for helper_tt in helper_tts:
            self.tt.merge_tt(helper_tt)

        best_score = None
        best_move = moves[0]

        current_best_score = None
        current_best_move = None

        for curr_depth in range(1, depth + 1):
            if time_limit is not None and time.time() - start > time_limit:
                break

            current_best_score = None
            current_best_move = None

            alpha = -float("inf")
            beta = float("inf")

            for move in self._order_moves(board, list(board.legal_moves)):
                board.push(move)
                score = self.minimax(board, curr_depth - 1, alpha, beta, False)
                board.pop()

                if current_best_score is None or score > current_best_score:
                    current_best_score = score
                    current_best_move = move

                alpha = max(alpha, current_best_score)
                self.logger.log_search(best_score, best_move, curr_depth, 0)

        if current_best_move is not None:
            best_score = current_best_score
            best_move = current_best_move

        return best_score if best_score is not None else 0, best_move