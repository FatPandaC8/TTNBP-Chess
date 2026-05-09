import chess
from engine.board.board import ChessBoard
from engine.evaluation.features.material import material
from engine.evaluation.features.piece_square import piece_square
from engine.evaluation.features.mobility import mobility_score
from engine.evaluation.features.king_safety import king_attack_score
from engine.evaluation.features.pawn_structure import pawn_structure_score
from engine.utils.loader import load_config
from engine.utils import (
    is_endgame,
    hanging_penalty,
)

def diff(board, feature_func):
    return feature_func(board, chess.WHITE) - feature_func(board, chess.BLACK)

class Evaluator:
    def __init__(self, config_path):
        self.cfg = load_config(config_path)

    # Vì chỉ có mỗi một cái implementation của Evaluator nên bách implement luôn thay vì viết interface
    def evaluate(self, board: ChessBoard, depth=0, debug=False) -> int:
        endgame = is_endgame(board)

        score = 0

        # Terminal 
        checkmate_penal = self.cfg["checkmate_penalty"]
        if board.is_checkmate():
            return -check_penal + depth if board.turn() == chess.WHITE else checkmate_penal - depth


        if board.is_stalemate() or board.is_insufficient_material():
            return 0
        

        # Core features 
        score += material(board)
        score += piece_square(board, endgame)


        # Check pressure 
        check_penal = self.cfg["check_penalty"]
        if board.is_check():
            score += check_penal if board.turn == chess.WHITE else check_penal


        # Advanced features 
        score += self.cfg["mobility_weight"] * diff(board, mobility_score) 
        score += self.cfg["features"]["king_attack"] * diff(board, king_attack_score) 
        score += self.cfg["features"]["pawn_structure"] * diff(board, pawn_structure_score) 
        score += self.cfg["features"]["hanging"] * diff(board, hanging_penalty)


        # Tempo 
        tempo = self.cfg["turn_bonus"] 
        score += tempo if board.turn() == chess.WHITE else -tempo


        if debug:
            print("material:", material(board))
            print("pst:", piece_square(board, endgame))
            print("mobility:", diff(board, mobility_score))

        return score
