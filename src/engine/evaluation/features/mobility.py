def mobility_score(board, color) -> int:
    score = 0

    for move in board.legal_moves():
        piece = board.piece_at(move.from_square)
        if piece and piece.color == color:
            score += 1

    return score