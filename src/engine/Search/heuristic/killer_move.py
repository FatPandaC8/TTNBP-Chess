import chess

MAX_PLY = 128
SLOTS   = 2          # 2 killer mỗi ply

class KillerMoves:

    def __init__(self):
        self.moves = [[None, None] for _ in range(MAX_PLY)]

    def store(self, move: chess.Move, ply: int):
        if ply >= MAX_PLY:
            return

        if self.moves[ply][0] == move:
            return

        self.moves[ply][1] = self.moves[ply][0]
        self.moves[ply][0] = move

    def is_killer(self, move: chess.Move, ply: int) -> bool:
        if ply >= MAX_PLY:
            return False
        return move == self.moves[ply][0] or move == self.moves[ply][1]

    def clear(self):
        self.moves = [[None, None] for _ in range(MAX_PLY)]