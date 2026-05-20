from pathlib import Path
import json
import threading
import queue
import atexit

from .date_time import timestamp


class Logger:
    def __init__(self, log_dir="logs", batch_size=100):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        self.filepath = self.log_dir / f"engine_{timestamp()}.log"

        self.batch_size = batch_size
        self.q = queue.Queue()
        self.buffer = []

        self._stop_event = threading.Event()

        # start background worker
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

        # safety flush on exit
        # allow programmer to define multiple exit functions to be executed
        # upon normal program termination.
        atexit.register(self.close)

    def _write(self, data: dict):
        self.q.put(json.dumps(data))

    def _run(self):
        while not self._stop_event.is_set() or not self.q.empty():
            try:
                item = self.q.get(timeout=0.2)
                self.buffer.append(item)

                if len(self.buffer) >= self.batch_size:
                    self._flush_buffer()

            except queue.Empty:
                # periodic flush even if batch not full
                if self.buffer:
                    self._flush_buffer()

        # final flush
        self._flush_buffer()

    def _flush_buffer(self):
        if not self.buffer:
            return

        with open(self.filepath, "a") as f:
            f.write("\n".join(self.buffer) + "\n")

        self.buffer.clear()

    def close(self):
        self._stop_event.set()
        self.worker.join(timeout=2)
        self._flush_buffer()

    def log_match_start(self):
        self._write({"type": "match_start"})

    def log_match_result(self, result):
        self._write({"type": "match_result", "result": result})

    def log_move(self, move, board):
        self._write({
            "type": "move",
            "move": str(move),
            "fen": board.fen()
        })

    def log_search(self, score, move, depth, time):
        self._write({
            "type": "search",
            "move": str(move),
            "score": score,
            "depth": depth,
            "time": time
        })