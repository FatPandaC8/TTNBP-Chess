import os

import chess
import pygame
import pygame.locals as pg_locals

from engine.game.match import Match
from engine.ui.pygame.renderer import PygameRenderer
from engine.ui.pygame.input_handler import InputHandler
from engine.ui.pygame.human_agent import HumanAgent


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
        self.match = match

        screen_width = 640
        screen_height = 750

        self.menu_showed = False
        self.running = True

        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")

        pygame.display.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode([screen_width, screen_height])
        self._small_font = pygame.font.SysFont("comicsansms", 20)
        self._big_font = pygame.font.SysFont("comicsansms", 50)
        pygame.display.set_caption("Chess")

        icon_path = os.path.join(assets_dir, "chess_icon.png")
        icon = pygame.image.load(icon_path)
        pygame.display.set_icon(icon)

        self.renderer = PygameRenderer(self.screen, assets_dir)

        self._connect_human_agents()

        self.clock = pygame.time.Clock()

    def start_game(self):
        """Main pygame event loop."""
        while self.running:
            self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pg_locals.K_ESCAPE:
                    self.running = False

            if not self.menu_showed:
                self._menu()
            elif self.match.is_over():
                self._declare_winner()
            else:
                self._game()

        pygame.quit()

    def _connect_human_agents(self):
        """Create an InputHandler and inject it into any HumanAgent in the match."""
        input_handler = InputHandler(self.renderer)
        for agent in (self.match.white_agent, self.match.black_agent):
            if isinstance(agent, HumanAgent):
                agent.input_handler = input_handler
                agent.selected_square = None

    def _menu(self):
        """Show game menu."""
        bg_color = (255, 255, 255)
        self.screen.fill(bg_color)

        black_color = (0, 0, 0)
        white_color = (255, 255, 255)

        start_btn = pygame.Rect(270, 300, 100, 50)
        pygame.draw.rect(self.screen, black_color, start_btn)

        welcome_text = self._big_font.render("Chess", False, black_color)
        created_by = self._small_font.render("Created by group 100", True, black_color)
        start_btn_label = self._small_font.render("Play", True, white_color)

        self.screen.blit(welcome_text,
                         ((self.screen.get_width() - welcome_text.get_width()) // 2, 150))
        self.screen.blit(created_by,
                         ((self.screen.get_width() - created_by.get_width()) // 2,
                          self.screen.get_height() - created_by.get_height() - 100))
        self.screen.blit(start_btn_label,
                         ((start_btn.x + (start_btn.width - start_btn_label.get_width()) // 2,
                           start_btn.y + (start_btn.height - start_btn_label.get_height()) // 2)))

        key_pressed = pygame.key.get_pressed()
        if pygame.mouse.get_pressed()[0]:
            mouse_coords = pygame.mouse.get_pos()
            if start_btn.collidepoint(mouse_coords[0], mouse_coords[1]):
                pygame.draw.rect(self.screen, white_color, start_btn, 3)
                self.menu_showed = True
        elif key_pressed[pg_locals.K_RETURN]:
            self.menu_showed = True

        pygame.display.flip()

    def _game(self):
        self.screen.fill((0, 0, 0))

        # 1. luôn render trước (EVERY FRAME)
        agent = self.match.current_agent()
        selected = getattr(agent, 'selected_square', None)
        legal_squares = getattr(agent, 'legal_squares', None)

        self.renderer.render(self.match.board, selected_square=selected, legal_squares=legal_squares)

        self.screen.blit(
            self._small_font.render(
                f"Turn: {'White' if self.match.board.turn else 'Black'}",
                True,
                (255, 255, 255),
            ),
            (10, 10),
        )

        # Ensure the current board state is visible before any expensive AI thinking.
        pygame.display.flip()

        # 2. xử lý move AFTER render
        move = agent.get_move(self.match.board.copy())

        if move is not None:
            try:
                self.match.validate_move(move)
                self.match.board.push(move)
            except ValueError as e:
                raise RuntimeError(f"Illegal move: {move}") from e

    def _declare_winner(self):
        """Show game over screen."""
        bg_color = (255, 255, 255)
        self.screen.fill(bg_color)

        black_color = (0, 0, 0)
        white_color = (255, 255, 255)

        reset_btn = pygame.Rect(250, 300, 140, 50)
        pygame.draw.rect(self.screen, black_color, reset_btn)

        outcome = self.match.board.outcome()
        if outcome.winner is None:
            winner_name = "Draw"
        else:
            winner_name = "White" if outcome.winner else "Black"

        winner_text = self._big_font.render(f"{winner_name} wins!", False, black_color)
        reset_btn_label = self._small_font.render("Play Again", True, white_color)

        self.screen.blit(winner_text,
                         ((self.screen.get_width() - winner_text.get_width()) // 2, 150))
        self.screen.blit(reset_btn_label,
                         ((reset_btn.x + (reset_btn.width - reset_btn_label.get_width()) // 2,
                           reset_btn.y + (reset_btn.height - reset_btn_label.get_height()) // 2)))

        key_pressed = pygame.key.get_pressed()
        if pygame.mouse.get_pressed()[0]:
            mouse_coords = pygame.mouse.get_pos()
            if reset_btn.collidepoint(mouse_coords[0], mouse_coords[1]):
                pygame.draw.rect(self.screen, white_color, reset_btn, 3)
                self._reset()
        elif key_pressed[pg_locals.K_RETURN]:
            self._reset()

        pygame.display.flip()

    def _reset(self):
        """Reset the game, reusing the same agents."""
        self.match = Match(
            board=chess.Board(),
            white_agent=self.match.white_agent,
            black_agent=self.match.black_agent,
        )
        self._connect_human_agents()
        self.menu_showed = True
