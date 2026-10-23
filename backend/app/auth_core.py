import base64
import hashlib
import hmac
import secrets
import sqlite3
import time

# 로그인 유지 시간은 30분이고 마지막 로그인부터 센다. 요청마다 연장하지 않는다. (D-025)
SESSION_TTL_SECONDS = 30 * 60

# scrypt 설정. 해시 문자열에 함께 저장해 나중에 바꿔도 예전 해시를 검증할 수 있다.
_N, _R, _P = 2**14, 8, 1


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, _N, _R, _P)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    # 해시가 없는 계정(이전용 계정이 가입으로 받기 전)은 어떤 비밀번호로도 통과하지 못한다. (D-024)
    if not stored:
        return False
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = _scrypt(password, base64.b64decode(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def create_session(conn: sqlite3.Connection, user_id: int, now: int | None = None) -> str:
    now = int(time.time()) if now is None else now
    session_id = secrets.token_urlsafe(32)
    with conn:
        # 만료된 세션은 로그인할 때 지운다.
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        conn.execute(
            "INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)",
            (session_id, user_id, now + SESSION_TTL_SECONDS),
        )
    return session_id


def get_session_user_id(
    conn: sqlite3.Connection, session_id: str, now: int | None = None
) -> int | None:
    now = int(time.time()) if now is None else now
    row = conn.execute(
        "SELECT user_id, expires_at FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if row is None or row["expires_at"] <= now:
        return None
    return row["user_id"]


def delete_session(conn: sqlite3.Connection, session_id: str) -> None:
    with conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def _sign(session_id: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), session_id.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_cookie(session_id: str, secret: str) -> str:
    return f"{session_id}.{_sign(session_id, secret)}"


def read_cookie(value: str | None, secret: str) -> str | None:
    # 서명이 맞지 않으면 세션 구분값을 DB 조회에 쓰지 않는다.
    if not value or "." not in value:
        return None
    session_id, _, sig = value.rpartition(".")
    if not session_id or not hmac.compare_digest(sig, _sign(session_id, secret)):
        return None
    return session_id
