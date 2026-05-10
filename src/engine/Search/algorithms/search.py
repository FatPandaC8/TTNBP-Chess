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
    

    # negamax với alpha-beta pruning và bảng chuyển vị (transposition table) và null move pruning
    def _negamax(self, board: ChessBoard, depth: int, alpha: int, beta: int , ply : int, null_move_allowed: bool) -> int:
        pass
        
        
