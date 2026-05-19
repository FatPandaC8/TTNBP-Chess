import chess
import time
import chess.polyglot
from engine.evaluation.eval import Evaluator
from engine.search.context import SearchContext
from engine.search.interface import BaseSearch
from engine.utils.logger import Logger
from ..cache.tranposition_table import TranspositionTable, TT_EXACT, TT_LOWER, TT_UPPER
from ..heuristic.history import HistoryTable
from ..heuristic.killer_move import KillerMoves

# ==============================================================================
# HẰNG SỐ ĐỊNH HÌNH ENGINE (Cố định)
# ==============================================================================
INFINITY = 9999999
NEGATIVE_INFINITY = -INFINITY
CHECKMATE_SCORE = 9000000

# Điểm số MVV-LVA phục vụ sắp xếp nước đi bắt quân
MVV_LVA_SCORES = [
    0, 0, 0, 0, 0, 0, 
    50, 51, 52, 53, 54, 55,  # Tốt bắt...
    40, 41, 42, 43, 44, 45,  # Mã bắt...
    30, 31, 32, 33, 34, 35,  # Tượng bắt...
    20, 21, 22, 23, 24, 25,  # Xe bắt...
    10, 11, 12, 13, 14, 15   # Hậu bắt...
]

class SearchTimer:
    """Bộ đếm thời gian và quản lý tài nguyên Nodes độc lập."""
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
        # Cứ sau 2048 nodes thì check thời gian một lần để giảm chi phí gọi hàm time()
        if (self.nodes & 2047) == 0:
            return (time.perf_counter() - self.start_time) >= self.time_limit
        return False


class Searcher(BaseSearch):
    def __init__(self, evaluator: Evaluator, logger: Logger):
        super().__init__(
            context=SearchContext(evaluator=evaluator, logger=logger)
        )
        
        self.tt = TranspositionTable()
        self.timer = SearchTimer()
        self.history_table = HistoryTable()
        self.killer_moves = KillerMoves()

        # ==============================================================================
        # CÁC THAM SỐ TÌM KIẾM (Các con số này sẽ được mang đi TUNE bằng SPSA)
        # ==============================================================================
        self.config = {
            "LMR_FULL_DEPTH_MOVES": 4,
            "LMR_REDUCTION_LIMIT": 3,
            "NULL_MOVE_MIN_DEPTH": 3,
            "NULL_MOVE_REDUCTION": 3,
            "ASPIRATION_MIN_DEPTH": 4,
            "ASPIRATION_DELTA": 50,
            
            # Cắt tỉa Razoring
            "RAZOR_DEPTH": 3,
            "RAZOR_MARGIN_D1": 300,
            "RAZOR_MARGIN_D2": 500,
            "RAZOR_MARGIN_D3": 900,
            
            # Cắt tỉa Futility
            "FUTILITY_DEPTH": 2,
            "FUTILITY_MARGIN_D1": 150,
            "FUTILITY_MARGIN_D2": 300
        }

    # ──────────────────────────────────────────────────────────────────────────
    # CÁC HÀM TRỢ LÝ: MOVE ORDERING & UTILS
    # ──────────────────────────────────────────────────────────────────────────

    def _order_moves(self, board: chess.Board, moves: list, tt_move: chess.Move, ply: int):
        """Ưu tiên nước đi tốt lên đầu để tối ưu hóa Alpha-Beta Cutoff."""
        color_idx = 1 if board.turn == chess.BLACK else 0

        def score_move(move):
            if move == tt_move:
                return 1000000  # Nước đi từ bảng chuyển vị luôn là số 1
            if board.is_capture(move):
                victim = board.piece_at(move.to_square)
                attacker = board.piece_at(move.from_square)
                v_type = victim.piece_type if victim else chess.PAWN
                a_type = attacker.piece_type if attacker else chess.PAWN
                return 100000 + MVV_LVA_SCORES[v_type * 6 + a_type]
            if move.promotion:
                return 80000 + move.promotion * 100
            if move == self.killer_moves.moves[ply][0]:
                return 90000
            elif move == self.killer_moves.moves[ply][1]:
                return 80000
            return self.history_table.get_score(board, move) 

        moves.sort(key=score_move, reverse=True)
    
    def _order_captures(self, board: chess.Board, moves: list):
        """Sắp xếp riêng các nước ăn quân cho Quiescence Search."""
        def cap_score(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            v_type = victim.piece_type if victim else chess.PAWN
            a_type = attacker.piece_type if attacker else chess.PAWN
            return MVV_LVA_SCORES[v_type * 6 + a_type]
        moves.sort(key=cap_score, reverse=True)

    def can_not_is_zugzwang(self, board: chess.Board) -> bool:
        """Tránh Null Move Pruning trong tàn cuộc thuần King + Pawn để tránh tự sát (Zugzwang)."""
        color = board.turn
        return bool(
            board.pieces(chess.KNIGHT, color) or
            board.pieces(chess.BISHOP, color) or
            board.pieces(chess.ROOK, color) or
            board.pieces(chess.QUEEN, color)
        )

    # ──────────────────────────────────────────────────────────────────────────
    # QUIESCENCE SEARCH (Tìm kiếm tĩnh)
    # ──────────────────────────────────────────────────────────────────────────

    def _quiescence(self, board: chess.Board, alpha: int, beta: int) -> int:
        """Hạn chế hiệu ứng chân trời (Horizon Effect) bằng cách giải quyết hết xung đột ăn quân."""
        self.timer.nodes += 1
        
        # Đứng yên tại chỗ (Stand-pat): Giả định không ăn quân nữa thì thế cờ đáng giá bao nhiêu?
        stand_pat = self.evaluator.evaluate(board)
        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        # Chỉ sinh ra các nước đi ăn quân hợp lệ
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

    # ──────────────────────────────────────────────────────────────────────────
    # HÀM SEARCH CHÍNH: NEGAMAX
    # ──────────────────────────────────────────────────────────────────────────

    def _negamax(self, board: chess.Board, depth: int, alpha: int, beta: int, ply: int, null_move_allowed: bool) -> int:
        self.timer.nodes += 1
        original_alpha = alpha

        # 1. KIỂM TRA LUẬT HÒA CỜ
        if ply > 0 and (board.can_claim_fifty_moves() or board.is_repetition(2)):
            return 0  

        # 2. TRA CỨU BẢNG CHUYỂN VỊ (TRANSPOSITION TABLE)
        hash_key = chess.polyglot.zobrist_hash(board)
        tt_entry = self.tt.retrieve(hash_key)
        tt_best_move = None
        
        if tt_entry:
            tt_best_move = tt_entry.best_move
            if tt_entry.depth >= depth:
                if tt_entry.flag == TT_EXACT:
                    return tt_entry.score
                elif tt_entry.flag == TT_LOWER:
                    alpha = max(alpha, tt_entry.score)
                elif tt_entry.flag == TT_UPPER:
                    beta = min(beta, tt_entry.score)
                if alpha >= beta:
                    return tt_entry.score

        # 3. ĐIỀU KIỆN DỪNG TÌM KIẾM SÂU -> CHUYỂN SANG SEARCH TĨNH
        if depth <= 0:
            return self._quiescence(board, alpha, beta)
        
        # 4. NULL MOVE PRUNING (Cắt tỉa nước đi trống)
        # Nếu nhường lượt mà đối thủ vẫn không làm gì được ta -> thế cờ quá mạnh -> Cắt!
        if (null_move_allowed and depth >= self.config["NULL_MOVE_MIN_DEPTH"] 
                and not board.is_check() and self.can_not_is_zugzwang(board)):
            board.push(chess.Move.null())
            null_score = -self._negamax(board, depth - 1 - self.config["NULL_MOVE_REDUCTION"], -beta, -beta + 1, ply + 1, False)
            board.pop()
            
            if self.timer.should_stop(): return 0
            if null_score >= beta: return null_score

        # 5. RAZORING (Cắt tỉa thế cờ quá nát ở depth thấp)
        if (depth <= self.config["RAZOR_DEPTH"] and not board.is_check() and abs(alpha) < CHECKMATE_SCORE):
            static_eval = self.evaluator.evaluate(board)
            
            # Lấy margin động theo depth
            margin = self.config[f"RAZOR_MARGIN_D{depth}"]
            if static_eval < alpha - margin:
                q_score = self._quiescence(board, alpha, beta)
                if q_score < alpha:
                    return q_score   # Thua quá sâu, qsearch không cứu được -> Fail-low sớm.

        # 6. FUTILITY PRUNING PREPARATION (Chuẩn bị cắt tỉa vô vọng)
        futility_pruning = False
        if (depth <= self.config["FUTILITY_DEPTH"] and not board.is_check() 
                and abs(alpha) < CHECKMATE_SCORE and abs(beta) < CHECKMATE_SCORE):
            static_eval = self.evaluator.evaluate(board)
            margin = self.config[f"FUTILITY_MARGIN_D{depth}"]
            
            # Nếu điểm tĩnh + biên độ vẫn không chạm tới nổi alpha -> Đánh dấu để tỉa các nước yếu
            if static_eval + margin <= alpha:
                futility_pruning = True

        # 7. SINH NƯỚC ĐI VÀ SẮP XẾP
        moves = list(board.legal_moves)
        if not moves:
            if board.is_check():
                return NEGATIVE_INFINITY + ply  # Thua cuộc, ưu tiên chiếu sát nhanh (ply nhỏ)
            return 0  # Hòa cờ (Stalemate)
            
        self._order_moves(board, moves, tt_best_move, ply)
        
        # 8. VÒNG LẶP DUYỆT CÁC NƯỚC ĐI (MOVE LOOP)
        best_score = NEGATIVE_INFINITY
        best_move_this_node = None
        moves_searched = 0 
        
        for move in moves:
            if self.timer.should_stop(): return 0
            
            is_capture = board.is_capture(move)
            gives_check = board.gives_check(move)
            
            # Áp dụng Futility Pruning: Bỏ qua nước đi không mang tính chiến thuật (không ăn quân, không chiếu...)
            if (futility_pruning and moves_searched > 0 
                    and not is_capture and not move.promotion and not gives_check and not board.is_check()):
                continue   

            board.push(move)

            # Phân tích điều kiện Late Move Reduction (LMR)
            is_killer = self.killer_moves.is_killer(move, ply)

            use_lmr = (moves_searched >= self.config["LMR_FULL_DEPTH_MOVES"] 
                       and depth >= self.config["LMR_REDUCTION_LIMIT"] 
                       and not is_capture and not move.promotion
                       and not board.is_check() and not gives_check and not is_killer)
            
            # --- CHIẾN LƯỢC TÌM KIẾM (PVS & LMR) ---
            if moves_searched == 0:
                # Nước đi đầu tiên (hi vọng là tốt nhất) -> Search Full Cửa Sổ
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, True)
            
            elif use_lmr:
                # Nước đi muộn + Không quan trọng -> Thu hẹp cửa sổ + Giảm độ sâu
                reduction = 2 if (depth >= 6 and moves_searched >= 8) else 1
                score = -self._negamax(board, depth - 1 - reduction, -alpha - 1, -alpha, ply + 1, True)

                # Nếu vô tình điểm vượt alpha -> Phải search lại (Re-search)
                if score > alpha:
                    score = -self._negamax(board, depth - 1, -alpha - 1, -alpha, ply + 1, True)
                if score > alpha:
                    score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, True)
            else:
                # Các nước đi sau thông thường -> Test nhanh bằng Null Window
                score = -self._negamax(board, depth - 1, -alpha - 1, -alpha, ply + 1, True)
                if score > alpha:
                    score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, True)

            board.pop()
            moves_searched += 1

            # Ghi nhận kết quả tốt nhất
            if score > best_score:
                best_score = score
                best_move_this_node = move

            alpha = max(alpha, score)
            
            # BETA CUTOFF: Đối thủ sẽ không cho phép ta đi vào nhánh này -> Cắt luôn!
            if alpha >= beta:
                if not is_capture:
                    self.killer_moves.store(move, ply)
                    self.history_table.record_cutoff(board, move, depth)
                break

        # 9. LƯU KẾT QUẢ VÀO BẢNG CHUYỂN VỊ TRƯỚC KHI THOÁT HÀM
        bound = TT_EXACT
        if best_score <= original_alpha:  bound = TT_UPPER
        elif best_score >= beta:          bound = TT_LOWER

        self.tt.store(hash_key, best_score, best_move_this_node, depth, bound)
        return best_score
    
    # ──────────────────────────────────────────────────────────────────────────
    # SƠ ĐỒ DUYỆT ĐỘ SÂU TĂNG DẦN (ITERATIVE DEEPENING)
    # ──────────────────────────────────────────────────────────────────────────

    def search(self, board: chess.Board, depth: int, time_limit: float=None) -> tuple[int, chess.Move]:
        self.timer.start(time_limit)
        self.history_table.age()  
        best_move = None
        best_score = NEGATIVE_INFINITY
        prev_score = 0

        for current_depth in range(1, depth + 1):
            if self.timer.should_stop(): break
            
            # Sử dụng Aspiration Windows ở độ sâu cao để bóp hẹp cửa sổ tìm kiếm alpha/beta
            if current_depth >= self.config["ASPIRATION_MIN_DEPTH"]:
                alpha = prev_score - self.config["ASPIRATION_DELTA"]
                beta  = prev_score + self.config["ASPIRATION_DELTA"]
                delta = self.config["ASPIRATION_DELTA"]

                while True:
                    score = self._negamax(board, current_depth, alpha, beta, 0, True)
                    if self.timer.should_stop(): break

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

                self.logger.log_search(best_move, best_score, current_depth, time.perf_counter() - self.timer.start_time)

        return best_score, best_move
    