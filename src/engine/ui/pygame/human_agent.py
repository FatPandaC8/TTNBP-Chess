import chess
from engine.agents.interface import Agent
from engine.ui.pygame.input_handler import InputHandler

class HumanAgent(Agent):
    """Human player.

    Owns the full interaction flow: click-to-select, click-to-move,
    selection state, and promotion. input_handler is injected by Game
    after pygame init.
    """

    def __init__(self):
        self.input_handler: InputHandler | None = None
        self.selected_square: int | None = None
        self.legal_squares: list[int] | None = None

    def get_move(self, board: chess.Board) -> chess.Move | None:
        if self.input_handler is None:
            return None

        square = self.input_handler.get_clicked_square()
        if square is None:
            return None

        if self.selected_square is None:
            piece = board.piece_at(square)
            if piece is not None and piece.color == board.turn:
                self.selected_square = square
                self.legal_squares = list({m.to_square for m in board.legal_moves if m.from_square == square})
            return None

        piece = board.piece_at(square)
        if piece is not None and piece.color == board.turn and square != self.selected_square:
            self.selected_square = square
            self.legal_squares = list({m.to_square for m in board.legal_moves if m.from_square == square})
            return None

        source = self.selected_square
        self.selected_square = None
        self.legal_squares = None

        move = chess.Move(source, square)
        if move in board.legal_moves:
            return move

        # Auto-promote to queen (pawn reaching back rank)
        promo = chess.Move(source, square, promotion=chess.QUEEN)
        if promo in board.legal_moves:
            return promo

        return None
