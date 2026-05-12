from pathlib import Path
from datetime import datetime
import json

class Logger:

    def __init__(self, log_dir="logs"):

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.filepath = self.log_dir / f"engine_{timestamp}.log"

    def _write(self, data: dict):

        with open(self.filepath, "a") as f:
            f.write(json.dumps(data) + "\n")

    # =========================
    # MATCH
    # =========================

    def log_match_start(self):

        self._write({
            "type": "match_start"
        })

    def log_match_result(self, result):

        self._write({
            "type": "match_result",
            "result": result
        })

    # =========================
    # MOVE
    # =========================

    def log_move(self, move, board):

        self._write({
            "type": "move",
            "move": str(move),
            "fen": board.fen()
        })