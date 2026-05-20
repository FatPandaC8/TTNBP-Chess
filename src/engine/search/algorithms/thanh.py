import time
import chess
import chess.polyglot

from engine.evaluation.eval import Evaluator
from ..cache.tranposition_table import TranspositionTable, TT_EXACT, TT_LOWER, TT_UPPER
from engine.search.interface import BaseSearch
from engine.utils.logger import Logger
from search import SearchTimer

# Định dạng hằng số dễ đọc hơn theo chuẩn PEP 8
INFINITY = 9_999_999
NEGATIVE_INFINITY = -INFINITY
CHECKMATE_SCORE = 9_000_000


class Searcher(BaseSearch):
    def __init__(self, evaluator: Evaluator, logger: Logger):
        super().__init__(evaluator, logger)
        self.tt = TranspositionTable()
        self.timer = SearchTimer()

    def _quiescence(self, board: chess.Board, alpha: int, beta: int) -> int:
        self.timer.nodes += 1

        stand_pat = self.evaluator.evaluate(board)
        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        captures = list(board.generate_legal_moves(
            to_mask=board.occupied_co[not board.turn]
        ))
        
        # Đã bỏ _order_captures do hàm rỗng tránh lãng phí overhead gọi hàm

        for move in captures:
            if self.timer.should_stop():
                return 0

            board.push(move)
            score = -self._quiescence(board, -beta, -alpha)
            board.pop()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    def _negamax(
        self,
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
        null_move_allowed: bool = True  # Giữ nguyên signature theo yêu cầu của bạn
    ) -> int:
        self.timer.nodes += 1
        original_alpha = alpha

        if ply > 0 and (board.can_claim_fifty_moves() or board.is_repetition(2)):
            return 0

        hash_key = chess.polyglot.zobrist_hash(board)
        tt_entry = self.tt.retrieve(hash_key)

        if tt_entry and tt_entry.depth >= depth:
            if tt_entry.flag == TT_EXACT:
                return tt_entry.score
            elif tt_entry.flag == TT_LOWER:
                alpha = max(alpha, tt_entry.score)
            elif tt_entry.flag == TT_UPPER:
                beta = min(beta, tt_entry.score)

            if alpha >= beta:
                return tt_entry.score

        if depth <= 0:
            return self._quiescence(board, alpha, beta)

        moves = list(board.legal_moves)
        if not moves:
            if board.is_check():
                return NEGATIVE_INFINITY + ply
            return 0

        # Đã bỏ _order_moves do hàm rỗng tránh lãng phí overhead gọi hàm

        best_score = NEGATIVE_INFINITY
        best_move = None

        for move in moves:
            if self.timer.should_stop():
                return 0

            board.push(move)
            score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, True)
            board.pop()

            if score > best_score:
                best_score = score
                best_move = move

            alpha = max(alpha, score)
            if alpha >= beta:
                break

        bound = TT_EXACT
        if best_score <= original_alpha:
            bound = TT_UPPER
        elif best_score >= beta:
            bound = TT_LOWER

        self.tt.store(hash_key, best_score, best_move, depth, bound)
        return best_score

    def search(self, board: chess.Board, depth: int, time_limit: float | None = None) -> tuple[int, chess.Move | None]:
        self.timer.start(time_limit)

        best_score = NEGATIVE_INFINITY
        best_move = None
        
        # Tối ưu: Tính toán Zobrist Hash của node gốc một lần duy nhất thay vì tính lại ở mỗi vòng lặp depth
        root_hash = chess.polyglot.zobrist_hash(board)

        for current_depth in range(1, depth + 1):
            if self.timer.should_stop():
                break

            score = self._negamax(
                board,
                current_depth,
                NEGATIVE_INFINITY,
                INFINITY,
                0,
                True
            )

            if not self.timer.should_stop():
                best_score = score

                tt_entry = self.tt.retrieve(root_hash)
                if tt_entry and tt_entry.best_move:
                    best_move = tt_entry.best_move

                self.logger.log_search(
                    best_move,
                    best_score,
                    current_depth,
                    time.perf_counter() - self.timer.start_time
                )

        return best_score, best_move
    


    