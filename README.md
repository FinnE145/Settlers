# Settlers

A two-player hex-island trading game for playing over a private network (e.g. Tailscale).
One game runs at a time; players join with a link. No accounts.

The rules the engine enforces are in [docs/RULES.md](docs/RULES.md).

## Running locally

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest         # tests
.venv/bin/gunicorn -k gthread -w 1 --threads 32 -b 127.0.0.1:5000 'settlers.app:create_app()'
```

Then open http://127.0.0.1:5000, create a game, and open the invite link in a second
browser (or a private window) to play the other side.

Use exactly one worker (`-w 1`): the game lives in memory, so restarting the server
also ends the current game. `python run.py` starts Flask's development server instead,
which works but logs a harmless WebSocket error in the browser console when a socket
reconnects.

## Layout

- `settlers/engine/` — rules engine (pure Python, JSON-serialisable state, no web code)
- `settlers/app.py` — Flask app and API
- `settlers/static/` — frontend (Preact + htm, vendored under `static/vendor/`, no build step)
- `tests/` — pytest suite
