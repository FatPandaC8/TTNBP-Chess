import chess
from engine.agents.interface import Agent

class Match:
    def __init__(
        self,
        board: chess.Board,
        white_agent: Agent,
        black_agent: Agent,
    ):
        self.board = board
        self.white_agent = white_agent
        self.black_agent = black_agent

    def current_agent(self) -> Agent:
        return self.white_agent if self.board.turn == chess.WHITE else self.black_agent


    def play_turn(self) -> chess.Move:
        agent = self.current_agent()

        board_copy = self.board.copy()

        try:
            move = agent.get_move(board_copy)

            if move is None:
                raise ValueError("Agent returned None")

            self.validate_move(move)

        except Exception as e:
            raise e

        self.board.push(move)
        return move

    def validate_move(self, move: chess.Move):
        if not self.board.is_legal(move):
            raise ValueError(f"Illegal move: {move}")

    def is_over(self) -> bool:
        return self.board.is_game_over()

    def result(self) -> str:
        return self.board.result()