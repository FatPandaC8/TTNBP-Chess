import chess
import time
from engine.evaluation.eval import Evaluator
from ..cache.tranposition_table import TranspositionTable  , TT_EXACT, TT_LOWER, TT_UPPER
import chess.polyglot
from  ..heuristic.history import HistoryTable
from ..heuristic.killer_move import KillerMoves
from engine.search.interface import BaseSearch
from engine.utils.logger import Logger

INFINITY = 9999999
NEGATIVE_INFINITY = -INFINITY
CHECKMATE_SCORE = 9000000



LMR_FULL_DEPTH_MOVES = 4
LMR_REDUCTION_LIMIT = 3
NULL_MOVE_REDUCTION = 3
NULL_MOVE_MIN_DEPTH = 3
ASPIRATION_MIN_DEPTH = 4
ASPIRATION_DELTA = 50

class SearchTimer:
    """Quản lý thời gian và đếm Nodes"""
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
        
        self.tt = TranspositionTable()
        self.timer = SearchTimer()
        self.history_table = HistoryTable()
        self.killer_moves = KillerMoves()
        
    def _order_moves(self, board: chess.Board, moves: list, tt_move: chess.Move, ply: int):
        pass  # TODO: Thêm move ordering heuristics (ví dụ: MVV/LVA, killer moves, history heuristic)
    
    
    def _order_captures(self, board: chess.Board, moves: list):
        pass  # TODO: Sắp xếp nước bắt quân theo MVV/LVA

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
    

    def can_not_is_zugzwang(self, board: chess.Board) -> bool:
        """Kiểm tra xem có phải là tình huống zugzwang hay không"""
        color = board.turn
        # Nếu còn Mã, Tượng, Xe, Hậu -> không phải tàn cuộc thuần
        return bool(
            board.pieces(chess.KNIGHT, color)
            or board.pieces(chess.BISHOP, color)
            or board.pieces(chess.ROOK, color)
            or board.pieces(chess.QUEEN, color)
        )
    

    # negamax với alpha-beta pruning và bảng chuyển vị (transposition table) và null move pruning

    def _negamax(self, board: chess.Board, depth: int, alpha: int, beta: int , ply : int, null_move_allowed: bool) -> int:
        self.timer.nodes += 1
        original_alpha = alpha
        if ply > 0 and (board.can_claim_fifty_moves() or board.is_repetition(2)):
            return 0  # Hòa do lặp lại hoặc luật 50 nước
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
                

        if depth <= 0:
            return self._quiescence(board, alpha, beta)
        
        # Null Move Pruning
        if (null_move_allowed and depth >= NULL_MOVE_MIN_DEPTH 
            and not board.is_check() and self.can_not_is_zugzwang(board)):
            board.push(chess.Move.null())

            null_score = -self._negamax(board, depth - 1 - NULL_MOVE_REDUCTION, -beta, -beta + 1, ply + 1, False)
            board.pop()
            if self.timer.should_stop():
                return 0
            
            if null_score >= beta:
                return null_score
            
        moves = list(board.legal_moves)
        if not moves:
            # Nếu không có nước đi hợp lệ, kiểm tra xem có phải là checkmate hay stalemate
            if board.is_check():
                return NEGATIVE_INFINITY + ply  # Checkmate, trừ đi ply để ưu tiên chiến thắng nhanh hơn
            else:
                return 0  # Stalemate, hòa
            
        self._order_moves(board, moves, tt_best_move, ply)
        best_score = NEGATIVE_INFINITY
        best_move_this_node = None
        moves_searched = 0 # Đếm số nước đã xét (dùng cho LMR)
        
        for move in moves:
            if self.timer.should_stop():
                return 0
            is_capture = board.is_capture(move)
            
            gives_check = board.gives_check(move)
            
            board.push(move)
            # LATE MOVE REDUCTION (LMR) 
            # Ý tưởng: Các nước đi xếp SAU (late moves) thường tệ hơn.
            # Ta search chúng với depth nhỏ hơn. Nếu chúng vẫn tốt hơn alpha,
            # ta mới search lại với full depth.
            #
            # Điều kiện để KHÔNG giảm depth (tức là search full):
            # - Nước đầu tiên (moves_searched < LMR_FULL_DEPTH_MOVES)
            # - depth chưa đủ sâu
            # - Nước bắt quân (capture)
            # - Nước phong cấp (promotion)
            # - Đang chiếu hoặc nước này tạo chiếu
            # - Killer move (nước đã từng tạo beta-cutoff)

            is_killer = False
            try:
                if move == self.killer_moves.moves[ply][0] or move == self.killer_moves.moves[ply][1]:
                    is_killer = True
            except IndexError:
                pass

            use_lmr = (moves_searched >= LMR_FULL_DEPTH_MOVES 
                       and depth >= LMR_REDUCTION_LIMIT 
                       and not is_capture 
                       and not move.promotion
                       and not board.is_check()
                       and not gives_check
                       and not is_killer)
            

            # PVS: Nước đầu tiên — search full window
            # Move ordering đã xếp nước tốt nhất lên đầu (hash move / TT move).
            # Search full [alpha, beta] để lấy điểm chuẩn PV.
            if moves_searched == 0:
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, True)
            
            elif use_lmr:
                #LMR + PVS: late move → null window + reduced depth
                reduction = 1
                if depth >= 6 and moves_searched >= 8:
                    reduction = 2


                 # Bước 1: null window, depth giảm
                score = -self._negamax(board, depth - 1 - reduction, -alpha - 1, -alpha, ply + 1, True)

                # Bước 2: vượt alpha với depth giảm → re-search full depth, null window
                if score > alpha :
                    score = -self._negamax(board, depth - 1, -alpha - 1, -alpha, ply + 1, True)

                # Bước 3: vẫn vượt alpha → re-search full window (PVS fail-high)
                if score > alpha:
                    score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, True)
            else:
                # PVS: nước sau thông thường → null window trước
                # Giả định nước đầu tốt nhất, nước sau chỉ cần chứng minh tệ hơn alpha.
                score = -self._negamax(board, depth - 1,  -alpha - 1, -alpha, ply + 1, True)

                # Nếu bất ngờ tốt hơn (PVS fail-high) → re-search full window
                if score > alpha:
                    score = -self._negamax(board, depth - 1,  -beta, -alpha, ply + 1, True)

            board.pop()
            moves_searched += 1

            if score > best_score:
                best_score = score
                best_move_this_node = move

            alpha = max(alpha, score)
            if alpha >= beta:
                if not is_capture:
                    self.killer_moves.store(move, ply)
                    self.history_table.record_cutoff(board, move, depth)
                break

        bound = TT_EXACT
        if best_score <= original_alpha:
            bound = TT_UPPER
        elif best_score >= beta:
            bound = TT_LOWER

        self.tt.store(hash_key, best_score, best_move_this_node, depth, bound)
        return best_score
    
    def search(self, board: chess.Board, depth: int, time_limit: float=None) -> tuple[int, chess.Move]:
        """
        Iterative Deepening + Aspiration Windows.

        Ý tưởng Aspiration Windows:
        - Thay vì search với cửa sổ [-INF, +INF], ta dùng cửa sổ hẹp
          [prev_score - delta, prev_score + delta].
        - Nếu kết quả nằm ngoài cửa sổ (fail-low hoặc fail-high),
          ta mở rộng cửa sổ ra và search lại.
        - Lợi ích: Cắt tỉa nhiều hơn khi score nằm trong cửa sổ.
        - Rủi ro: Phải search lại nếu score nằm ngoài (nhưng rất hiếm).
        """

        self.timer.start(time_limit)
        self.history_table.age()  
        best_move = None
        best_score = NEGATIVE_INFINITY
        prev_score = 0

        for current_depth in range(1, depth + 1):
            if self.timer.should_stop():
                break
            if current_depth >= ASPIRATION_MIN_DEPTH:
                # Bắt đầu với cửa sổ hẹp quanh score trước
                alpha = prev_score - ASPIRATION_DELTA
                beta  = prev_score + ASPIRATION_DELTA
                delta = ASPIRATION_DELTA

                while True:
                    score = self._negamax(board, current_depth, alpha, beta, 0, True)

                    if self.timer.should_stop():
                        break

                    if score <= alpha:
                        # Fail-low: mở rộng cửa sổ về phía âm
                        alpha = max(alpha - delta, NEGATIVE_INFINITY)
                        delta *= 2  # Tăng delta mỗi lần fail
                    elif score >= beta:
                        # Fail-high: mở rộng cửa sổ về phía dương
                        beta = min(beta + delta, INFINITY)
                        delta *= 2
                    else:
                        # Nằm trong cửa sổ -> kết quả hợp lệ
                        break
            else:
                # Depth thấp (1-3): dùng cửa sổ full để tránh fail sớm
                score = self._negamax(board, current_depth, NEGATIVE_INFINITY, INFINITY, 0, True)

            if not self.timer.should_stop():
                best_score = score
                prev_score = score  # Lưu lại để depth tiếp theo dùng

                tt_entry = self.tt.retrieve(chess.polyglot.zobrist_hash(board))
                if tt_entry and tt_entry.best_move:
                    best_move = tt_entry.best_move

                print(f"info depth {current_depth} score cp {best_score} " f"nodes {self.timer.nodes} pv {best_move}")

        return best_score, best_move
