import chess

from engine.evaluation.features.material import material
from engine.evaluation.features.piece_square import piece_square
from engine.evaluation.features.mobility import mobility_score
from engine.evaluation.features.king_safety import king_attack_score
from engine.evaluation.features.pawn_structure import pawn_structure_score

from engine.utils import (
    is_endgame,
    hanging_penalty,
)

TURN_BONUS = 25
MOBILITY_WEIGHT = 5

def diff(board, feature_func):
    return feature_func(board, chess.WHITE) - feature_func(board, chess.BLACK)

class Evaluator:
    # Vì chỉ có mỗi một cái implementation của Evaluator nên bách implement luôn thay vì viết interface
    def evaluate(self, board, depth=0, debug=False) -> int:
        endgame = is_endgame(board)

        score = 0

        # --- Terminal ---
        if board.is_checkmate():
            return -1_000_000 + depth if board.turn() == chess.WHITE else 1_000_000 - depth


        if board.is_stalemate() or board.is_insufficient_material():
            return 0


        # --- Core features ---
        score += material(board)
        score += piece_square(board, endgame)

        # --- Check pressure ---
        if board.is_check():
            score += -50 if board.turn == chess.WHITE else 50

        # --- Advanced features ---
        score += MOBILITY_WEIGHT * diff(board, mobility_score) 
        score += diff(board, king_attack_score) 
        score += diff(board, pawn_structure_score) 
        score += diff(board, hanging_penalty)

        # --- Tempo ---
        score += TURN_BONUS if board.turn() == chess.WHITE else -TURN_BONUS

        if debug:
            print("material:", material(board))
            print("pst:", piece_square(board, endgame))
            print("mobility:", diff(board, mobility_score))

        return score
