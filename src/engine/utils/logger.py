from pathlib import Path
from collections import deque
import threading
import atexit
import time
import orjson

from .date_time import timestamp


class Logger:
    def __init__(
        self,
        log_dir="logs",
        filename="engine.jsonl",   # single persistent file
        batch_size=32,             # lower for more realtime logging
        flush_interval=0.05,
        queue_size=4096,
    ):
        self.cutoff_count = 0

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # ONE FILE ONLY
        self.filepath = self.log_dir / filename

        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # fast append/pop queue
        self.q = deque(maxlen=queue_size)

        # write batch buffer
        self.buffer = []

        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # persistent binary file handle
        self.file = open(
            self.filepath,
            "ab",
            buffering=1024 * 1024
        )

        # background writer thread
        self.worker = threading.Thread(
            target=self._run,
            daemon=True
        )
        self.worker.start()

        atexit.register(self.close)

    # ---------------------------------------------------------
    # Internal enqueue
    # ---------------------------------------------------------

    def _write(self, data: dict):
        serialized = orjson.dumps(data)

        with self._lock:
            self.q.append(serialized)

    # ---------------------------------------------------------
    # Worker loop
    # ---------------------------------------------------------

    def _run(self):
        last_flush = time.monotonic()

        while not self._stop_event.is_set() or self.q:
            self._drain_queue()

            now = time.monotonic()

            should_flush = (
                len(self.buffer) >= self.batch_size
                or (
                    self.buffer
                    and now - last_flush >= self.flush_interval
                )
            )

            if should_flush:
                self._flush_buffer()
                last_flush = now

        # final flush during shutdown
        self._flush_buffer()

    def _drain_queue(self):
        with self._lock:
            while self.q:
                self.buffer.append(
                    self.q.popleft()
                )

    # ---------------------------------------------------------
    # Disk IO
    # ---------------------------------------------------------

    def _flush_buffer(self):
        if not self.buffer:
            return

        self.file.write(
            b"\n".join(self.buffer) + b"\n"
        )

        # IMPORTANT:
        # makes logs visible while engine is running
        self.file.flush()

        # optional:
        # force physical disk sync
        # slower but safest
        #
        # os.fsync(self.file.fileno())

        self.buffer.clear()

    # ---------------------------------------------------------
    # Shutdown
    # ---------------------------------------------------------

    def close(self):
        if self._stop_event.is_set():
            return

        self._stop_event.set()

        self.worker.join(timeout=2)

        self._flush_buffer()

        self.file.flush()
        self.file.close()

    # ---------------------------------------------------------
    # Log APIs
    # ---------------------------------------------------------

    def log_match_start(self):
        self._write({
            "type": "match_start",
            "ts": timestamp()
        })

    def log_match_result(self, result):
        self._write({
            "type": "match_result",
            "result": result,
            "ts": timestamp()
        })

    def log_move(self, move, board):
        self._write({
            "type": "move",
            "move": str(move),
            "fen": board.fen(),
            "ts": timestamp()
        })

    def log_search(
        self,
        score,
        move,
        depth,
        time_ms,
    ):
        self._write({
            "type": "search",
            "move": str(move),
            "score": score,
            "depth": depth,
            "time_ms": time_ms,
            "ts": timestamp()
        })

    def log_cutoff(self, depth, move):
        """
        Useage: find the place of your pruning
        for example: 
        if alpha >= beta:
        
        Replace with:
        if alpha >= beta:
            self.logger.cutoff_count += 1
            self.logger.log_cutoff(depth, move)
        """
        self._write({
            "type": "cutoff",
            "move": str(move),
            "depth": depth,
            "ts": timestamp()
        })
