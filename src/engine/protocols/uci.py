import sys

import chess
from engine.agents.interface import Agent

class UCIProtocol:

    def __init__(self, agent: Agent):
        self.agent = agent
        self.board = chess.Board()
        self.running = True

    def loop(self):
        # while self.running:
        #     try:
        #         command = input().strip()
        #         self._handle_command(command)
            
        #     except EOFError:
        #         break
        while self.running:
            line = sys.stdin.readline()
            if not line:
                break
            command = line.strip()
            self._handle_command(command)


    def _handle_command(self, command: str) -> None:
        
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
        self._send("id name TTNBP-Chess")
        self._send("id author Phuc")
        self._send("uciok")

    def _handle_isready(self) -> None:
        self._send("readyok")

    def _handle_position(self, command: str) -> None:
        tokens = command.split()

        self.board.reset()

        if "startpos" in tokens:
                if "moves" in tokens:
                    idx = tokens.index("moves")
                    moves = tokens[idx + 1:]
                    for m in moves:
                        self.board.push_uci(m)

        elif "fen" in tokens:
            fen_idx = tokens.index("fen") + 1
            moves_idx = tokens.index("moves") if "moves" in tokens else len(tokens)

            fen = " ".join(tokens[fen_idx:moves_idx])
            self.board.set_fen(fen)

            if "moves" in tokens:
                for m in tokens[moves_idx + 1:]:
                    self.board.push_uci(m)

    def _handle_go(self, command: str):
        move = self.agent.get_move(self.board)
        self._send(f"bestmove {move.uci()}")

    def _handle_newgame(self) -> None:
        self.board.reset()

    def _handle_quit(self) -> None:
        self.running = False

    def _send(self, msg):
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()
