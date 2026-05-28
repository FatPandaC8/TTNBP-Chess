from __future__ import annotations

from dataclasses import dataclass

import chess
import pygame


@dataclass(frozen=True)
class PromotionChoice:
    piece_type: int
    piece_name: str
    rect: pygame.Rect


class PromotionPicker:
    _PIECE_ORDER = (
        chess.QUEEN,
        chess.ROOK,
        chess.BISHOP,
        chess.KNIGHT,
    )

    def __init__(
        self,
        to_square: int,
        color: chess.Color,
        square_size: int,
        board_offset_x: int,
        board_offset_y: int,
    ) -> None:
        self.to_square = to_square
        self.color = color
        self.choices: list[PromotionChoice] = []
        self._build(square_size, board_offset_x, board_offset_y)

    def hit_test(self, pos: tuple[int, int]) -> int | None:
        for choice in self.choices:
            if choice.rect.collidepoint(pos):
                return choice.piece_type
        return None

    def bounding_rect(self) -> pygame.Rect:
        rects = [choice.rect for choice in self.choices]
        return rects[0].unionall(rects[1:])

    def _build(self, sq: int, bx: int, by: int) -> None:
        color_str = "white" if self.color == chess.WHITE else "black"
        file_idx = chess.square_file(self.to_square)
        rank_idx = chess.square_rank(self.to_square)

        col_x = bx + file_idx * sq
        base_y = by + (7 - rank_idx) * sq

        for i, pt in enumerate(self._PIECE_ORDER):
            y = base_y + i * sq if self.color == chess.WHITE else base_y - i * sq
            rect = pygame.Rect(col_x, y, sq, sq)
            name = f"{color_str}_{chess.piece_name(pt)}"
            self.choices.append(PromotionChoice(piece_type=pt, piece_name=name, rect=rect))
