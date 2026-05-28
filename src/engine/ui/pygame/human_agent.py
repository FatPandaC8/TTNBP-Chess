import chess
import pygame
import pygame.locals as pg_locals

from engine.agents.interface import Agent
from engine.ui.pygame.input_handler import InputHandler
from engine.ui.pygame.promotion_picker import PromotionPicker


class HumanAgent(Agent):
    _IDLE = "idle"
    _SELECTED = "piece_selected"
    _PROMOTING = "awaiting_promo"

    def __init__(self) -> None:
        self.input_handler: InputHandler | None = None
        self.selected_square: int | None = None
        self.legal_squares: list[int] | None = None
        self.promotion_picker: PromotionPicker | None = None

        self._state = self._IDLE
        self._pending_move: chess.Move | None = None

    def get_move(self, board: chess.Board) -> chess.Move | None:
        if self.input_handler is None or self._state == self._PROMOTING:
            return None

        square = self.input_handler.get_clicked_square()
        if square is None:
            return None

        return self._process_click(square, board)

    def handle_event(self, event: pygame.event.Event) -> chess.Move | None:
        if self.input_handler is not None:
            self.input_handler.handle_event(event)

        if self._state != self._PROMOTING:
            return None

        if event.type == pygame.KEYDOWN and event.key == pg_locals.K_ESCAPE:
            self._cancel_promotion()
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            piece_type = self.promotion_picker.hit_test(event.pos) if self.promotion_picker is not None else None
            if piece_type is not None:
                return self._confirm_promotion(piece_type)
            self._cancel_promotion()

        return None

    def _process_click(self, square: int, board: chess.Board) -> chess.Move | None:
        if self._state == self._IDLE:
            self._try_select(square, board)
            return None

        if self._state == self._SELECTED:
            return self._try_move(square, board)

        return None

    def _try_select(self, square: int, board: chess.Board) -> None:
        piece = board.piece_at(square)
        if piece is not None and piece.color == board.turn:
            self._select(square, board)

    def _try_move(self, square: int, board: chess.Board) -> chess.Move | None:
        piece = board.piece_at(square)
        if piece is not None and piece.color == board.turn and square != self.selected_square:
            self._select(square, board)
            return None

        source = self.selected_square
        self._deselect()

        plain = chess.Move(source, square)
        if plain in board.legal_moves:
            return plain

        if self._is_promotion(source, square, board):
            self._enter_promotion(source, square, board)
            return None

        return None

    @staticmethod
    def _is_promotion(source: int, dest: int, board: chess.Board) -> bool:
        return any(
            chess.Move(source, dest, promotion=pt) in board.legal_moves
            for pt in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)
        )

    def _enter_promotion(self, source: int, dest: int, board: chess.Board) -> None:
        self._state = self._PROMOTING
        self._pending_move = chess.Move(source, dest)

        renderer = self.input_handler.renderer
        self.promotion_picker = PromotionPicker(
            to_square=dest,
            color=board.turn,
            square_size=renderer.get_square_size(),
            board_offset_x=renderer.board_offset_x,
            board_offset_y=renderer.board_offset_y,
        )

    def _confirm_promotion(self, piece_type: int) -> chess.Move:
        move = chess.Move(
            self._pending_move.from_square,
            self._pending_move.to_square,
            promotion=piece_type,
        )
        self._cleanup_promotion()
        return move

    def _cancel_promotion(self) -> None:
        self._cleanup_promotion()

    def _cleanup_promotion(self) -> None:
        if self.input_handler is not None:
            self.input_handler.clear_clicked_square()

        self._state = self._IDLE
        self._pending_move = None
        self.promotion_picker = None
        self.selected_square = None
        self.legal_squares = None

    def _select(self, square: int, board: chess.Board) -> None:
        self._state = self._SELECTED
        self.selected_square = square
        self.legal_squares = list({m.to_square for m in board.legal_moves if m.from_square == square})

    def _deselect(self) -> None:
        self._state = self._IDLE
        self.selected_square = None
        self.legal_squares = None
