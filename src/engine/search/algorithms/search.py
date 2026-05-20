import chess
import time
import chess.polyglot
from engine.evaluation.eval import Evaluator
from engine.search.interface import BaseSearch
from engine.utils.logger import Logger
from ..cache.tranposition_table import TranspositionTable, TT_EXACT, TT_LOWER, TT_UPPER
from ..heuristic.history import HistoryTable
from ..heuristic.killer_move import KillerMoves

# ==============================================================================
# HẰNG SỐ CỐ ĐỊNH (KHÔNG TUNE)
# ==============================================================================
INFINITY          = 9999999
NEGATIVE_INFINITY = -INFINITY
CHECKMATE_SCORE   = 9000000

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
# BẢNG KHAI BÁO THAM SỐ TUNING (SPSA / UCI)
# ==============================================================================
TUNABLE_PARAMS: dict[str, tuple] = {
    # LMR – Late Move Reduction
    "LMR_FULL_DEPTH_MOVES": (4,  2,  8,  1),
    "LMR_REDUCTION_LIMIT":  (3,  2,  5,  1),
    "LMR_REDUCTION_BASE":   (1,  1,  2,  1),
    "LMR_REDUCTION_DEEP":   (2,  1,  3,  1),

    # Null Move Pruning
    "NULL_MOVE_MIN_DEPTH":  (3,  2,  5,  1),
    "NULL_MOVE_REDUCTION":  (3,  2,  4,  1),

    # Aspiration Windows
    "ASPIRATION_MIN_DEPTH": (4,  3,  7,  1),
    "ASPIRATION_DELTA":     (50,  20, 200,  10),

    # Razoring
    "RAZOR_DEPTH":          (3,  1,  4,  1),
    "RAZOR_MARGIN_D1":      (300, 100, 700,  30),
    "RAZOR_MARGIN_D2":      (500, 200, 900,  40),
    "RAZOR_MARGIN_D3":      (900, 400, 1500, 60),

    # Futility Pruning
    "FUTILITY_DEPTH":       (2,  1,  3,  1),
    "FUTILITY_MARGIN_D1":   (150,  50, 400,  25),
    "FUTILITY_MARGIN_D2":   (300, 100, 600,  30),

    # Move-ordering scores
    "MO_KILLER1_SCORE":     (75000, 55000, 95000, 5000),
    "MO_KILLER2_SCORE":     (70000, 50000, 90000, 5000),
    "HISTORY_MAX_BONUS":    (2000, 500, 8000, 500),
}

_MO_TT_SCORE       = 1_000_000
_MO_CAPTURE_BASE   =   100_000
_MO_PROMOTION_BASE =    85_000


class SearchTimer:
    __slots__ = ['start_time', 'time_limit', 'nodes']

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
        if (self.nodes & 2047) == 0:
            return (time.perf_counter() - self.start_time) >= self.time_limit
        return False


class Searcher(BaseSearch):
    def __init__(self, evaluator: Evaluator, logger: Logger):
        super().__init__(evaluator, logger)

        self.tt            = TranspositionTable()
        self.timer         = SearchTimer()
        self.history_table = HistoryTable()
        self.killer_moves  = KillerMoves()

        # ── KHỞI TẠO CÁC THUỘC TÍNH PHẲNG ĐỂ TRUY CẬP NHANH (FAST ACCESS) ──────
        
        # Nhóm A: Ngưỡng độ sâu & nước đi
        self.lmr_full_depth_moves = TUNABLE_PARAMS["LMR_FULL_DEPTH_MOVES"][0]
        self.lmr_reduction_limit  = TUNABLE_PARAMS["LMR_REDUCTION_LIMIT"][0]
        self.lmr_reduction_base   = TUNABLE_PARAMS["LMR_REDUCTION_BASE"][0]
        self.lmr_reduction_deep   = TUNABLE_PARAMS["LMR_REDUCTION_DEEP"][0]

        self.null_move_min_depth  = TUNABLE_PARAMS["NULL_MOVE_MIN_DEPTH"][0]
        self.null_move_reduction  = TUNABLE_PARAMS["NULL_MOVE_REDUCTION"][0]

        self.aspiration_min_depth = TUNABLE_PARAMS["ASPIRATION_MIN_DEPTH"][0]
        self.aspiration_delta     = TUNABLE_PARAMS["ASPIRATION_DELTA"][0]

        self.razor_depth          = TUNABLE_PARAMS["RAZOR_DEPTH"][0]
        self.futility_depth       = TUNABLE_PARAMS["FUTILITY_DEPTH"][0]

        # Mảng Margins theo Depth: index chính là depth (0, 1, 2, 3)
        # Giúp loại bỏ hoàn toàn việc tạo chuỗi f"RAZOR_MARGIN_D{depth}"
        self.razor_margins = [
            0, # Depth 0 không dùng
            TUNABLE_PARAMS["RAZOR_MARGIN_D1"][0],
            TUNABLE_PARAMS["RAZOR_MARGIN_D2"][0],
            TUNABLE_PARAMS["RAZOR_MARGIN_D3"][0]
        ]

        self.futility_margins = [
            0, # Depth 0 không dùng
            TUNABLE_PARAMS["FUTILITY_MARGIN_D1"][0],
            TUNABLE_PARAMS["FUTILITY_MARGIN_D2"][0]
        ]

        # Nhóm C: Move-ordering scores
        self.mo_killer1_score     = TUNABLE_PARAMS["MO_KILLER1_SCORE"][0]
        self.mo_killer2_score     = TUNABLE_PARAMS["MO_KILLER2_SCORE"][0]
        self.history_max_bonus    = TUNABLE_PARAMS["HISTORY_MAX_BONUS"][0]

    def set_option(self, name: str, value: int) -> bool:
        """
        Được gọi bởi UCI Handler. 
        Hàm này có thể chậm một chút không sao vì chỉ gọi khi Tuner setup cấu hình.
        """
        val = int(value)
        
        # Nhóm A
        if name == "LMR_FULL_DEPTH_MOVES":   self.lmr_full_depth_moves = val
        elif name == "LMR_REDUCTION_LIMIT":  self.lmr_reduction_limit = val
        elif name == "LMR_REDUCTION_BASE":   self.lmr_reduction_base = val
        elif name == "LMR_REDUCTION_DEEP":   self.lmr_reduction_deep = val
        elif name == "NULL_MOVE_MIN_DEPTH":  self.null_move_min_depth = val
        elif name == "NULL_MOVE_REDUCTION":  self.null_move_reduction = val
        elif name == "ASPIRATION_MIN_DEPTH": self.aspiration_min_depth = val
        elif name == "RAZOR_DEPTH":          self.razor_depth = val
        elif name == "FUTILITY_DEPTH":       self.futility_depth = val
        
        # Nhóm B (Centipawns)
        elif name == "ASPIRATION_DELTA":     self.aspiration_delta = val
        elif name == "RAZOR_MARGIN_D1":      self.razor_margins[1] = val
        elif name == "RAZOR_MARGIN_D2":      self.razor_margins[2] = val
        elif name == "RAZOR_MARGIN_D3":      self.razor_margins[3] = val
        elif name == "FUTILITY_MARGIN_D1":   self.futility_margins[1] = val
        elif name == "FUTILITY_MARGIN_D2":   self.futility_margins[2] = val
        
        # Nhóm C
        elif name == "MO_KILLER1_SCORE":     self.mo_killer1_score = val
        elif name == "MO_KILLER2_SCORE":     self.mo_killer2_score = val
        elif name == "HISTORY_MAX_BONUS":    self.history_max_bonus = val
        else:
            return False
        return True

    # ──────────────────────────────────────────────────────────────────────────
    # MOVE ORDERING (TỐI ƯU TRUY CẬP BIẾN PHẲNG)
    # ──────────────────────────────────────────────────────────────────────────

    def _order_moves(self, board: chess.Board, moves: list, tt_move: chess.Move, ply: int):
        def score_move(move):
            if move == tt_move:
                return _MO_TT_SCORE
            if board.is_capture(move):
                victim   = board.piece_at(move.to_square)
                attacker = board.piece_at(move.from_square)
                v_type   = victim.piece_type   if victim   else chess.PAWN
                a_type   = attacker.piece_type if attacker else chess.PAWN
                return _MO_CAPTURE_BASE + MVV_LVA_SCORES[v_type * 6 + a_type]
            if move.promotion:
                return _MO_PROMOTION_BASE + move.promotion * 100
            if move == self.killer_moves.moves[ply][0]:
                return self.mo_killer1_score
            if move == self.killer_moves.moves[ply][1]:
                return self.mo_killer2_score
            return min(self.history_table.get_score(board, move), self.history_max_bonus)

        moves.sort(key=score_move, reverse=True)

    def _order_captures(self, board: chess.Board, moves: list):
        def cap_score(move):
            victim   = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            v_type   = victim.piece_type   if victim   else chess.PAWN
            a_type   = attacker.piece_type if attacker else chess.PAWN
            return MVV_LVA_SCORES[v_type * 7 + a_type]
        moves.sort(key=cap_score, reverse=True)

    def can_not_is_zugzwang(self, board: chess.Board) -> bool:
        color = board.turn
        return bool(
            board.pieces(chess.KNIGHT, color) or
            board.pieces(chess.BISHOP, color) or
            board.pieces(chess.ROOK,   color) or
            board.pieces(chess.QUEEN,  color)
        )

    # ──────────────────────────────────────────────────────────────────────────
    # QUIESCENCE SEARCH
    # ──────────────────────────────────────────────────────────────────────────

    def _quiescence(self, board: chess.Board, alpha: int, beta: int) -> int:
        self.timer.nodes += 1
        stand_pat = self.evaluator.evaluate(board)
        if stand_pat >= beta:  return beta
        if alpha < stand_pat:  alpha = stand_pat

        captures = list(board.generate_legal_moves(to_mask=board.occupied_co[not board.turn]))
        self._order_captures(board, captures)

        for move in captures:
            if self.timer.should_stop(): return 0
            board.push(move)
            score = -self._quiescence(board, -beta, -alpha)
            board.pop()
            if score >= beta: return beta
            if score > alpha: alpha = score

        return alpha

    # ──────────────────────────────────────────────────────────────────────────
    # NEGAMAX (SIÊU TỐI ƯU TRA CỨU BIẾN)
    # ──────────────────────────────────────────────────────────────────────────

    def _negamax(self, board: chess.Board, depth: int, alpha: int, beta: int,
                 ply: int, null_move_allowed: bool) -> int:
        self.timer.nodes += 1
        original_alpha = alpha

        # 1. Luật hòa
        if ply > 0 and (board.can_claim_fifty_moves() or board.is_repetition(2)):
            return 0

        # 2. Transposition Table
        hash_key    = chess.polyglot.zobrist_hash(board)
        tt_entry    = self.tt.retrieve(hash_key)
        tt_best_move = None

        if tt_entry:
            tt_best_move = tt_entry.best_move
            if tt_entry.depth >= depth:
                if   tt_entry.flag == TT_EXACT: return tt_entry.score
                elif tt_entry.flag == TT_LOWER: alpha = max(alpha, tt_entry.score)
                elif tt_entry.flag == TT_UPPER: beta  = min(beta,  tt_entry.score)
                if alpha >= beta: return tt_entry.score

        # 3. Quiescence
        if depth <= 0:
            return self._quiescence(board, alpha, beta)

        # 4. Null Move Pruning
        if (null_move_allowed
                and depth >= self.null_move_min_depth
                and not board.is_check()
                and self.can_not_is_zugzwang(board)):
            board.push(chess.Move.null())
            null_score = -self._negamax(
                board,
                depth - 1 - self.null_move_reduction,
                -beta, -beta + 1, ply + 1, False
            )
            board.pop()
            if self.timer.should_stop(): return 0
            if null_score >= beta: return null_score

        # 5. Razoring
        if (depth <= self.razor_depth
                and not board.is_check()
                and abs(alpha) < CHECKMATE_SCORE):
            static_eval = self.evaluator.evaluate(board)
            # Truy cập mảng theo index cực nhanh, phòng vệ mảng nếu depth vượt tầm khai báo
            margin = self.razor_margins[depth] if depth < len(self.razor_margins) else 0
            if static_eval < alpha - margin:
                q_score = self._quiescence(board, alpha, beta)
                if q_score < alpha: return q_score

        # 6. Futility Pruning
        futility_pruning = False
        if (depth <= self.futility_depth
                and not board.is_check()
                and abs(alpha) < CHECKMATE_SCORE
                and abs(beta)  < CHECKMATE_SCORE):
            static_eval = self.evaluator.evaluate(board)
            margin = self.futility_margins[depth] if depth < len(self.futility_margins) else 0
            if static_eval + margin <= alpha:
                futility_pruning = True

        # 7. Sinh & sắp xếp nước đi
        moves = list(board.legal_moves)
        if not moves:
            return NEGATIVE_INFINITY + ply if board.is_check() else 0

        self._order_moves(board, moves, tt_best_move, ply)

        # 8. Move loop
        best_score         = NEGATIVE_INFINITY
        best_move_this_node = None
        moves_searched     = 0

        for move in moves:
            if self.timer.should_stop(): return 0

            is_capture  = board.is_capture(move)
            gives_check = board.gives_check(move)

            # Futility Pruning
            if (futility_pruning and moves_searched > 0
                    and not is_capture and not move.promotion
                    and not gives_check and not board.is_check()):
                continue

            board.push(move)
            is_killer = self.killer_moves.is_killer(move, ply)

            use_lmr = (
                moves_searched >= self.lmr_full_depth_moves
                and depth        >= self.lmr_reduction_limit
                and not is_capture
                and not move.promotion
                and not board.is_check()
                and not gives_check
                and not is_killer
            )

            # PVS + LMR
            if moves_searched == 0:
                score = -self._negamax(board, depth - 1, -beta,      -alpha,     ply + 1, True)

            elif use_lmr:
                reduction = self.lmr_reduction_deep if (depth >= 6 and moves_searched >= 8) else self.lmr_reduction_base
                score = -self._negamax(board, depth - 1 - reduction, -alpha - 1, -alpha,  ply + 1, True)
                if score > alpha:
                    score = -self._negamax(board, depth - 1,          -alpha - 1, -alpha,  ply + 1, True)
                if score > alpha:
                    score = -self._negamax(board, depth - 1,          -beta,      -alpha,  ply + 1, True)

            else:
                score = -self._negamax(board, depth - 1,              -alpha - 1, -alpha,  ply + 1, True)
                if score > alpha:
                    score = -self._negamax(board, depth - 1,          -beta,      -alpha,  ply + 1, True)

            board.pop()
            moves_searched += 1

            if score > best_score:
                best_score          = score
                best_move_this_node = move

            alpha = max(alpha, score)

            if alpha >= beta:
                if not is_capture:
                    self.killer_moves.store(move, ply)
                    self.history_table.record_cutoff(board, move, depth)
                break

        # 9. Lưu TT
        bound = TT_EXACT
        if   best_score <= original_alpha: bound = TT_UPPER
        elif best_score >= beta:           bound = TT_LOWER

        self.tt.store(hash_key, best_score, best_move_this_node, depth, bound)
        return best_score

    # ──────────────────────────────────────────────────────────────────────────
    # ITERATIVE DEEPENING
    # ──────────────────────────────────────────────────────────────────────────

    def search(self, board: chess.Board, depth: int,
               time_limit: float = None) -> tuple[int, chess.Move]:
        self.timer.start(time_limit)
        self.history_table.age()
        best_move  = None
        best_score = NEGATIVE_INFINITY
        prev_score = 0

        for current_depth in range(1, depth + 1):
            if self.timer.should_stop(): break

            if current_depth >= self.aspiration_min_depth:
                delta = self.aspiration_delta
                alpha = prev_score - delta
                beta  = prev_score + delta

                while True:
                    score = self._negamax(board, current_depth, alpha, beta, 0, True)
                    if self.timer.should_stop(): break

                    if   score <= alpha: alpha = max(alpha - delta, NEGATIVE_INFINITY); delta *= 2
                    elif score >= beta:  beta  = min(beta  + delta, INFINITY);          delta *= 2
                    else:                break
            else:
                score = self._negamax(board, current_depth, NEGATIVE_INFINITY, INFINITY, 0, True)

            if not self.timer.should_stop():
                best_score = score
                prev_score = score

                tt_entry = self.tt.retrieve(chess.polyglot.zobrist_hash(board))
                if tt_entry and tt_entry.best_move:
                    best_move = tt_entry.best_move

                self.logger.log_search(
                    best_move, best_score, current_depth,
                    time.perf_counter() - self.timer.start_time
                )

        return best_score, best_move
    

if __name__ == "__main__":
    # Test toàn bộ Searcher với một vị trí phức tạp 
    Evaluator = Evaluator()
    Logger = Logger()
    searcher = Searcher(Evaluator, Logger)
    board = chess.Board("r1bq1rk1/ppp2ppp/2n1pn2/3p4/3P4/2P1PN2/PP1N1PPP/RNBQ1RK1 w - - 0 7")
    score, best_move = searcher.search(board, depth=4, time_limit=5.0)
    print(f"Best Move: {best_move}, Score: {score}")