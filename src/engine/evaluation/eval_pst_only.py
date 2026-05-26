import chess
from engine.evaluation.constants.piece_square_tables import PHASE_INC, OPENING_PST, ENDGAME_PST

class PSTOnlyEvaluator:
    """
    Bộ lượng giá chỉ dùng Piece-Square Tables (PST), không tính Material Value.
    Dùng để so sánh với Evaluator đầy đủ.
    """
    
    def evaluate(self, board: chess.Board) -> int:
        opening_score = 0
        endgame_score = 0
        phase = 0

        # Lặp qua từng LOẠI QUÂN
        for piece_type in range(1, 7):  # Từ PAWN (1) đến KING (6)
            phase_weight = PHASE_INC[piece_type]
            op_table = OPENING_PST[piece_type]
            eg_table = ENDGAME_PST[piece_type]

            # 1. QUÂN TRẮNG
            white_squares = board.pieces(piece_type, chess.WHITE)
            for sq in white_squares:
                opening_score += op_table[sq]
                endgame_score += eg_table[sq]
                phase += phase_weight

            # 2. QUÂN ĐEN
            black_squares = board.pieces(piece_type, chess.BLACK)
            for sq in black_squares:
                sq_flipped = sq ^ 56
                opening_score -= op_table[sq_flipped]
                endgame_score -= eg_table[sq_flipped]
                phase += phase_weight

        # 3. Tính Tapered Evaluation
        opening_phase = min(phase, 24)
        endgame_phase = 24 - opening_phase

        score = (opening_score * opening_phase + endgame_score * endgame_phase) // 24

        # 4. Trả về theo góc nhìn Active Color
        if board.turn == chess.BLACK:
            return -score
        else:
            return score
