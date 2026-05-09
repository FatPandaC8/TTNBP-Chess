import chess
import time
from engine.evaluation.constants.piece_square_tables import PHASE_INC, OPENING_PST, ENDGAME_PST

class Evaluator:
    """
    Bộ lượng giá tĩnh (Static Evaluation) tối ưu bằng Python.
    Sử dụng Tapered Evaluation (Nội suy Khai cuộc - Tàn cuộc) và Piece-Square Tables.
    """
    
    def evaluate(self, board: chess.Board) -> int:
        opening_score = 0
        endgame_score = 0
        phase = 0

        # Tối ưu hóa: Lặp qua từng LOẠI QUÂN thay vì lặp qua 64 ô
        for piece_type in range(1, 7): # Từ PAWN (1) đến KING (6)
            phase_weight = PHASE_INC[piece_type]
            op_table = OPENING_PST[piece_type]
            eg_table = ENDGAME_PST[piece_type]

            # 1. QUÂN TRẮNG (Không cần lật bàn cờ)
            # board.pieces() trả về một SquareSet cực nhanh (Bitboard)
            for sq in board.pieces(piece_type, chess.WHITE):
                opening_score += op_table[sq]
                endgame_score += eg_table[sq]
                phase += phase_weight

            # 2. QUÂN ĐEN (Cần lật bàn cờ)
            for sq in board.pieces(piece_type, chess.BLACK):
                # Phép XOR 56 giúp đảo lộn ô cờ (VD: a8 (56) -> a1 (0))
                sq_flipped = sq ^ 56
                
                # Trừ điểm vì Đen có lợi thế ở ô này
                opening_score -= op_table[sq_flipped]
                endgame_score -= eg_table[sq_flipped]
                phase += phase_weight

        # 3. Tính toán Tapered Evaluation (Nội suy)
        # Bóp phase về giới hạn tối đa là 24
        opening_phase = min(phase, 24)
        endgame_phase = 24 - opening_phase

        # Tính tổng điểm nội suy. Trắng dương, Đen âm.
        score = (opening_score * opening_phase + endgame_score * endgame_phase) // 24

        # 4. Trả về điểm theo góc nhìn của người đang đến lượt (Active Color)
        # Trong thuật toán NegaMax, người đang đi luôn muốn điểm dương.
        if board.turn == chess.BLACK:
            return -score
        else:
            return score


if __name__ == "__main__":
    evaluator = Evaluator()
    # FEN giống hệt bài test của bạn
    board = chess.Board("rnbqkb1r/p1pp1ppp/1p3n2/4N3/4P3/8/PPPP1PPP/RNBQKB1R w KQkq - 0 4")
    
    start_time = time.perf_counter()
    
    # Chạy thử lượng giá
    score = evaluator.evaluate(board)
    
    duration = time.perf_counter() - start_time
    
    print(f"Evaluation Score: {score}")
    # Đổi sang format giây / mili-giây
    print(f"Test took: {duration:.6f} seconds ({duration * 1000:.3f} ms)")