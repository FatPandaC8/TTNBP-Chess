import pygame
import chess


class InputHandler:
    """Raw input plumbing: click detection and screen-to-square conversion.

    Owns no game state. HumanAgent calls get_clicked_square() and owns
    the selection logic on top.
    """

    def __init__(self, renderer):
        self.renderer = renderer
        self._prev_mouse_pressed = False

    def get_clicked_square(self) -> int | None:
        """Returns the board square under a fresh left-click, or None."""
        mouse_btn = pygame.mouse.get_pressed()
        clicked = mouse_btn[0] and not self._prev_mouse_pressed
        self._prev_mouse_pressed = mouse_btn[0]

        if not clicked:
            return None

        mouse_x, mouse_y = pygame.mouse.get_pos()
        return self.renderer.screen_to_square(mouse_x, mouse_y)
