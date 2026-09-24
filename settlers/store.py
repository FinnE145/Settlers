"""In-memory holder for the single game this server runs.

Kept behind one small interface so it can later be swapped for something that
persists games (the game state itself is plain JSON-serialisable data).
"""

from __future__ import annotations

import threading

from .engine.board import Board, generate_board


class GameStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.pending_board: Board | None = None

    def get_pending_board(self) -> Board:
        with self.lock:
            if self.pending_board is None:
                self.pending_board = generate_board()
            return self.pending_board

    def regenerate_pending_board(self) -> Board:
        with self.lock:
            self.pending_board = generate_board()
            return self.pending_board
