import chess
from engine.evaluation.constants.piece_square_tables import PST, KING_ENDGAME_TABLE

MIRROR = [chess.square_mirror(sq) for sq in chess.SQUARES]
EMPTY_TABLE = [0] * 64

def piece_square(board, endgame: bool) -> int:
    score = 0

    for square, piece in board.piece_map().items():
        table = (
            KING_ENDGAME_TABLE
            if endgame and piece.piece_type == chess.KING
            else PST.get(piece.piece_type, EMPTY_TABLE)
        )

        if piece.color == chess.WHITE:
            score += table[MIRROR[square]]
        else:
            score -= table[square]

    return score