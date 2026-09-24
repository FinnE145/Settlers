"""Holder for the single game this server runs, plus who is seated in it.

Kept behind one small interface so it can later be swapped for something that
persists games (the game state itself is plain JSON-serialisable data).
"""

from __future__ import annotations

import random
import secrets
import threading

from .engine.board import Board, generate_board
from .engine.constants import PLAYER_COLOURS
from .engine.game import Game, RuleError


class GameStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.version = 0
        self.pending_board: Board | None = None
        self.game: Game | None = None
        self.seats: dict[str, int] = {}  # secret player token -> player index
        self.invite_token: str | None = None
        self.creator: int | None = None

    # ---------------------------------------------------------------- changes

    def _bump(self) -> None:
        self.version += 1
        self.changed.notify_all()

    def wait_for_change(self, since: int, timeout: float) -> int:
        with self.changed:
            self.changed.wait_for(lambda: self.version != since, timeout=timeout)
            return self.version

    # ------------------------------------------------------------ new games

    def get_pending_board(self) -> Board:
        with self.lock:
            if self.pending_board is None:
                self.pending_board = generate_board()
            return self.pending_board

    def regenerate_pending_board(self) -> Board:
        with self.lock:
            self._require_no_game()
            self.pending_board = generate_board()
            return self.pending_board

    def _require_no_game(self) -> None:
        if self.game is not None:
            raise RuleError("A game is already running.")

    def create_game(self, colour: str) -> str:
        """Start a game on the previewed board. Returns the creator's player token."""
        if colour not in PLAYER_COLOURS:
            raise RuleError("Pick red or blue.")
        with self.lock:
            self._require_no_game()
            board = self.get_pending_board()
            first = random.SystemRandom().randrange(len(PLAYER_COLOURS))
            self.game = Game(board, first_player=first)
            self.creator = PLAYER_COLOURS.index(colour)
            token = secrets.token_urlsafe(24)
            self.seats = {token: self.creator}
            self.invite_token = secrets.token_urlsafe(24)
            self.pending_board = None
            self._bump()
            return token

    def join(self, invite: str) -> str | None:
        """Take the free seat with an invite token. Returns the new player token."""
        with self.lock:
            if self.game is None or self.invite_token is None:
                return None
            if not secrets.compare_digest(invite, self.invite_token):
                return None
            token = secrets.token_urlsafe(24)
            self.seats[token] = 1 - self.creator
            self.invite_token = None
            self._bump()
            return token

    def abandon(self, token: str | None) -> None:
        with self.lock:
            if self.seat_of(token) is None:
                raise RuleError("Only a player in this game can end it.")
            self.game = None
            self.seats = {}
            self.invite_token = None
            self.creator = None
            self._bump()

    # ------------------------------------------------------------- playing

    def seat_of(self, token: str | None) -> int | None:
        if not token:
            return None
        with self.lock:
            for t, seat in self.seats.items():
                if secrets.compare_digest(t, token):
                    return seat
        return None

    def status(self) -> str:
        if self.game is None:
            return "none"
        if self.invite_token is not None:
            return "waiting"
        return "finished" if self.game.phase == "finished" else "playing"

    def act(self, token: str | None, action) -> None:
        with self.lock:
            seat = self.seat_of(token)
            if self.game is None or seat is None:
                raise RuleError("You're not in this game.")
            if self.invite_token is not None:
                raise RuleError("Waiting for your opponent to join.")
            self.game.act(seat, action)
            self._bump()

    def session_view(self, token: str | None, base_url: str) -> dict:
        with self.lock:
            status = self.status()
            view = {"status": status, "version": self.version}
            if self.game is None:
                return view
            seat = self.seat_of(token)
            if seat is None:
                view["status"] = "occupied"
                return view
            view.update({
                "seat": seat,
                "my_link": f"{base_url}play/{token}",
                "board": self.game.board.client_view(),
                "game": self.game.view_for(seat),
            })
            if status == "waiting" and seat == self.creator:
                view["invite_link"] = f"{base_url}join/{self.invite_token}"
            return view
