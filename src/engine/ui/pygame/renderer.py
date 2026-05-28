import math
import os

import chess
import pygame

from engine.ui.pygame.piece import Piece


# ---------------------------------------------------------------------------
# Layout constants — change these to resize the whole UI
# ---------------------------------------------------------------------------
BOARD_PX      = 640          # board is always square
SIDE_PANEL_W  = 260          # move-history / captured panel on the right
H_MARGIN      = 20           # left & right outer margin
TOP_BAR_H     = 50           # player-name bar above the board
BOTTOM_BAR_H  = 50           # player-name bar below the board
WINDOW_W      = H_MARGIN + BOARD_PX + H_MARGIN + SIDE_PANEL_W + H_MARGIN   # 980
WINDOW_H      = TOP_BAR_H + BOARD_PX + BOTTOM_BAR_H                        # 740

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Chess.com inspired theme
# ---------------------------------------------------------------------------

# Board
SQ_LIGHT = (238, 238, 210)
SQ_DARK  = (118, 150, 86)

COORD_ON_LIGHT = SQ_DARK
COORD_ON_DARK  = SQ_LIGHT

# Overlays
COL_SELECTED  = (186, 202, 68, 150)
COL_LAST_MOVE = (246, 246, 105, 95)
COL_CHECK     = (220, 50, 50, 170)

COL_HOVER = (255, 255, 255, 24)

COL_DOT  = (0, 0, 0, 65)
COL_RING = (0, 0, 0, 65)

# UI chrome
BG_DARK  = (49, 46, 43)
BG_PANEL = (38, 36, 33)

TEXT_PRI = (245, 245, 245)
TEXT_SEC = (170, 170, 170)

ACCENT    = (129, 182, 76)
BTN_BG    = (129, 182, 76)
BTN_HOVER = (149, 200, 90)
BTN_TEXT  = (255, 255, 255)

# ---------------------------------------------------------------------------
# Lichess inspired theme
# ---------------------------------------------------------------------------

# # Board
# SQ_LIGHT = (240, 217, 181)
# SQ_DARK  = (181, 136, 99)

# COORD_ON_LIGHT = SQ_DARK
# COORD_ON_DARK  = SQ_LIGHT

# # Overlays
# COL_SELECTED  = (76, 175, 80, 110)
# COL_LAST_MOVE = (205, 210, 106, 70)
# COL_CHECK     = (230, 70, 70, 150)

# COL_HOVER = (255, 255, 255, 18)

# COL_DOT  = (0, 0, 0, 50)
# COL_RING = (0, 0, 0, 50)

# # UI chrome
# BG_DARK  = (22, 21, 18)
# BG_PANEL = (32, 30, 27)

# TEXT_PRI = (220, 220, 220)
# TEXT_SEC = (140, 140, 140)

# ACCENT    = (90, 140, 220)
# BTN_BG    = (70, 110, 180)
# BTN_HOVER = (90, 130, 210)
# BTN_TEXT  = (255, 255, 255)


def _ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(int(_lerp(a, b, t)) for a, b in zip(c1, c2))


# ---------------------------------------------------------------------------
# MovingPiece  — lightweight animation state for a sliding piece
# ---------------------------------------------------------------------------
class MovingPiece:
    DURATION = 0.13   # seconds

    def __init__(self, piece_name: str, from_sq: int, from_px: tuple, to_px: tuple):
        self.piece_name = piece_name
        self.from_sq    = from_sq
        self.from_px    = from_px
        self.to_px      = to_px
        self.elapsed    = 0.0

    @property
    def done(self) -> bool:
        return self.elapsed >= self.DURATION

    @property
    def current_px(self) -> tuple[int, int]:
        t = _ease_out_cubic(min(self.elapsed / self.DURATION, 1.0))
        return (
            int(_lerp(self.from_px[0], self.to_px[0], t)),
            int(_lerp(self.from_px[1], self.to_px[1], t)),
        )

    def update(self, dt: float) -> None:
        self.elapsed = min(self.elapsed + dt, self.DURATION)


# ---------------------------------------------------------------------------
# PygameRenderer
# ---------------------------------------------------------------------------
class PygameRenderer:
    def __init__(self, screen: pygame.Surface, assets_dir: str):
        self.screen = screen

        self.board_offset_x = H_MARGIN
        self.board_offset_y = TOP_BAR_H

        # --- board image ---
        board_path = os.path.join(assets_dir, "board.png")
        raw_board = pygame.image.load(board_path).convert()
        self.board_img = pygame.transform.smoothscale(raw_board, (BOARD_PX, BOARD_PX))
        self.square_size = BOARD_PX // 8

        # --- coordinate font (small, bundled fallback) ---
        self._coord_font = pygame.font.SysFont("segoeui", 11, bold=True)
        
        # --- static cached board layer ---
        self.static_board_surface = pygame.Surface(
            (BOARD_PX, BOARD_PX)
        ).convert()

        # draw board image once
        self.static_board_surface.blit(self.board_img, (0, 0))

        self._coord_surface = pygame.Surface((BOARD_PX, BOARD_PX), pygame.SRCALPHA)
        self._draw_coordinates_to(self._coord_surface)

        # --- pieces ---
        pieces_path = os.path.join(assets_dir, "pieces.png")
        self.piece_renderer = Piece(pieces_path, cols=6, rows=2)
        self.piece_renderer.rescale(self.square_size)   # fit pieces to square size

        self.piece_to_name = {
            'P': 'white_pawn',   'N': 'white_knight', 'B': 'white_bishop',
            'R': 'white_rook',   'Q': 'white_queen',  'K': 'white_king',
            'p': 'black_pawn',   'n': 'black_knight', 'b': 'black_bishop',
            'r': 'black_rook',   'q': 'black_queen',  'k': 'black_king',
        }


        # --- pre-built overlay surfaces (avoids per-frame allocation) ---
        sq = self.square_size
        self._surf_selected  = self._solid_sq(COL_SELECTED)
        self._surf_last_move = self._solid_sq(COL_LAST_MOVE)
        self._surf_check     = self._solid_sq(COL_CHECK)
        self._surf_hover     = self._solid_sq(COL_HOVER)
        self._surf_dot       = self._make_dot(filled=True)
        self._surf_ring      = self._make_dot(filled=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        board: chess.Board,
        *,
        selected_square: int | None = None,
        legal_squares:   list[int] | None = None,
        last_move:       chess.Move | None = None,
        hover_square:    int | None = None,
        moving_piece:    MovingPiece | None = None,
        pulse_t:         float = 0.0,
    ) -> None:
        """Draw the complete board frame.  All parameters are keyword-only
        so callers are explicit about what they pass."""

        # Layer 0 – board image
        self.screen.blit(
            self.static_board_surface,
            (self.board_offset_x, self.board_offset_y)
        )

        # Layer 1 – last-move highlight (faint, always on)
        if last_move is not None:
            self._draw_last_move(last_move)

        # Layer 2 – check highlight (red king square, drawn under piece)
        if board.is_check():
            self._draw_check(board)

        # Layer 3 – selection highlight (pulsing)
        if selected_square is not None:
            self._draw_selection(selected_square, pulse_t)

        # Layer 4 – hover (own-piece squares only)
        if hover_square is not None:
            self._draw_hover(hover_square, board)

        # Layer 5 – legal move dots / capture rings
        if legal_squares:
            self._draw_legal_dots(board, legal_squares)

        # Layer 6 – all pieces except the one currently flying
        skip_sq = moving_piece.from_sq if (moving_piece and not moving_piece.done) else None
        self._draw_all_pieces(board, skip_square=skip_sq)

        # Layer 7 – animating piece on top of everything
        if moving_piece and not moving_piece.done:
            self.piece_renderer.draw(self.screen, moving_piece.piece_name, moving_piece.current_px)

        # Layer 8 – coordinates
        self.screen.blit(self._coord_surface, (self.board_offset_x, self.board_offset_y))


    def get_square_size(self) -> int:
        return self.square_size

    def get_board_offset(self) -> tuple[int, int]:
        return (self.board_offset_x, self.board_offset_y)

    def screen_to_square(self, mouse_x: int, mouse_y: int) -> int | None:
        x = mouse_x - self.board_offset_x
        y = mouse_y - self.board_offset_y
        if x < 0 or y < 0 or x >= BOARD_PX or y >= BOARD_PX:
            return None
        return chess.square(x // self.square_size, 7 - (y // self.square_size))

    def square_to_screen(self, square: int) -> tuple[int, int]:
        return self._square_to_screen(square)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _square_to_screen(self, square: int) -> tuple[int, int]:
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        x = self.board_offset_x + file * self.square_size
        y = self.board_offset_y + (7 - rank) * self.square_size
        return (x, y)

    def _solid_sq(self, rgba: tuple) -> pygame.Surface:
        s = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
        s.fill(rgba)
        return s

    def _make_dot(self, filled: bool) -> pygame.Surface:
        sq  = self.square_size
        s   = pygame.Surface((sq, sq), pygame.SRCALPHA)
        half = sq // 2
        if filled:
            radius = sq // 5
            pygame.draw.circle(s, COL_DOT, (half, half), radius)
        else:
            pygame.draw.circle(s, COL_RING, (half, half), half - 3, 5)
        return s

    def _draw_last_move(self, move: chess.Move) -> None:
        for sq in (move.from_square, move.to_square):
            self.screen.blit(self._surf_last_move, self._square_to_screen(sq))

    def _draw_check(self, board: chess.Board) -> None:
        king_sq = board.king(board.turn)
        if king_sq is not None:
            self.screen.blit(self._surf_check, self._square_to_screen(king_sq))

    def _draw_selection(self, square: int, pulse_t: float) -> None:
        # Animate alpha with a slow sine pulse so the selection "breathes"
        alpha = int(100 + 50 * math.sin(pulse_t * math.pi * 2.5))
        surf = self._surf_selected.copy()
        surf.set_alpha(alpha)
        self.screen.blit(surf, self._square_to_screen(square))

    def _draw_hover(self, square: int, board: chess.Board) -> None:
        piece = board.piece_at(square)
        if piece is not None and piece.color == board.turn:
            self.screen.blit(self._surf_hover, self._square_to_screen(square))

    def _draw_legal_dots(self, board: chess.Board, legal_squares: list[int]) -> None:
        for sq in legal_squares:
            surf = self._surf_ring if board.piece_at(sq) else self._surf_dot
            self.screen.blit(surf, self._square_to_screen(sq))

    def _draw_all_pieces(self, board: chess.Board, skip_square: int | None) -> None:
        for square in chess.SQUARES:
            if square == skip_square:
                continue
            piece = board.piece_at(square)
            if piece is not None:
                self.piece_renderer.draw(
                    self.screen,
                    self.piece_to_name[piece.symbol()],
                    self._square_to_screen(square),
                )

    def _draw_coordinates_to(self, target: pygame.Surface) -> None:
        files = "abcdefgh"
        sq = self.square_size

        for i in range(8):
            # File labels
            on_light = (i % 2 == 0)

            f_color = COORD_ON_LIGHT if on_light else COORD_ON_DARK
            f_surf = self._coord_font.render(files[i], True, f_color)

            fx = i * sq + sq - f_surf.get_width() - 3
            fy = 8 * sq - f_surf.get_height() - 2

            target.blit(f_surf, (fx, fy))

            # Rank labels
            r_on_light = ((7 - i) % 2 == 0)

            r_color = COORD_ON_LIGHT if r_on_light else COORD_ON_DARK
            r_surf = self._coord_font.render(str(8 - i), True, r_color)

            target.blit(r_surf, (3, i * sq + 3))
