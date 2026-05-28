import pygame

class InputHandler:
    def __init__(self, renderer) -> None:
        self.renderer = renderer
        self._clicked_square = None

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            square = self.get_square_at(event.pos)
            if square is not None:
                self._clicked_square = square

    def get_clicked_square(self) -> int | None:
        square = self._clicked_square
        self._clicked_square = None
        return square

    def clear_clicked_square(self) -> None:
        self._clicked_square = None

    def get_square_at(self, pos: tuple[int, int]) -> int | None:
        mx, my = pos
        return self.renderer.screen_to_square(mx, my)

    def get_hovered_square(self) -> int | None:
        mx, my = pygame.mouse.get_pos()
        return self.renderer.screen_to_square(mx, my)

    def get_mouse_pos(self) -> tuple[int, int]:
        return pygame.mouse.get_pos()
