import chess
from engine.evaluation.constants.piece_values import PIECE_VALUES

def hanging_penalty(board, color) -> int:
    penalty = 0
    opponent = not color

    for square, piece in board.piece_map().items():
        if piece.color != color or piece.piece_type == chess.KING:
            continue

        if board.is_attacked_by(opponent, square) and \
           not board.is_attacked_by(color, square):
            penalty -= PIECE_VALUES[piece.piece_type] // 4

    return penalty