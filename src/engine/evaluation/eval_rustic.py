import chess

from engine.evaluation.constants.piece_square_tables import PHASE_INC, OPENING_PST, ENDGAME_PST


class RusticStyleEvaluator:
    """
    Bộ lượng giá theo phong cách Rustic với tapered PST.
    Mỗi bảng đã bao gồm cả material lẫn positional bonus, nên không cộng material riêng.
    """

    def evaluate(self, board: chess.Board) -> int:
        opening_score = 0
        endgame_score = 0
        phase = 0

        for piece_type in range(1, 7):
            phase_weight = PHASE_INC[piece_type]
            opening_table = OPENING_PST[piece_type]
            endgame_table = ENDGAME_PST[piece_type]

            for square in board.pieces(piece_type, chess.WHITE):
                opening_score += opening_table[square]
                endgame_score += endgame_table[square]
                phase += phase_weight

            for square in board.pieces(piece_type, chess.BLACK):
                flipped_square = square ^ 56
                opening_score -= opening_table[flipped_square]
                endgame_score -= endgame_table[flipped_square]
                phase += phase_weight

        opening_phase = min(phase, 24)
        endgame_phase = 24 - opening_phase
        score = (opening_score * opening_phase + endgame_score * endgame_phase) // 24

        if board.turn == chess.BLACK:
            return -score

        return score