import chess
import time
from engine.evaluation.eval import Evaluator
from engine.Board.board import ChessBoard
from ..Cache.Tranposition_Table import TranspositionTable  , TT_EXACT, TT_LOWER, TT_UPPER

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

class Searcher:
    def __init__(self, evaluator: Evaluator, tt: TranspositionTable):
        self.evaluator = evaluator
        self.tt = tt
    
    def _quiescence(self, board: ChessBoard, alpha: int, beta: int) -> int:
        stand_pat = self.evaluator.evaluate(board.board)
        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        for move in board.generate_legal_captures():
            board.push(move)
            score = -self._quiescence(board, -beta, -alpha)
            board.pop()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha
    

    def can_not_is_zugzwang(self, board: ChessBoard) -> bool:
        """Kiểm tra xem có phải là tình huống zugzwang hay không"""
        color = board.turn
        # Nếu còn Mã, Tượng, Xe, Hậu -> không phải tàn cuộc thuần
        return bool(
            board.pieces(chess.KNIGHT, color)
            or board.pieces(chess.BISHOP, color)
            or board.pieces(chess.ROOK, color)
            or board.pieces(chess.QUEEN, color)
        )
    

    def _order_moves(self, board: ChessBoard, moves: list, tt_move: chess.Move, ply: int):
        pass  # TODO: Thêm move ordering heuristics (ví dụ: MVV/LVA, killer moves, history heuristic)



    # negamax với alpha-beta pruning và bảng chuyển vị (transposition table) và null move pruning

    def _negamax(self, board: ChessBoard, depth: int, alpha: int, beta: int , ply : int, null_move_allowed: bool, NULL_MOVE_MIN_DEPTH: int, NULL_MOVE_REDUCTION: int) -> int:
        self.timer.nodes += 1
        orginal_alpha = alpha
        if ply > 0 and (board.can_claim_fifty_moves() or board.is_repetition(2)):
            return 0  # Hòa do lặp lại hoặc luật 50 nước
        hash_key = chess.polyglot.zobrist_hash(board.board)
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
                

        if depth == 0:
            return self._quiescence(board, alpha, beta)
        
        # Null Move Pruning
        if (null_move_allowed and depth >= NULL_MOVE_MIN_DEPTH 
            and not board.board.is_check() and self.can_not_is_zugzwang(board)):
            board.push(chess.Move.null())

            null_score = -self._negamax(board, depth - 1 - NULL_MOVE_REDUCTION, -beta, -beta + 1, ply + 1, False, NULL_MOVE_MIN_DEPTH, NULL_MOVE_REDUCTION)
            board.pop()
            if self.timer.should_stop():
                return 0
            
            if null_score >= beta:
                return null_score
            
        moves = board.generate_legal_moves()
        if not moves:
            # Nếu không có nước đi hợp lệ, kiểm tra xem có phải là checkmate hay stalemate
            if board.board.is_check():
                return -999999 + ply  # Checkmate, trừ đi ply để ưu tiên chiến thắng nhanh hơn
            else:
                return 0  # Stalemate, hòa
            
        self._order_moves(board, moves, tt_best_move, ply)
        best_score = -999999
        best_move_this_node = None
        moves_searched = 0
        pass
        


