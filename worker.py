"""A disposable, persistent AI process: search never owns the event loop."""

import logging
import multiprocessing as mp
from multiprocessing.connection import Connection
from typing import Any

from ai import SearchResult, choose_move
from board import Board

LOG = logging.getLogger(__name__)


def _serve(connection: Connection) -> None:
    try:
        while True:
            request = connection.recv()
            if request is None:
                return
            board, difficulty, depth, budget = request
            try:
                connection.send((choose_move(board, difficulty, depth, budget), None))
            except Exception as exc:
                connection.send((None, f"{type(exc).__name__}: {exc}"))
    except (EOFError, BrokenPipeError, OSError):
        return
    finally:
        connection.close()


class AIWorker:
    def __init__(self) -> None:
        self.process: Any = None
        self.connection: Connection | None = None
        self.busy = False

    def submit(self, board: Board, difficulty: str, depth: int, budget: float) -> None:
        if self.busy:
            raise RuntimeError("AI already has a pending position")
        if self.process is None or not self.process.is_alive():
            self.close()
            context = mp.get_context("spawn")
            parent, child = context.Pipe()
            process = context.Process(target=_serve, args=(child,), daemon=True,
                                      name="Hexxagon-CPU")
            try:
                process.start()
            except (OSError, RuntimeError):
                parent.close()
                child.close()
                process.close()
                raise
            self.process = process
            child.close()
            self.connection = parent
        self.connection.send((board, difficulty, depth, budget))
        self.busy = True

    def poll(self) -> tuple[SearchResult | None, str | None] | None:
        if not self.busy or self.connection is None:
            return None
        try:
            if self.connection.poll():
                self.busy = False
                return self.connection.recv()
            if self.process is not None and not self.process.is_alive():
                self.busy = False
                return None, "AI process stopped unexpectedly"
        except (EOFError, BrokenPipeError, OSError) as exc:
            self.busy = False
            return None, str(exc)
        return None

    def close(self) -> None:
        """Cancel owned work on restart/quit, including a search already running."""
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=0.5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=0.5)
            self.process.close()
        if self.connection is not None:
            self.connection.close()
        self.process = None
        self.connection = None
        self.busy = False
