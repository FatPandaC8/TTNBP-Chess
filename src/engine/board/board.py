import chess

class ChessBoard:
    def __init__(self):
        self.board = chess.Board()

    # Get information from the chess board
    def legal_moves(self):
        return self.board.legal_moves
    
    def turn(self):
        return self.board.turn
    
    def is_game_over(self):
        return self.board.is_game_over()
    
    def fen(self):
        return self.board.fen()
    
    def result(self):
        return self.board.result()
    
    def copy(self):
        new = ChessBoard()
        new.board = self.board.copy()
        return new
    
    def pieces(self, piece_type, color):
        return self.board.pieces(piece_type, color)
    
    def is_checkmate(self):
        return self.board.is_checkmate()

    def is_stalemate(self):
        return self.board.is_stalemate()

    def piece_map(self):
        return self.board.piece_map()

    def piece_at(self, square):
        return self.board.piece_at(square)

    def king(self, color):
        return self.board.king(color)

    def attacks(self, square):
        return self.board.attacks(square)

    def is_attacked_by(self, color, square):
        return self.board.is_attacked_by(color, square)

    def fullmove_number(self):
        return self.board.fullmove_number
    
    def is_insufficient_material(self):
        return self.board.is_insufficient_material()
    
    def is_check(self):
        return self.board.is_check()
    
    # Actions to modify the chess board
    def push(self, move):
        self.board.push(move)

    def pop(self):
        self.board.pop()
