class HelperConfig:
    def __init__(
        self,
        depth,
        move_ordering="normal",
        aggressive=False,
        randomize=False
    ):
        self.depth = depth
        self.move_ordering = move_ordering
        self.aggressive = aggressive
        self.randomize = randomize