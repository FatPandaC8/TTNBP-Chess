import chess

def pawn_structure_score(board, color) -> int:
    score = 0
    pawns = board.pieces(chess.PAWN, color)
    files = [chess.square_file(sq) for sq in pawns]

    for f in range(8):
        count = files.count(f)

        if count > 1:
            score -= 20 * (count - 1)

        if count > 0:
            has_neighbor = (
                (f > 0 and files.count(f - 1) > 0) or
                (f < 7 and files.count(f + 1) > 0)
            )
            if not has_neighbor:
                score -= 15

    return score