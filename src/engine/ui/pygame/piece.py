import pygame

class Piece(pygame.sprite.Sprite):
    def __init__(self, filename: str, cols: int, rows: int):
        pygame.sprite.Sprite.__init__(self)
        self.pieces = {
            "white_pawn":   5,  "white_knight": 3, "white_bishop": 2,
            "white_rook":   4,  "white_queen":  1, "white_king":   0,
            "black_pawn":  11,  "black_knight": 9, "black_bishop": 8,
            "black_rook":  10,  "black_queen":  7, "black_king":   6,
        }
        self.spritesheet = pygame.image.load(filename).convert_alpha()
        self.cols = cols
        self.rows = rows
        self.cell_count = cols * rows

        rect = self.spritesheet.get_rect()
        self.cell_width  = rect.width  // cols
        self.cell_height = rect.height // rows
        self._rebuild_cells()

    def _rebuild_cells(self) -> None:
        w, h = self.cell_width, self.cell_height
        self.cells = [
            (i % self.cols * w, i // self.cols * h, w, h)
            for i in range(self.cell_count)
        ]

    def rescale(self, target_size: int) -> None:
        """Re-build the spritesheet so every cell is target_size × target_size.

        Called once at renderer init so pieces are pixel-perfect on the board.
        Uses smoothscale for clean bilinear interpolation — looks much better
        than the default nearest-neighbor scale.
        """
        if self.cell_width == target_size and self.cell_height == target_size:
            return

        new_sheet = pygame.Surface(
            (target_size * self.cols, target_size * self.rows),
            pygame.SRCALPHA,
        )
        for i, (cx, cy, cw, ch) in enumerate(self.cells):
            cell_surf = self.spritesheet.subsurface((cx, cy, cw, ch))
            scaled    = pygame.transform.smoothscale(cell_surf, (target_size, target_size))
            col = i % self.cols
            row = i // self.cols
            new_sheet.blit(scaled, (col * target_size, row * target_size))

        self.spritesheet = new_sheet
        self.cell_width  = target_size
        self.cell_height = target_size
        self._rebuild_cells()

    def draw(self, surface: pygame.Surface, piece_name: str, coords: tuple) -> None:
        piece_index = self.pieces[piece_name]
        surface.blit(self.spritesheet, coords, self.cells[piece_index])
