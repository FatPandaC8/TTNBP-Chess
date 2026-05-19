import chess
from engine.evaluation.constants.piece_square_tables import (
    PHASE_INC,
    OPENING_PST,
    ENDGAME_PST,
    MATERIAL_VALUE
)

class BalancedEvaluator:
    """
    Evaluator cân bằng: PST + material + vài heuristic nhẹ.
    Mạnh hơn Evaluator, nhanh hơn StockfishLike.
    """

    BISHOP_PAIR_BONUS = 30
    ROOK_OPEN_FILE_BONUS = 18
    ROOK_SEMI_OPEN_FILE_BONUS = 10
    PASSED_PAWN_BASE = 18

    def evaluate(self, board: chess.Board) -> int:
        opening_score = 0
        endgame_score = 0
        phase = 0

        for piece_type in range(1, 7):
            phase_weight = PHASE_INC[piece_type]
            op_table = OPENING_PST[piece_type]
            eg_table = ENDGAME_PST[piece_type]
            material = MATERIAL_VALUE[piece_type]

            white_squares = board.pieces(piece_type, chess.WHITE)
            for sq in white_squares:
                opening_score += op_table[sq]
                endgame_score += eg_table[sq]
                phase += phase_weight
            opening_score += material * len(white_squares)
            endgame_score += material * len(white_squares)

            black_squares = board.pieces(piece_type, chess.BLACK)
            for sq in black_squares:
                sq_flipped = sq ^ 56
                opening_score -= op_table[sq_flipped]
                endgame_score -= eg_table[sq_flipped]
                phase += phase_weight
            opening_score -= material * len(black_squares)
            endgame_score -= material * len(black_squares)

        opening_phase = min(phase, 24)
        endgame_phase = 24 - opening_phase
        score = (opening_score * opening_phase + endgame_score * endgame_phase) // 24

        # --- Heuristics nhẹ ---
        score += self._bishop_pair_bonus(board)
        score += self._rook_file_bonus(board)
        score += self._passed_pawn_bonus(board)

        if board.turn == chess.BLACK:
            return -score
        return score

    def _bishop_pair_bonus(self, board: chess.Board) -> int:
        score = 0
        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
            score += self.BISHOP_PAIR_BONUS
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
            score -= self.BISHOP_PAIR_BONUS
        return score

    def _rook_file_bonus(self, board: chess.Board) -> int:
        score = 0
        white_pawns = board.pieces(chess.PAWN, chess.WHITE)
        black_pawns = board.pieces(chess.PAWN, chess.BLACK)

        for sq in board.pieces(chess.ROOK, chess.WHITE):
            f = chess.square_file(sq)
            friendly = any(chess.square_file(p) == f for p in white_pawns)
            enemy = any(chess.square_file(p) == f for p in black_pawns)
            if not friendly and not enemy:
                score += self.ROOK_OPEN_FILE_BONUS
            elif not friendly and enemy:
                score += self.ROOK_SEMI_OPEN_FILE_BONUS

        for sq in board.pieces(chess.ROOK, chess.BLACK):
            f = chess.square_file(sq)
            friendly = any(chess.square_file(p) == f for p in black_pawns)
            enemy = any(chess.square_file(p) == f for p in white_pawns)
            if not friendly and not enemy:
                score -= self.ROOK_OPEN_FILE_BONUS
            elif not friendly and enemy:
                score -= self.ROOK_SEMI_OPEN_FILE_BONUS

        return score

    def _passed_pawn_bonus(self, board: chess.Board) -> int:
        score = 0
        for sq in board.pieces(chess.PAWN, chess.WHITE):
            if self._is_passed_pawn(board, sq, chess.WHITE):
                rank = chess.square_rank(sq)
                score += self.PASSED_PAWN_BASE + rank * 4
        for sq in board.pieces(chess.PAWN, chess.BLACK):
            if self._is_passed_pawn(board, sq, chess.BLACK):
                rank = 7 - chess.square_rank(sq)
                score -= self.PASSED_PAWN_BASE + rank * 4
        return score

    def _is_passed_pawn(self, board, square, color) -> bool:
        enemy_pawns = board.pieces(chess.PAWN, not color)
        file_index = chess.square_file(square)
        rank_index = chess.square_rank(square)

        for e in enemy_pawns:
            ef = chess.square_file(e)
            if abs(ef - file_index) > 1:
                continue
            er = chess.square_rank(e)
            if color == chess.WHITE and er > rank_index:
                return False
            if color == chess.BLACK and er < rank_index:
                return False
        return True