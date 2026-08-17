import time

import jwt
import pytest

from tokens import (
    ALGORITHM,
    TokenError,
    issue_session_cookie,
    validate_iframe_token,
    validate_session_cookie,
)

SECRET = "test-secret"


def test_validate_iframe_token_accepts_valid_token():
    token = jwt.encode(
        {"sub": "42", "iat": int(time.time()), "exp": int(time.time()) + 60},
        SECRET,
        algorithm=ALGORITHM,
    )
    assert validate_iframe_token(token, SECRET) == "42"


def test_validate_iframe_token_rejects_expired_token():
    token = jwt.encode(
        {"sub": "42", "iat": int(time.time()) - 120, "exp": int(time.time()) - 60},
        SECRET,
        algorithm=ALGORITHM,
    )
    with pytest.raises(TokenError):
        validate_iframe_token(token, SECRET)


def test_validate_iframe_token_rejects_wrong_secret():
    token = jwt.encode(
        {"sub": "42", "iat": int(time.time()), "exp": int(time.time()) + 60},
        SECRET,
        algorithm=ALGORITHM,
    )
    with pytest.raises(TokenError):
        validate_iframe_token(token, "wrong-secret")


def test_validate_iframe_token_rejects_missing_sub():
    token = jwt.encode(
        {"iat": int(time.time()), "exp": int(time.time()) + 60},
        SECRET,
        algorithm=ALGORITHM,
    )
    with pytest.raises(TokenError):
        validate_iframe_token(token, SECRET)


def test_issue_and_validate_session_cookie_roundtrip():
    cookie = issue_session_cookie("42", SECRET, ttl_seconds=7200)
    assert validate_session_cookie(cookie, SECRET) == "42"


def test_validate_session_cookie_rejects_expired():
    cookie = issue_session_cookie("42", SECRET, ttl_seconds=-1)
    with pytest.raises(TokenError):
        validate_session_cookie(cookie, SECRET)


def test_validate_session_cookie_rejects_iframe_token():
    # um token sem claim "typ=session" (ex.: o token curto do iframe) não
    # pode ser aceito como cookie de sessão
    token = jwt.encode(
        {"sub": "42", "iat": int(time.time()), "exp": int(time.time()) + 60},
        SECRET,
        algorithm=ALGORITHM,
    )
    with pytest.raises(TokenError):
        validate_session_cookie(token, SECRET)
