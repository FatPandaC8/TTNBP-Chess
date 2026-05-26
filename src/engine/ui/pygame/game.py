import os
import math
from concurrent.futures import ThreadPoolExecutor

import chess
import pygame
import pygame.locals as pg_locals

from engine.game.match import Match
from engine.ui.pygame.renderer import (
    PygameRenderer, MovingPiece,
    WINDOW_W, WINDOW_H, BOARD_PX, H_MARGIN, TOP_BAR_H, SIDE_PANEL_W,
    BG_DARK, BG_PANEL, TEXT_PRI, TEXT_SEC,
    BTN_BG, BTN_HOVER, BTN_TEXT,
    _lerp_color,
)
from engine.ui.pygame.input_handler import InputHandler
from engine.ui.pygame.human_agent import HumanAgent


# How long the final board position stays visible before game-over overlay
# fades in — gives the player time to process the last move.
_GAME_OVER_DELAY    = 1.0
_GAME_OVER_FADE_DUR = 0.35


class _Button:
    """Minimal stateful button with smooth hover colour transition."""

    def __init__(self, rect: pygame.Rect, label: str, font: pygame.font.Font):
        self.rect     = rect
        self.label    = label
        self.font     = font
        self._hover_t = 0.0   # 0 = resting  →  1 = fully hovered

    def update(self, dt: float) -> None:
        target = 1.0 if self.rect.collidepoint(pygame.mouse.get_pos()) else 0.0
        self._hover_t += (target - self._hover_t) * min(dt * 10.0, 1.0)

    def draw(self, surface: pygame.Surface) -> None:
        color = _lerp_color(BTN_BG, BTN_HOVER, self._hover_t)
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        text_surf = self.font.render(self.label, True, BTN_TEXT)
        tx = self.rect.centerx - text_surf.get_width()  // 2
        ty = self.rect.centery - text_surf.get_height() // 2
        surface.blit(text_surf, (tx, ty))

    def is_clicked(self, event: pygame.event.Event) -> bool:
        return (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )


class Game:
    """Pygame application shell for chess gameplay.

    Responsible for:
    - pygame window and event loop
    - menu and UI rendering
    - delegating gameplay to Match

    NOT responsible for:
    - board ownership
    - move validation
    - turn management
    - game-over logic
    """

    def __init__(self, match: Match):
        self.match   = match
        self.running = True
        self._state  = "menu"   # "menu" | "game" | "game_over"

        # Non-blocking AI
        self._executor  = ThreadPoolExecutor(max_workers=1)
        self._ai_future = None

        # Animation / timing
        self._moving_piece: MovingPiece | None = None
        self._last_move:    chess.Move  | None = None
        self._pulse_t    = 0.0   # selection-ring pulse
        self._thinking_t = 0.0   # AI dot animation

        # Game-over fade
        self._game_over_timer = 0.0
        self._overlay_alpha   = 0

        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")

        pygame.display.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("Chess")
        pygame.display.set_icon(pygame.image.load(os.path.join(assets_dir, "chess_icon.png")))

        self._font_sm = self._load_font(assets_dir, 15)
        self._font_md = self._load_font(assets_dir, 18)
        self._font_lg = self._load_font(assets_dir, 46)

        self.renderer = PygameRenderer(self.screen, assets_dir)
        self._connect_human_agents()

        cx = WINDOW_W // 2
        self._btn_play       = _Button(pygame.Rect(cx - 70, 320, 140, 46), "Play",       self._font_md)
        self._btn_play_again = _Button(pygame.Rect(cx - 80, 395, 160, 46), "Play Again", self._font_md)

        self.clock = pygame.time.Clock()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def start_game(self) -> None:
        while self.running:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pg_locals.K_ESCAPE:
                    self.running = False
                else:
                    self._handle_event(event)

            self._update(dt)
            self._draw()
            pygame.display.flip()

        self._executor.shutdown(wait=False)
        pygame.quit()

    # ------------------------------------------------------------------
    # Event routing  (KEYDOWN events — not get_pressed — for one-shot actions)
    # ------------------------------------------------------------------

    def _handle_event(self, event: pygame.event.Event) -> None:
        if self._state == "menu":
            if self._btn_play.is_clicked(event):
                self._state = "game"
            elif event.type == pygame.KEYDOWN and event.key == pg_locals.K_RETURN:
                self._state = "game"

        elif self._state == "game_over":
            if self._btn_play_again.is_clicked(event):
                self._reset()
            elif event.type == pygame.KEYDOWN and event.key == pg_locals.K_RETURN:
                self._reset()

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def _update(self, dt: float) -> None:
        self._pulse_t    += dt
        self._thinking_t += dt

        if self._state == "menu":
            self._btn_play.update(dt)
        elif self._state == "game":
            self._update_game(dt)
        elif self._state == "game_over":
            self._btn_play_again.update(dt)
            fade_progress       = max(0.0, self._game_over_timer - _GAME_OVER_DELAY)
            self._overlay_alpha = int(min(fade_progress / _GAME_OVER_FADE_DUR, 1.0) * 200)
            self._game_over_timer += dt

    def _update_game(self, dt: float) -> None:
        # Advance sliding-piece animation each frame
        if self._moving_piece:
            self._moving_piece.update(dt)
            if self._moving_piece.done:
                self._moving_piece = None
            return   # don't process new moves while a piece is mid-flight

        # Transition to game_over as soon as the board says it's done
        if self.match.is_over():
            if self._state == "game":
                self._state           = "game_over"
                self._game_over_timer = 0.0
                self._overlay_alpha   = 0
            return

        agent = self.match.current_agent()

        if isinstance(agent, HumanAgent):
            move = agent.get_move(self.match.board)
        else:
            # Submit AI work once; poll for result every frame (never blocks)
            if self._ai_future is None:
                board_copy       = self.match.board.copy()
                self._ai_future  = self._executor.submit(agent.get_move, board_copy)
                self._thinking_t = 0.0
            move = None
            if self._ai_future.done():
                move            = self._ai_future.result()
                self._ai_future = None

        if move is not None:
            self._apply_move(move)

    # ------------------------------------------------------------------
    # Apply move + kick off slide animation
    # ------------------------------------------------------------------

    def _apply_move(self, move: chess.Move) -> None:
        piece = self.match.board.piece_at(move.from_square)
        if piece is not None:
            self._moving_piece = MovingPiece(
                piece_name = self.renderer.piece_to_name[piece.symbol()],
                from_sq    = move.from_square,
                from_px    = self.renderer.square_to_screen(move.from_square),
                to_px      = self.renderer.square_to_screen(move.to_square),
            )

        try:
            self.match.validate_move(move)
            self.match.board.push(move)
        except ValueError as e:
            self._moving_piece = None
            raise RuntimeError(f"Illegal move: {move}") from e

        self._last_move = move

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        self.screen.fill(BG_DARK)

        if self._state == "menu":
            self._draw_menu()
        elif self._state == "game":
            self._draw_game()
        elif self._state == "game_over":
            self._draw_game()
            self._draw_game_over_overlay()

    def _draw_menu(self) -> None:
        title = self._font_lg.render("Chess", True, TEXT_PRI)
        self.screen.blit(title, (WINDOW_W // 2 - title.get_width() // 2, 200))

        sub = self._font_sm.render("Press Enter or click Play to start", True, TEXT_SEC)
        self.screen.blit(sub, (WINDOW_W // 2 - sub.get_width() // 2, 278))

        self._btn_play.draw(self.screen)

        credit = self._font_sm.render("Created by group 100", True, TEXT_SEC)
        self.screen.blit(credit, (WINDOW_W // 2 - credit.get_width() // 2, WINDOW_H - 46))

    def _draw_game(self) -> None:
        agent = self.match.current_agent()

        hover_sq  = None
        selected  = getattr(agent, 'selected_square', None)
        legal_sqs = getattr(agent, 'legal_squares',   None)

        if isinstance(agent, HumanAgent) and agent.input_handler:
            hover_sq = agent.input_handler.get_hovered_square()

        self.renderer.render(
            self.match.board,
            selected_square = selected,
            legal_squares   = legal_sqs,
            last_move       = self._last_move,
            hover_square    = hover_sq,
            moving_piece    = self._moving_piece,
            pulse_t         = self._pulse_t,
        )

        self._draw_top_bar()
        self._draw_side_panel()

    def _draw_top_bar(self) -> None:
        turn_name = "White" if self.match.board.turn == chess.WHITE else "Black"
        turn_surf = self._font_md.render(f"{turn_name} to move", True, TEXT_PRI)
        ty = (TOP_BAR_H - turn_surf.get_height()) // 2
        self.screen.blit(turn_surf, (H_MARGIN, ty))

        if self._ai_future is not None:
            n_dots   = int(self._thinking_t * 3) % 4
            think    = self._font_sm.render("Thinking" + "." * n_dots, True, TEXT_SEC)
            self.screen.blit(think, (H_MARGIN + turn_surf.get_width() + 14, ty + 3))

    def _draw_side_panel(self) -> None:
        panel_x = H_MARGIN + BOARD_PX + H_MARGIN
        panel_y = TOP_BAR_H
        panel_w = SIDE_PANEL_W
        panel_h = BOARD_PX

        pygame.draw.rect(self.screen, BG_PANEL,
                         (panel_x, panel_y, panel_w, panel_h), border_radius=6)

        label = self._font_sm.render("Moves", True, TEXT_SEC)
        self.screen.blit(label, (panel_x + 12, panel_y + 12))

        san_pairs   = self._build_san_list()
        row_h       = 22
        content_y   = panel_y + 38
        max_y       = panel_y + panel_h - 10
        visible     = (max_y - content_y) // row_h
        start       = max(0, len(san_pairs) - visible)

        for idx, (w_san, b_san) in enumerate(san_pairs[start:]):
            num   = self._font_sm.render(f"{start + idx + 1}.", True, TEXT_SEC)
            white = self._font_sm.render(w_san,  True, TEXT_PRI)
            black = self._font_sm.render(b_san,  True, TEXT_PRI)
            self.screen.blit(num,   (panel_x + 10,  content_y))
            self.screen.blit(white, (panel_x + 38,  content_y))
            self.screen.blit(black, (panel_x + 120, content_y))
            content_y += row_h
            if content_y > max_y:
                break

    def _draw_game_over_overlay(self) -> None:
        if self._overlay_alpha <= 0:
            return

        bx = self.renderer.board_offset_x
        by = self.renderer.board_offset_y

        overlay = pygame.Surface((BOARD_PX, BOARD_PX), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, self._overlay_alpha))
        self.screen.blit(overlay, (bx, by))

        # Wait until overlay is mostly opaque before showing text
        if self._overlay_alpha < 170:
            return

        outcome = self.match.board.outcome()
        if outcome is None:
            return

        if outcome.winner is None:
            winner_text = "Draw"
        elif outcome.winner == chess.WHITE:
            winner_text = "White wins!"
        else:
            winner_text = "Black wins!"

        title = self._font_lg.render(winner_text, True, TEXT_PRI)
        tx = bx + (BOARD_PX - title.get_width())  // 2
        ty = by + BOARD_PX // 2 - title.get_height() - 30
        self.screen.blit(title, (tx, ty))

        reason = outcome.termination.name.replace("_", " ").title()
        sub = self._font_sm.render(reason, True, TEXT_SEC)
        self.screen.blit(sub, (bx + (BOARD_PX - sub.get_width()) // 2,
                                ty + title.get_height() + 8))

        self._btn_play_again.draw(self.screen)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_san_list(self) -> list[tuple[str, str]]:
        """Replay the board's move stack to produce (white_san, black_san) pairs."""
        board  = chess.Board()
        pairs: list[tuple[str, str]] = []
        moves  = list(self.match.board.move_stack)
        i = 0
        while i < len(moves):
            w = board.san(moves[i])
            board.push(moves[i])
            i += 1
            b = ""
            if i < len(moves):
                b = board.san(moves[i])
                board.push(moves[i])
                i += 1
            pairs.append((w, b))
        return pairs

    def _connect_human_agents(self) -> None:
        input_handler = InputHandler(self.renderer)
        for agent in (self.match.white_agent, self.match.black_agent):
            if isinstance(agent, HumanAgent):
                agent.input_handler   = input_handler
                agent.selected_square = None

    def _reset(self) -> None:
        self.match = Match(
            board       = chess.Board(),
            white_agent = self.match.white_agent,
            black_agent = self.match.black_agent,
        )
        self._connect_human_agents()
        self._last_move       = None
        self._moving_piece    = None
        self._ai_future       = None
        self._game_over_timer = 0.0
        self._overlay_alpha   = 0
        self._state           = "game"

    @staticmethod
    def _load_font(assets_dir: str, size: int) -> pygame.font.Font:
        for name in ("inter_regular.ttf", "Inter-Regular.ttf"):
            path = os.path.join(assets_dir, "fonts", name)
            if os.path.exists(path):
                return pygame.font.Font(path, size)
        for sysname in ("segoeui", "helveticaneue", "dejavusans", "freesans"):
            try:
                return pygame.font.SysFont(sysname, size)
            except Exception:
                continue
        return pygame.font.Font(None, size)