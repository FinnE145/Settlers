# Settlers

A two-player hex-island trading game for playing over a private network (e.g. Tailscale).
One game runs at a time; players join with a link. No accounts.

The rules the engine enforces are in [docs/RULES.md](docs/RULES.md).

## Running locally

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python run.py            # http://127.0.0.1:5000
.venv/bin/python -m pytest         # tests
```

## Layout

- `settlers/engine/` — rules engine (pure Python, JSON-serialisable state, no web code)
- `settlers/app.py` — Flask app and API
- `settlers/static/` — frontend (Preact + htm, vendored under `static/vendor/`, no build step)
- `tests/` — pytest suite
