import os
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI, Header
from fastapi.responses import PlainTextResponse

from tokens import (
    SESSION_COOKIE_TTL_SECONDS,
    TokenError,
    issue_session_cookie,
    validate_iframe_token,
    validate_session_cookie,
)

app = FastAPI()

SESSION_COOKIE_NAME = "dashboard_session"


def _extract_token(original_uri: str) -> str | None:
    query = urlsplit(original_uri).query
    values = parse_qs(query).get("token")
    return values[0] if values else None


def _extract_session_cookie(cookie_header: str) -> str | None:
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == SESSION_COOKIE_NAME:
            return value
    return None


@app.get("/validate")
def validate(
    x_original_uri: str = Header(default=""),
    cookie: str = Header(default=""),
):
    iframe_secret = os.environ["IFRAME_AUTH_SECRET"]
    session_secret = os.environ["GATEWAY_SESSION_SECRET"]

    session_cookie = _extract_session_cookie(cookie)
    if session_cookie:
        try:
            validate_session_cookie(session_cookie, session_secret)
            return PlainTextResponse("ok")
        except TokenError:
            pass

    token = _extract_token(x_original_uri)
    if token:
        try:
            user_id = validate_iframe_token(token, iframe_secret)
        except TokenError:
            return PlainTextResponse("invalid token", status_code=401)
        new_cookie = issue_session_cookie(user_id, session_secret)
        ok_response = PlainTextResponse("ok")
        ok_response.headers["Set-Cookie"] = (
            f"{SESSION_COOKIE_NAME}={new_cookie}; Path=/; "
            f"Max-Age={SESSION_COOKIE_TTL_SECONDS}; HttpOnly; Secure; SameSite=Lax"
        )
        return ok_response

    return PlainTextResponse("missing credentials", status_code=401)
