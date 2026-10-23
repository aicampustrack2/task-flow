import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth_core import (
    SESSION_TTL_SECONDS,
    create_session,
    delete_session,
    get_session_user_id,
    hash_password,
    read_cookie,
    sign_cookie,
    verify_password,
)
from app.config import get_session_secret
from app.db import connect
from app.rules import RuleError, validate_password, validate_username
from app.schemas import Credentials, User

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "session"
_UNAUTHORIZED = "로그인이 필요합니다."
_LOGIN_FAILED = "아이디 또는 비밀번호가 맞지 않습니다."

_dummy_hash: str | None = None


def _get_dummy_hash() -> str:
    # 없는 아이디도 해시 계산을 한 번 하게 해서 응답 시간으로 아이디 유무가 드러나지 않게 한다.
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("dummy-password")
    return _dummy_hash


def _to_user(row) -> User:
    return User(id=row["id"], username=row["username"])


def _session_id_from(request: Request) -> str | None:
    return read_cookie(request.cookies.get(COOKIE_NAME), get_session_secret())


def current_user(request: Request) -> User:
    # 로그인 안 됨은 401이다. 읽기 실패는 예외가 그대로 오류 응답이 되어 401로 오해되지 않는다.
    session_id = _session_id_from(request)
    if session_id is None:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED)
    conn = connect()
    try:
        user_id = get_session_user_id(conn, session_id)
        row = (
            None
            if user_id is None
            else conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
        )
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED)
    return _to_user(row)


@router.post("/signup", response_model=User, status_code=201)
def signup(body: Credentials) -> User:
    try:
        username = validate_username(body.username)
        password = validate_password(body.password)
    except RuleError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    password_hash = hash_password(password)
    taken = HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.")
    conn = connect()
    try:
        # 저장(commit)이 끝난 뒤에만 응답한다. (D-004)
        with conn:
            row = conn.execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()
            if row is None:
                try:
                    user_id = conn.execute(
                        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (username, password_hash),
                    ).lastrowid
                except sqlite3.IntegrityError:
                    raise taken from None
            elif row["password_hash"] is None:
                # 이전용 계정이 처음 가입으로 비밀번호를 정해 계정과 기존 Task를 받는다. (D-024)
                # 비밀번호 설정은 아직 비어 있을 때만 한 번 통한다.
                cur = conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ? AND password_hash IS NULL",
                    (password_hash, row["id"]),
                )
                if cur.rowcount != 1:
                    raise taken
                user_id = row["id"]
            else:
                raise taken
        saved = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()
    return _to_user(saved)


@router.post("/login", response_model=User)
def login(body: Credentials, response: Response) -> User:
    failed = HTTPException(status_code=401, detail=_LOGIN_FAILED)
    # 로그인에는 가입 규칙(길이 등)을 다시 적용하지 않는다. 형식이 안 맞으면 그냥 실패다.
    if not isinstance(body.username, str) or not isinstance(body.password, str):
        raise failed
    username = body.username.strip().lower()

    conn = connect()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
        ok = verify_password(body.password, row["password_hash"] if row else _get_dummy_hash())
        if row is None or not ok:
            raise failed
        session_id = create_session(conn, row["id"])
    finally:
        conn.close()

    response.set_cookie(
        COOKIE_NAME,
        sign_cookie(session_id, get_session_secret()),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return _to_user(row)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    # 로그인하지 않은 상태의 로그아웃은 401이다. 현재 세션만 끝낸다.
    session_id = _session_id_from(request)
    if session_id is None:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED)
    conn = connect()
    try:
        if get_session_user_id(conn, session_id) is None:
            raise HTTPException(status_code=401, detail=_UNAUTHORIZED)
        delete_session(conn, session_id)
    finally:
        conn.close()
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=User)
def me(user: User = Depends(current_user)) -> User:
    return user
