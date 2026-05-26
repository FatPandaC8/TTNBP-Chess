from __future__ import annotations

from typing import Optional

import chess
import time
import chess.polyglot
from engine.evaluation.eval import Evaluator
from engine.search.interface import BaseSearch
from engine.utils.logger import Logger

try:
    # Ưu tiên import absolute giống bản đầu để chạy ổn khi project được gọi từ root.
    from engine.search.cache.tranposition_table import TranspositionTable, TT_EXACT, TT_LOWER, TT_UPPER
    from engine.search.heuristic.history import HistoryTable
    from engine.search.heuristic.killer_move import KillerMoves
except ImportError:
    # Fallback cho trường hợp file nằm trong package con và cần relative import như bản update.
    from ..cache.tranposition_table import TranspositionTable, TT_EXACT, TT_LOWER, TT_UPPER
    from ..heuristic.history import HistoryTable
    from ..heuristic.killer_move import KillerMoves

# ==============================================================================
# HẰNG SỐ CỐ ĐỊNH
# ==============================================================================
INFINITY = 9_999_999
NEGATIVE_INFINITY = -INFINITY
CHECKMATE_SCORE = 9_000_000

# Bảng 7x7: index = victim_type * 7 + attacker_type
# chess.PAWN..KING = 1..6, index 0 để trống cho trường hợp không xác định.
MVV_LVA_SCORES = [
    0,  0,  0,  0,  0,  0,  0,  # Victim 0
    0, 50, 51, 52, 53, 54, 55,  # Victim 1 (Pawn)
    0, 40, 41, 42, 43, 44, 45,  # Victim 2 (Knight)
    0, 30, 31, 32, 33, 34, 35,  # Victim 3 (Bishop)
    0, 20, 21, 22, 23, 24, 25,  # Victim 4 (Rook)
    0, 10, 11, 12, 13, 14, 15,  # Victim 5 (Queen)
    0,  0,  0,  0,  0,  0,  0,  # Victim 6 (King)
]

# ==============================================================================
# BẢNG THAM SỐ TUNING (SPSA / UCI)
# Tuple: (default, min, max, step)
# ==============================================================================
TUNABLE_PARAMS: dict[str, tuple[int, int, int, int]] = {
    "LMR_FULL_DEPTH_MOVES": (2, 2, 8, 1),
    "LMR_REDUCTION_LIMIT": (5, 2, 5, 1),
    "LMR_REDUCTION_BASE": (2, 1, 2, 1),
    "LMR_REDUCTION_DEEP": (3, 1, 3, 1),

    "NULL_MOVE_MIN_DEPTH": (5, 2, 5, 1),
    "NULL_MOVE_REDUCTION": (2, 2, 4, 1),

    "ASPIRATION_MIN_DEPTH": (5, 3, 7, 1),
    "ASPIRATION_DELTA": (50, 20, 200, 10),

    "RAZOR_DEPTH": (4, 1, 4, 1),
    "RAZOR_MARGIN_D1": (430, 100, 700, 30),
    "RAZOR_MARGIN_D2": (440, 200, 900, 40),
    "RAZOR_MARGIN_D3": (520, 400, 1500, 60),

    "FUTILITY_DEPTH": (1, 1, 3, 1),
    "FUTILITY_MARGIN_D1": (200, 50, 400, 25),
    "FUTILITY_MARGIN_D2": (400, 100, 600, 30),

    "MO_KILLER1_SCORE": (80_000, 55_000, 95_000, 5_000),
    "MO_KILLER2_SCORE": (80_000, 50_000, 90_000, 5_000),
    "HISTORY_MAX_BONUS": (3_500, 500, 8_000, 500),
}

_MO_TT_SCORE = 1_000_000
_MO_CAPTURE_BASE = 100_000
_MO_PROMOTION_BASE = 85_000


class SearchTimer:
    __slots__ = ["start_time", "time_limit", "nodes"]

    def __init__(self):
        self.start_time = 0.0
        self.time_limit = None
        self.nodes = 0

    def start(self, time_limit=None):
        self.start_time = time.perf_counter()
        self.time_limit = time_limit
        self.nodes = 0

    def should_stop(self) -> bool:
        if self.time_limit is None:
            return False
        # Không check timer từng node để giảm overhead.
        if (self.nodes & 2047) == 0:
            return (time.perf_counter() - self.start_time) >= self.time_limit
        return False


class Searcher(BaseSearch):
    def __init__(self, evaluator: Evaluator, logger: Logger):
        super().__init__(evaluator, logger)

        self.tt = TranspositionTable()
        self.timer = SearchTimer()
        self.history_table = HistoryTable()
        self.killer_moves = KillerMoves()

        # Nhóm A: ngưỡng độ sâu & nước đi
        self.lmr_full_depth_moves = TUNABLE_PARAMS["LMR_FULL_DEPTH_MOVES"][0]
        self.lmr_reduction_limit = TUNABLE_PARAMS["LMR_REDUCTION_LIMIT"][0]
        self.lmr_reduction_base = TUNABLE_PARAMS["LMR_REDUCTION_BASE"][0]
        self.lmr_reduction_deep = TUNABLE_PARAMS["LMR_REDUCTION_DEEP"][0]

        self.null_move_min_depth = TUNABLE_PARAMS["NULL_MOVE_MIN_DEPTH"][0]
        self.null_move_reduction = TUNABLE_PARAMS["NULL_MOVE_REDUCTION"][0]

        self.aspiration_min_depth = TUNABLE_PARAMS["ASPIRATION_MIN_DEPTH"][0]
        self.aspiration_delta = TUNABLE_PARAMS["ASPIRATION_DELTA"][0]

        self.razor_depth = TUNABLE_PARAMS["RAZOR_DEPTH"][0]
        self.futility_depth = TUNABLE_PARAMS["FUTILITY_DEPTH"][0]

        self.razor_margins = [
            0,
            TUNABLE_PARAMS["RAZOR_MARGIN_D1"][0],
            TUNABLE_PARAMS["RAZOR_MARGIN_D2"][0],
            TUNABLE_PARAMS["RAZOR_MARGIN_D3"][0],
        ]
        self.futility_margins = [
            0,
            TUNABLE_PARAMS["FUTILITY_MARGIN_D1"][0],
            TUNABLE_PARAMS["FUTILITY_MARGIN_D2"][0],
        ]

        # Nhóm C: điểm move-ordering
        self.mo_killer1_score = TUNABLE_PARAMS["MO_KILLER1_SCORE"][0]
        self.mo_killer2_score = TUNABLE_PARAMS["MO_KILLER2_SCORE"][0]
        self.history_max_bonus = TUNABLE_PARAMS["HISTORY_MAX_BONUS"][0]

    # ──────────────────────────────────────────────────────────────────────
    # SET OPTION / TUNING
    # ──────────────────────────────────────────────────────────────────────

    def set_option(self, name: str, value: int) -> bool:
        """Cập nhật tham số tuning từ UCI/SPSA."""
        val = int(value)

        if name == "LMR_FULL_DEPTH_MOVES":
            self.lmr_full_depth_moves = val
        elif name == "LMR_REDUCTION_LIMIT":
            self.lmr_reduction_limit = val
        elif name == "LMR_REDUCTION_BASE":
            self.lmr_reduction_base = val
        elif name == "LMR_REDUCTION_DEEP":
            self.lmr_reduction_deep = val
        elif name == "NULL_MOVE_MIN_DEPTH":
            self.null_move_min_depth = val
        elif name == "NULL_MOVE_REDUCTION":
            self.null_move_reduction = val
        elif name == "ASPIRATION_MIN_DEPTH":
            self.aspiration_min_depth = val
        elif name == "ASPIRATION_DELTA":
            self.aspiration_delta = val
        elif name == "RAZOR_DEPTH":
            self.razor_depth = val
        elif name == "RAZOR_MARGIN_D1":
            self.razor_margins[1] = val
        elif name == "RAZOR_MARGIN_D2":
            self.razor_margins[2] = val
        elif name == "RAZOR_MARGIN_D3":
            self.razor_margins[3] = val
        elif name == "FUTILITY_DEPTH":
            self.futility_depth = val
        elif name == "FUTILITY_MARGIN_D1":
            self.futility_margins[1] = val
        elif name == "FUTILITY_MARGIN_D2":
            self.futility_margins[2] = val
        elif name == "MO_KILLER1_SCORE":
            self.mo_killer1_score = val
        elif name == "MO_KILLER2_SCORE":
            self.mo_killer2_score = val
        elif name == "HISTORY_MAX_BONUS":
            self.history_max_bonus = val
        else:
            return False
        return True

    # ──────────────────────────────────────────────────────────────────────
    # SAFE HELPERS: giữ tinh thần bản đầu — không để heuristic phụ làm raise
    # ──────────────────────────────────────────────────────────────────────

    def _killer_at(self, ply: int, slot: int):
        try:
            return self.killer_moves.moves[ply][slot]
        except (AttributeError, IndexError, TypeError):
            return None

    def _is_killer(self, move: chess.Move, ply: int) -> bool:
        # Ưu tiên method nếu KillerMoves bản mới có is_killer().
        try:
            is_killer = getattr(self.killer_moves, "is_killer", None)
            if callable(is_killer):
                return bool(is_killer(move, ply))
        except (AttributeError, IndexError, TypeError):
            pass

        # Fallback giống bản đầu: truy cập mảng có try/except.
        return move == self._killer_at(ply, 0) or move == self._killer_at(ply, 1)

    def _store_killer(self, move: chess.Move, ply: int) -> None:
        try:
            self.killer_moves.store(move, ply)
        except (AttributeError, IndexError, TypeError):
            pass

    def _history_score(self, board: chess.Board, move: chess.Move) -> int:
        try:
            get_score = getattr(self.history_table, "get_score", None)
            if callable(get_score):
                return min(int(get_score(board, move)), self.history_max_bonus)
        except Exception:
            # History chỉ là heuristic phụ; nếu table chưa đủ API thì trả 0 để tránh crash search.
            pass
        return 0

    def _record_history_cutoff(self, board: chess.Board, move: chess.Move, depth: int) -> None:
        try:
            self.history_table.record_cutoff(board, move, depth)
        except Exception:
            pass

    @staticmethod
    def _piece_type_or_pawn(piece) -> int:
        return piece.piece_type if piece else chess.PAWN

    @staticmethod
    def _mvv_lva_index(victim_type: int, attacker_type: int) -> int:
        return victim_type * 7 + attacker_type

    @staticmethod
    def _margin_at(margins: list[int], depth: int) -> int:
        if depth < len(margins):
            return margins[depth]
        # Nếu depth tuning vượt số margin khai báo, dùng margin sâu nhất thay vì 0.
        return margins[-1]

    def _save_best_safe(self, best_move, best_score: int) -> None:
        save_best = getattr(self, "_save_best", None)
        if callable(save_best):
            try:
                save_best(best_move, best_score)
            except TypeError:
                # Phòng trường hợp BaseSearch cũ không cùng signature.
                pass

    def _log_search_safe(self, best_score: int, best_move, depth: int, elapsed: float) -> None:
        try:
            # Giữ thứ tự tham số theo bản đầu: score, move, depth, elapsed.
            self.logger.log_search(best_score, best_move, depth, elapsed)
        except TypeError:
            # Fallback cho logger bản update nếu đang dùng signature: move, score, depth, elapsed.
            self.logger.log_search(best_move, best_score, depth, elapsed)

    # ──────────────────────────────────────────────────────────────────────
    # MOVE ORDERING
    # ──────────────────────────────────────────────────────────────────────

    def _order_moves(self, board: chess.Board, moves: list[chess.Move], tt_move: Optional[chess.Move], ply: int):
        def score_move(move: chess.Move) -> int:
            if tt_move is not None and move == tt_move:
                return _MO_TT_SCORE

            if board.is_capture(move):
                victim = board.piece_at(move.to_square)
                attacker = board.piece_at(move.from_square)
                v_type = self._piece_type_or_pawn(victim)
                a_type = self._piece_type_or_pawn(attacker)
                return _MO_CAPTURE_BASE + MVV_LVA_SCORES[self._mvv_lva_index(v_type, a_type)]

            if move.promotion:
                return _MO_PROMOTION_BASE + move.promotion * 100

            if move == self._killer_at(ply, 0):
                return self.mo_killer1_score
            if move == self._killer_at(ply, 1):
                return self.mo_killer2_score

            return self._history_score(board, move)

        moves.sort(key=score_move, reverse=True)

    def _order_captures(self, board: chess.Board, moves: list[chess.Move]):
        def cap_score(move: chess.Move) -> int:
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            v_type = self._piece_type_or_pawn(victim)
            a_type = self._piece_type_or_pawn(attacker)
            return MVV_LVA_SCORES[self._mvv_lva_index(v_type, a_type)]

        moves.sort(key=cap_score, reverse=True)

    def can_not_is_zugzwang(self, board: chess.Board) -> bool:
        """True nếu bên tới lượt còn quân mạnh, thường an toàn hơn cho null-move pruning."""
        color = board.turn
        return bool(
            board.pieces(chess.KNIGHT, color)
            or board.pieces(chess.BISHOP, color)
            or board.pieces(chess.ROOK, color)
            or board.pieces(chess.QUEEN, color)
        )

    # ──────────────────────────────────────────────────────────────────────
    # QUIESCENCE SEARCH
    # ──────────────────────────────────────────────────────────────────────

    def _quiescence(self, board: chess.Board, alpha: int, beta: int) -> int:
        self.timer.nodes += 1

        stand_pat = self.evaluator.evaluate(board)
        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        captures = list(board.generate_legal_moves(to_mask=board.occupied_co[not board.turn]))
        self._order_captures(board, captures)

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

    # ──────────────────────────────────────────────────────────────────────
    # NEGAMAX + ALPHA-BETA + TT + NULL MOVE + RAZOR/FUTILITY + PVS/LMR
    # ──────────────────────────────────────────────────────────────────────

    def _negamax(
        self,
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
        null_move_allowed: bool,
    ) -> int:
        self.timer.nodes += 1
        original_alpha = alpha

        # Luật hòa: tránh claim draw ở root làm mất cơ hội tìm nước thắng.
        if ply > 0 and (board.can_claim_fifty_moves() or board.is_repetition(2)):
            return 0

        # Transposition Table
        hash_key = chess.polyglot.zobrist_hash(board)
        tt_entry = self.tt.retrieve(hash_key)
        tt_best_move = None

        if tt_entry:
            tt_best_move = tt_entry.best_move
            if tt_entry.depth >= depth:
                if tt_entry.flag == TT_EXACT:
                    return tt_entry.score
                if tt_entry.flag == TT_LOWER:
                    alpha = max(alpha, tt_entry.score)
                elif tt_entry.flag == TT_UPPER:
                    beta = min(beta, tt_entry.score)
                if alpha >= beta:
                    return tt_entry.score

        if depth <= 0:
            return self._quiescence(board, alpha, beta)

        in_check = board.is_check()

        # Null Move Pruning
        if (
            null_move_allowed
            and depth >= self.null_move_min_depth
            and not in_check
            and self.can_not_is_zugzwang(board)
        ):
            board.push(chess.Move.null())
            null_score = -self._negamax(
                board,
                depth - 1 - self.null_move_reduction,
                -beta,
                -beta + 1,
                ply + 1,
                False,
            )
            board.pop()

            if self.timer.should_stop():
                return 0
            if null_score >= beta:
                return null_score

        # Razoring: chỉ áp dụng khi không ở vùng mate score.
        if depth <= self.razor_depth and not in_check and abs(alpha) < CHECKMATE_SCORE:
            static_eval = self.evaluator.evaluate(board)
            margin = self._margin_at(self.razor_margins, depth)
            if static_eval < alpha - margin:
                q_score = self._quiescence(board, alpha, beta)
                if q_score < alpha:
                    return q_score

        # Futility Pruning: đánh dấu, không prune nước đầu để vẫn có best_move.
        futility_pruning = False
        if (
            depth <= self.futility_depth
            and not in_check
            and abs(alpha) < CHECKMATE_SCORE
            and abs(beta) < CHECKMATE_SCORE
        ):
            static_eval = self.evaluator.evaluate(board)
            margin = self._margin_at(self.futility_margins, depth)
            if static_eval + margin <= alpha:
                futility_pruning = True

        moves = list(board.legal_moves)
        if not moves:
            return NEGATIVE_INFINITY + ply if in_check else 0

        self._order_moves(board, moves, tt_best_move, ply)

        best_score = NEGATIVE_INFINITY
        best_move_this_node = None
        moves_searched = 0

        for move in moves:
            if self.timer.should_stop():
                return 0

            is_capture = board.is_capture(move)
            gives_check = board.gives_check(move)

            if (
                futility_pruning
                and moves_searched > 0
                and not is_capture
                and not move.promotion
                and not gives_check
                and not in_check
            ):
                continue

            board.push(move)
            is_killer = self._is_killer(move, ply)

            use_lmr = (
                moves_searched >= self.lmr_full_depth_moves
                and depth >= self.lmr_reduction_limit
                and not is_capture
                and not move.promotion
                and not in_check
                and not gives_check
                and not is_killer
            )

            if moves_searched == 0:
                # PV move: search full window.
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, True)

            elif use_lmr:
                reduction = (
                    self.lmr_reduction_deep
                    if depth >= 6 and moves_searched >= 8
                    else self.lmr_reduction_base
                )

                # Late move: thử null-window với depth giảm trước.
                score = -self._negamax(
                    board,
                    depth - 1 - reduction,
                    -alpha - 1,
                    -alpha,
                    ply + 1,
                    True,
                )

                # Nếu vượt alpha, search lại full-depth null-window.
                if score > alpha:
                    score = -self._negamax(board, depth - 1, -alpha - 1, -alpha, ply + 1, True)

                # Nếu vẫn vượt alpha, search lại full-window.
                if score > alpha:
                    score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, True)

            else:
                # PVS cho các nước sau: null-window trước, fail-high thì full-window.
                score = -self._negamax(board, depth - 1, -alpha - 1, -alpha, ply + 1, True)
                if score > alpha:
                    score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, True)

            board.pop()
            moves_searched += 1

            if score > best_score:
                best_score = score
                best_move_this_node = move

            alpha = max(alpha, score)

            if alpha >= beta:
                if not is_capture:
                    self._store_killer(move, ply)
                    self._record_history_cutoff(board, move, depth)
                break

        bound = TT_EXACT
        if best_score <= original_alpha:
            bound = TT_UPPER
        elif best_score >= beta:
            bound = TT_LOWER

        self.tt.store(hash_key, best_score, best_move_this_node, depth, bound)
        return best_score

    # ──────────────────────────────────────────────────────────────────────
    # ITERATIVE DEEPENING + ASPIRATION WINDOW
    # ──────────────────────────────────────────────────────────────────────

    def search(self, board: chess.Board, depth: int, time_limit: float = None) -> tuple[int, Optional[chess.Move]]:
        self.timer.start(time_limit)
        self.history_table.age()

        best_move = None
        best_score = NEGATIVE_INFINITY
        prev_score = 0

        for current_depth in range(1, depth + 1):
            if self.timer.should_stop():
                break

            if current_depth >= self.aspiration_min_depth:
                delta = self.aspiration_delta
                alpha = prev_score - delta
                beta = prev_score + delta

                while True:
                    score = self._negamax(board, current_depth, alpha, beta, 0, True)

                    if self.timer.should_stop():
                        break

                    if score <= alpha:
                        alpha = max(alpha - delta, NEGATIVE_INFINITY)
                        delta *= 2
                    elif score >= beta:
                        beta = min(beta + delta, INFINITY)
                        delta *= 2
                    else:
                        break
            else:
                score = self._negamax(board, current_depth, NEGATIVE_INFINITY, INFINITY, 0, True)

            if not self.timer.should_stop():
                best_score = score
                prev_score = score

                tt_entry = self.tt.retrieve(chess.polyglot.zobrist_hash(board))
                if tt_entry and tt_entry.best_move:
                    best_move = tt_entry.best_move

                self._save_best_safe(best_move, best_score)
                self._log_search_safe(
                    best_score,
                    best_move,
                    current_depth,
                    time.perf_counter() - self.timer.start_time,
                )

        return best_score, best_move


