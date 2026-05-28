from engine.game.match import Match

class MatchRunner:

    def __init__(
        self,
        match: Match,
    ):
        self.match = match

    def run(self):

        while not self.match.is_over():

            self.match.play_turn()

        print("\nGame Over")
        print(f"Result: {self.match.result()}")