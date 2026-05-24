import os
import pygame
import chess
from engine.ui.pygame.piece import Piece


class PygameRenderer:
    def __init__(self, screen: pygame.Surface, assets_dir: str):
        self.screen = screen
        self.board_offset_x = 0
        self.board_offset_y = 50

        # Load board image
        board_path = os.path.join(assets_dir, "board.png")
        self.board_img = pygame.image.load(board_path).convert()

        # Calculate square size
        self.square_size = self.board_img.get_rect().width // 8

        # Load piece sprites
        pieces_path = os.path.join(assets_dir, "pieces.png")
        self.piece_renderer = Piece(pieces_path, cols=6, rows=2)

        # Piece to unicode mapping for python-chess
        self.piece_to_name = {
            'P': 'white_pawn',
            'N': 'white_knight',
            'B': 'white_bishop',
            'R': 'white_rook',
            'Q': 'white_queen',
            'K': 'white_king',
            'p': 'black_pawn',
            'n': 'black_knight',
            'b': 'black_bishop',
            'r': 'black_rook',
            'q': 'black_queen',
            'k': 'black_king',
        }

    def _square_to_screen(self, square: int) -> tuple:
        """Convert chess square (0-63) to screen coordinates."""
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        x = self.board_offset_x + file * self.square_size
        y = self.board_offset_y + (7 - rank) * self.square_size
        return (x, y)

    def render(self, board: chess.Board, selected_square: int | None = None, legal_squares: list[int] | None = None):
        """Render the board, optional selection highlight, legal-move hints, and all pieces."""
        self.screen.blit(self.board_img, (self.board_offset_x, self.board_offset_y))

        if selected_square is not None:
            x, y = self._square_to_screen(selected_square)
            highlight = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
            highlight.fill((255, 220, 0, 110))
            self.screen.blit(highlight, (x, y))

        if legal_squares:
            half = self.square_size // 2
            _dot = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
            pygame.draw.circle(_dot, (0, 0, 0, 70), (half, half), self.square_size // 6)
            _ring = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
            pygame.draw.circle(_ring, (0, 0, 0, 70), (half, half), half - 3, 4)
            for sq in legal_squares:
                x, y = self._square_to_screen(sq)
                self.screen.blit(_ring if board.piece_at(sq) else _dot, (x, y))

        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece is not None:
                piece_name = self.piece_to_name[piece.symbol()]
                self.piece_renderer.draw(self.screen, piece_name, self._square_to_screen(square))

    def get_square_size(self) -> int:
        """Return the size of a single square in pixels."""
        return self.square_size

    def get_board_offset(self) -> tuple:
        """Return the board offset (x, y)."""
        return (self.board_offset_x, self.board_offset_y)

    def screen_to_square(self, mouse_x: int, mouse_y: int) -> int | None:
        """Convert screen coordinates to chess square number, or None if outside board."""
        x = mouse_x - self.board_offset_x
        y = mouse_y - self.board_offset_y

        if x < 0 or y < 0 or x >= self.square_size * 8 or y >= self.square_size * 8:
            return None

        file = x // self.square_size
        rank = 7 - (y // self.square_size)

        return chess.square(file, rank)
