import time

from engine.utils.logger import Logger
from engine.game.match import Match

class MatchRunner:

    def __init__(
        self,
        match: Match,
        logger: Logger,
        delay: float = 0.0
    ):
        self.match = match
        self.delay = delay
        self.logger = logger

    def run(self):

        while not self.match.is_over():

            self.match.play_turn()

            time.sleep(self.delay)

        print("\nGame Over")
        print(f"Result: {self.match.result()}")