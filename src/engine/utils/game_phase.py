import chess
from engine.evaluation.constants.piece_values import PIECE_VALUES

def is_endgame(board) -> bool:
    queens = board.pieces(chess.QUEEN, chess.WHITE) | board.pieces(chess.QUEEN, chess.BLACK)

    if len(queens) == 0:
        return True

    for color in [chess.WHITE, chess.BLACK]:
        material = sum(
            len(board.pieces(pt, color)) * PIECE_VALUES[pt]
            for pt in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]
        )
        if material < 1300:
            return True

    return False


def get_game_phase(board) -> str:
    queens = board.pieces(chess.QUEEN, chess.WHITE) | board.pieces(chess.QUEEN, chess.BLACK)

    if len(queens) == 0 or is_endgame(board):
        return "endgame"

    move_num = board.fullmove_number()

    if move_num < 10:
        return "opening"
    elif move_num < 40:
        return "middlegame"
    else:
        return "endgame"