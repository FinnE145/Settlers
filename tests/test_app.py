import pytest

from settlers.app import SEAT_COOKIE, create_app


@pytest.fixture
def app():
    return create_app()


def client(app):
    return app.test_client()


def post(c, url, body=None):
    return c.post(url, json=body or {})


def cookie(c):
    ck = c.get_cookie(SEAT_COOKIE)
    return ck.value if ck else None


def start_game(app, colour="red"):
    host = client(app)
    res = post(host, "/api/game", {"colour": colour})
    assert res.status_code == 200
    invite = res.get_json()["invite_link"]
    guest = client(app)
    res = guest.get(invite.replace("http://localhost", ""))
    assert res.status_code == 302
    return host, guest


def test_security_headers(app):
    res = client(app).get("/")
    assert "nonce-" in res.headers["Content-Security-Policy"]
    assert res.headers["Referrer-Policy"] == "no-referrer"
    assert res.headers["X-Frame-Options"] == "DENY"


def test_setup_preview_and_regenerate(app):
    c = client(app)
    a = c.get("/api/setup").get_json()["board"]
    assert a == c.get("/api/setup").get_json()["board"]
    b = post(c, "/api/setup/regenerate").get_json()["board"]
    assert b["terrain"] != a["terrain"]


def test_posts_require_json(app):
    c = client(app)
    assert c.post("/api/setup/regenerate", data="x").status_code == 415
    assert c.post("/api/game", data={"colour": "red"}).status_code == 415


def test_create_join_and_seats(app):
    host, guest = start_game(app, colour="blue")
    hv = host.get("/api/session").get_json()
    gv = guest.get("/api/session").get_json()
    assert hv["status"] == gv["status"] == "playing"
    assert hv["seat"] == 1 and gv["seat"] == 0
    assert "invite_link" not in hv
    # A stranger sees that a game is running but nothing about it.
    sv = client(app).get("/api/session").get_json()
    assert sv == {"status": "occupied", "version": sv["version"]}
    # Setup is locked while a game runs.
    assert post(client(app), "/api/setup/regenerate").status_code == 400
    assert post(client(app), "/api/game", {"colour": "red"}).status_code == 400


def test_invite_only_works_once(app):
    host = client(app)
    invite = post(host, "/api/game", {"colour": "red"}).get_json()["invite_link"]
    path = invite.replace("http://localhost", "")
    assert client(app).get(path).status_code == 302
    assert client(app).get(path).status_code == 404


def test_actions_wait_for_opponent_and_follow_turns(app):
    host = client(app)
    post(host, "/api/game", {"colour": "red"})
    res = post(host, "/api/action", {"action": {"type": "roll"}})
    assert res.status_code == 400 and "Waiting" in res.get_json()["error"]

    invite = host.get("/api/session").get_json()["invite_link"]
    guest = client(app)
    guest.get(invite.replace("http://localhost", ""))
    view = host.get("/api/session").get_json()
    first = view["game"]["setup"]["player"]
    mover, other = (host, guest) if view["seat"] == first else (guest, host)
    spot = mover.get("/api/session").get_json()["game"]["legal"]["settlement"][0]
    res = post(other, "/api/action", {"action": {"type": "build_settlement", "vertex": spot}})
    assert res.status_code == 400
    res = post(mover, "/api/action", {"action": {"type": "build_settlement", "vertex": spot}})
    assert res.status_code == 200


def test_player_link_restores_seat(app):
    host, _ = start_game(app)
    link = host.get("/api/session").get_json()["my_link"]
    other_device = client(app)
    assert other_device.get(link.replace("http://localhost", "")).status_code == 302
    assert other_device.get("/api/session").get_json()["seat"] == 0
    assert client(app).get("/play/not-a-token").status_code == 404


def test_abandon(app):
    host, guest = start_game(app)
    assert post(client(app), "/api/abandon").status_code == 400
    assert post(guest, "/api/abandon").status_code == 200
    assert host.get("/api/session").get_json()["status"] == "none"


# ------------------------------------------------------------ saving


def test_game_survives_a_restart(tmp_path):
    from settlers.store import GameStore

    save = str(tmp_path / "game.json")
    app1 = create_app(GameStore(save))
    host, guest = start_game(app1)
    view = host.get("/api/session").get_json()
    first = view["game"]["setup"]["player"]
    mover = host if view["seat"] == first else guest
    spot = mover.get("/api/session").get_json()["game"]["legal"]["settlement"][0]
    assert post(mover, "/api/action", {"action": {"type": "build_settlement", "vertex": spot}}).status_code == 200
    token = cookie(host)

    app2 = create_app(GameStore(save))  # a fresh server reading the same file
    again = app2.test_client()
    again.set_cookie(SEAT_COOKIE, token)
    restored = again.get("/api/session").get_json()
    before = host.get("/api/session").get_json()
    assert restored["status"] == "playing"
    assert restored["game"]["buildings"] == before["game"]["buildings"]
    assert restored["board"] == before["board"]


def test_unreadable_save_is_set_aside(tmp_path):
    from settlers.store import GameStore

    save = tmp_path / "game.json"
    save.write_text("{not json")
    store = GameStore(str(save))
    assert store.game is None
    assert (tmp_path / "game.json.unreadable").exists()


def test_ending_a_game_is_saved(tmp_path):
    from settlers.store import GameStore

    save = str(tmp_path / "game.json")
    app1 = create_app(GameStore(save))
    host, _ = start_game(app1)
    post(host, "/api/abandon")
    assert GameStore(save).game is None


# ---------------------------------------------------------- network


def test_only_allowed_networks_get_in(app):
    app = create_app(allowed_networks="100.64.0.0/10,127.0.0.0/8")
    outside = app.test_client()
    outside.environ_base["REMOTE_ADDR"] = "203.0.113.9"
    assert outside.get("/").status_code == 403
    assert outside.get("/api/session").status_code == 403
    tailnet = app.test_client()
    tailnet.environ_base["REMOTE_ADDR"] = "100.101.2.3"
    assert tailnet.get("/").status_code == 200
    mapped = app.test_client()
    mapped.environ_base["REMOTE_ADDR"] = "::ffff:100.101.2.3"
    assert mapped.get("/").status_code == 200


def test_large_bodies_are_refused(app):
    c = client(app)
    res = c.post("/api/action", data="x" * (70 * 1024), content_type="application/json")
    assert res.status_code == 413
