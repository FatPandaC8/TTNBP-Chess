import chess

def are_rooks_connected(board, color) -> bool:
    rooks = list(board.pieces(chess.ROOK, color))
    if len(rooks) < 2:
        return False

    for i, r1 in enumerate(rooks):
        for r2 in rooks[i+1:]:
            if chess.square_rank(r1) == chess.square_rank(r2):
                return True
            if chess.square_file(r1) == chess.square_file(r2):
                return True

    return False


def count_pieces_developed(board, color) -> int:
    count = 0
    back_rank = 0 if color == chess.WHITE else 7

    for square in range(64):
        piece = board.piece_at(square)
        if not piece or piece.color != color:
            continue

        if piece.piece_type in [chess.PAWN, chess.KING]:
            continue

        if chess.square_rank(square) != back_rank:
            count += 1

    return count