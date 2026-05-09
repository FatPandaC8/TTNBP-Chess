import chess

class ChessBoard:
    def __init__(self):
        self.board = chess.Board()

    # Get information from the chess board
    def legal_moves(self):
        return list(self.board.legal_moves)
    
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
    
    # Actions to modify the chess board
    def push(self, move):
        self.board.push(move)

    def pop(self):
        self.board.pop()
