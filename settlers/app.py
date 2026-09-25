"""Flask application factory: pages, JSON API and the live-update socket."""

from __future__ import annotations

import ipaddress
import json
import os
import secrets
import time
from urllib.parse import urlsplit

from flask import Flask, abort, g, jsonify, make_response, redirect, render_template, request
from flask_sock import ConnectionClosed, Sock

from .engine.game import RuleError
from .store import GameStore

SEAT_COOKIE = "settlers_seat"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30
PING_SECONDS = 20


def parse_networks(spec: str | None) -> list:
    """Comma-separated CIDRs, e.g. "100.64.0.0/10,127.0.0.0/8". Empty means allow all."""
    if not spec:
        return []
    return [ipaddress.ip_network(part.strip(), strict=False) for part in spec.split(",") if part.strip()]


def address_allowed(address: str | None, networks: list) -> bool:
    if not networks:
        return True
    try:
        ip = ipaddress.ip_address(address or "")
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return any(ip in net for net in networks if net.version == ip.version)


def create_app(store: GameStore | None = None, allowed_networks: str | None = None) -> Flask:
    """Settings come from arguments, falling back to environment variables:

    SETTLERS_SAVE_FILE         where to keep the running game (unset: memory only)
    SETTLERS_ALLOWED_NETWORKS  comma-separated CIDRs allowed to connect (unset: anyone)
    """
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    store = store or GameStore(os.environ.get("SETTLERS_SAVE_FILE") or None)
    networks = parse_networks(allowed_networks if allowed_networks is not None
                              else os.environ.get("SETTLERS_ALLOWED_NETWORKS"))
    app.extensions["settlers_store"] = store
    sock = Sock(app)

    def token() -> str | None:
        return request.cookies.get(SEAT_COOKIE)

    def with_seat_cookie(response, seat_token: str):
        response.set_cookie(SEAT_COOKIE, seat_token, max_age=COOKIE_MAX_AGE,
                            httponly=True, samesite="Lax")
        return response

    def json_body() -> dict:
        # Requiring a JSON content type means a cross-site form can't post here.
        if not request.is_json:
            abort(415)
        body = request.get_json(silent=True)
        return body if isinstance(body, dict) else {}

    def same_origin() -> bool:
        origin = request.headers.get("Origin")
        return origin is None or urlsplit(origin).netloc == request.host

    @app.errorhandler(RuleError)
    def rule_error(err):
        return jsonify({"error": str(err)}), 400

    @app.before_request
    def check_network():
        if not address_allowed(request.remote_addr, networks):
            app.logger.warning("Refused a request from %s", request.remote_addr)
            abort(403)

    @app.before_request
    def make_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.after_request
    def security_headers(response):
        nonce = getattr(g, "csp_nonce", "")
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # Player links carry secret tokens; never leak them via Referer.
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    # ------------------------------------------------------------------ pages

    @app.get("/")
    def index():
        return render_template("index.html", csp_nonce=g.csp_nonce)

    @app.get("/play/<seat_token>")
    def play_link(seat_token):
        if store.seat_of(seat_token) is None:
            return render_template("message.html", csp_nonce=g.csp_nonce,
                                   message="That player link isn't part of the current game."), 404
        return with_seat_cookie(redirect("/"), seat_token)

    @app.get("/join/<invite>")
    def join_link(invite):
        if store.seat_of(token()) is not None:
            return redirect("/")
        seat_token = store.join(invite)
        if seat_token is None:
            return render_template("message.html", csp_nonce=g.csp_nonce,
                                   message="That invite link has already been used or has expired."), 404
        return with_seat_cookie(redirect("/"), seat_token)

    # -------------------------------------------------------------------- API

    @app.get("/api/session")
    def session():
        return jsonify(store.session_view(token(), request.host_url))

    @app.get("/api/setup")
    def get_setup():
        return jsonify({"board": store.get_pending_board().client_view()})

    @app.post("/api/setup/regenerate")
    def regenerate():
        json_body()
        return jsonify({"board": store.regenerate_pending_board().client_view()})

    @app.post("/api/game")
    def create_game():
        body = json_body()
        seat_token = store.create_game(body.get("colour"))
        view = store.session_view(seat_token, request.host_url)
        return with_seat_cookie(make_response(jsonify(view)), seat_token)

    @app.post("/api/action")
    def action():
        body = json_body()
        store.act(token(), body.get("action"))
        return jsonify({"ok": True})

    @app.post("/api/abandon")
    def abandon():
        json_body()
        store.abandon(token())
        return jsonify({"ok": True})

    @sock.route("/ws")
    def live(ws):
        if not same_origin():
            ws.close(reason=1008, message="Bad origin")
            return
        seat_token = token()
        base_url = request.host_url
        seen = -1
        last_sent = time.monotonic()
        try:
            # Short waits so a socket the client has closed is released promptly.
            while ws.connected:
                version = store.wait_for_change(seen, timeout=1.0)
                if version != seen:
                    seen = version
                    view = store.session_view(seat_token, base_url)
                    ws.send(json.dumps({"type": "session", "data": view}))
                    last_sent = time.monotonic()
                elif time.monotonic() - last_sent >= PING_SECONDS:
                    ws.send('{"type":"ping"}')
                    last_sent = time.monotonic()
        except ConnectionClosed:
            pass

    return app
