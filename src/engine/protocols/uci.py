import chess
from engine.agents.interface import Agent

class UCIProtocol:

    def __init__(self, agent: Agent):
        self.agent = agent
        self.board = chess.Board()

        self.running = True

    def loop(self):
        while self.running:
            try:
                command = input().strip()
                self._handle_command(command)
            
            except EOFError:
                break

    def _handle_command(self, command: str) -> None:

        print(f"[UCI] {command}")
        
        if command == "uci":
            self._handle_uci()

        elif command == "isready":
            self._handle_isready()

        elif command.startswith("position"):
            self._handle_position(command)

        elif command.startswith("go"):
            self._handle_go(command)

        elif command == "ucinewgame":
            self._handle_newgame()

        elif command == "quit":
            self._handle_quit()

    def _handle_uci(self) -> None:
        print("id name TTNBP-Chess")
        print("id author Phuc")
        print("uciok")

    def _handle_isready(self) -> None:
        print("readyok")

    def _handle_position(self, command: str) -> None:
        tokens = command.split()

        self.board.reset()

        if tokens[1] != "startpos":
            return
        
        if "moves" not in tokens:
            return

        idx = tokens.index("moves")

        moves = tokens[idx + 1:]

        for move in moves:
            self.board.push_uci(move)

    def _handle_go(self, command: str):
        move = self.agent.get_move(self.board)
        print(f"bestmove {move}")

    def _handle_newgame(self) -> None:
        self.board.reset()

    def _handle_quit(self) -> None:
        self.running = False
