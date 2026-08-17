import time

import jwt

ALGORITHM = "HS256"
IFRAME_TOKEN_LEEWAY_SECONDS = 10
SESSION_COOKIE_TTL_SECONDS = 7200


class TokenError(Exception):
    """Levantado quando um token de iframe ou cookie de sessão é inválido."""


def validate_iframe_token(token: str, secret: str) -> str:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            leeway=IFRAME_TOKEN_LEEWAY_SECONDS,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    return payload["sub"]


def issue_session_cookie(
    user_id: str, secret: str, ttl_seconds: int = SESSION_COOKIE_TTL_SECONDS
) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "iat": now, "exp": now + ttl_seconds, "typ": "session"}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def validate_session_cookie(cookie_value: str, secret: str) -> str:
    try:
        payload = jwt.decode(
            cookie_value,
            secret,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub", "typ"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if payload.get("typ") != "session":
        raise TokenError("not a session token")
    return payload["sub"]
