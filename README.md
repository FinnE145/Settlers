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

## Deploying with Docker

On the server (Ubuntu with Docker and Tailscale):

```sh
git clone https://github.com/FinnE145/Settlers.git && cd Settlers
docker compose up -d --build
```

Then open `http://fe-pro:45670` from any device on the tailnet, create a game and send
the invite link to your opponent.

- **Saving:** the running game is written to the `settlers-data` volume after every move,
  so restarting or updating the container keeps it. `docker compose down -v` deletes it.
- **Updating:** `git pull && docker compose up -d --build`.
- **Logs:** `docker compose logs -f`.
- **Who can connect:** the app only answers Tailscale addresses (`100.64.0.0/10` and
  `fd7a:115c:a1e0::/48`); anything else gets a 403. Docker publishes ports on every
  interface and bypasses `ufw`, which is why the app checks addresses itself. Opening it
  from the server via `localhost` also gets a 403 (that traffic arrives from Docker's
  bridge network), so use the Tailscale name.
- **Closing the port entirely off-tailnet (optional):** publish it on the server's
  Tailscale IP only (`tailscale ip -4`), e.g. `- "100.x.y.z:45670:8000"` in
  `docker-compose.yml`. The container can then only start once Tailscale is up.
- **Settings** (environment variables, set in the `Dockerfile`, overridable in
  `docker-compose.yml`): `SETTLERS_SAVE_FILE`, `SETTLERS_ALLOWED_NETWORKS`.

Run the random-game simulation with `.venv/bin/python -m tests.simulate 100`.
