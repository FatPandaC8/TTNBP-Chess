import pygame

class InputHandler:
    """Raw input plumbing: click detection, hover detection, screen-to-square.

    Owns no game state. HumanAgent calls get_clicked_square() and owns
    the selection logic on top.
    """

    def __init__(self, renderer):
        self.renderer = renderer
        self._prev_mouse_pressed = False
        self._cached_square = None
        self._last_mouse_pos = None
    
    def _get_mouse_square(self):
        """Cache mouse position to avoid repeated system calls."""
        mx, my = pygame.mouse.get_pos()
        
        # Only recalculate if mouse moved
        if (mx, my) == self._last_mouse_pos:
            return self._cached_square
        
        self._last_mouse_pos = (mx, my)
        self._cached_square = self.renderer.screen_to_square(mx, my)
        return self._cached_square
    
    def get_hovered_square(self) -> int | None:
        """Returns cached square."""
        return self._get_mouse_square()
