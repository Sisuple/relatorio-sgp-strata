import time

import jwt
import pytest
from fastapi.testclient import TestClient

import main
from tokens import ALGORITHM, issue_session_cookie

IFRAME_SECRET = "iframe-secret"
SESSION_SECRET = "session-secret"


@pytest.fixture(autouse=True)
def secrets(monkeypatch):
    monkeypatch.setenv("IFRAME_AUTH_SECRET", IFRAME_SECRET)
    monkeypatch.setenv("GATEWAY_SESSION_SECRET", SESSION_SECRET)


@pytest.fixture
def client():
    return TestClient(main.app)


def _iframe_token(user_id="42", ttl=60):
    return jwt.encode(
        {"sub": user_id, "iat": int(time.time()), "exp": int(time.time()) + ttl},
        IFRAME_SECRET,
        algorithm=ALGORITHM,
    )


def test_missing_token_and_cookie_returns_401(client):
    resp = client.get("/validate", headers={"X-Original-URI": "/", "Cookie": ""})
    assert resp.status_code == 401


def test_valid_token_returns_200_and_sets_cookie(client):
    token = _iframe_token()
    resp = client.get(
        "/validate", headers={"X-Original-URI": f"/?token={token}", "Cookie": ""}
    )
    assert resp.status_code == 200
    assert "dashboard_session=" in resp.headers["set-cookie"]


def test_expired_token_returns_401(client):
    token = _iframe_token(ttl=-60)
    resp = client.get(
        "/validate", headers={"X-Original-URI": f"/?token={token}", "Cookie": ""}
    )
    assert resp.status_code == 401


def test_valid_session_cookie_returns_200_without_token(client):
    cookie = issue_session_cookie("42", SESSION_SECRET)
    resp = client.get(
        "/validate",
        headers={"X-Original-URI": "/", "Cookie": f"dashboard_session={cookie}"},
    )
    assert resp.status_code == 200


def test_tampered_token_returns_401(client):
    token = _iframe_token() + "tampered"
    resp = client.get(
        "/validate", headers={"X-Original-URI": f"/?token={token}", "Cookie": ""}
    )
    assert resp.status_code == 401
