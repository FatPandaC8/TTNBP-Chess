import chess

ATTACK_WEIGHT_TABLE = [0, 0, 20, 60, 120, 200, 300, 400, 500, 500]

def get_king_ring(board, color):
    king_sq = board.king(color)
    return chess.BB_KING_ATTACKS[king_sq] if king_sq is not None else chess.BB_EMPTY


def king_attack_score(board, attacking_color) -> int:
    opponent = not attacking_color
    king_ring = get_king_ring(board, opponent)

    num_attackers = 0
    total_hits = 0

    for square, piece in board.piece_map().items():
        if piece.color != attacking_color or piece.piece_type == chess.KING:
            continue

        hits = bin(board.attacks(square) & king_ring).count("1")

        if hits > 0:
            num_attackers += 1
            total_hits += hits

    table_score = ATTACK_WEIGHT_TABLE[min(num_attackers, len(ATTACK_WEIGHT_TABLE) - 1)]
    return table_score + total_hits * 5