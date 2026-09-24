"""Flask application factory."""

from __future__ import annotations

import secrets

from flask import Flask, g, jsonify, render_template

from .store import GameStore


def create_app() -> Flask:
    app = Flask(__name__)
    store = GameStore()
    app.extensions["settlers_store"] = store

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
        return response

    @app.get("/")
    def index():
        return render_template("index.html", csp_nonce=g.csp_nonce)

    @app.get("/api/setup")
    def get_setup():
        return jsonify({"board": store.get_pending_board().client_view()})

    @app.post("/api/setup/regenerate")
    def regenerate():
        return jsonify({"board": store.regenerate_pending_board().client_view()})

    return app
