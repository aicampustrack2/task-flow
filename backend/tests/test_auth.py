import os
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path

from fastapi import HTTPException, Response
from starlette.requests import Request

from app.auth import COOKIE_NAME, current_user, login, logout, me, signup
from app.db import connect, init_db
from app.schemas import Credentials

# 테스트용 가짜 값이다.
SECRET = "fake-secret-for-test"
PW = "fake-password-1"


def req(cookie: str | None = None) -> Request:
    headers = [(b"cookie", f"{COOKIE_NAME}={cookie}".encode())] if cookie else []
    return Request({"type": "http", "headers": headers})


def cookie_value(response: Response) -> str:
    c = SimpleCookie()
    for h in response.headers.getlist("set-cookie"):
        c.load(h)
    return c[COOKIE_NAME].value


class AuthBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = {k: os.environ.get(k) for k in ("TASKFLOW_DB", "SESSION_SECRET")}
        os.environ["TASKFLOW_DB"] = str(Path(self._tmp.name) / "test.db")
        os.environ["SESSION_SECRET"] = SECRET
        init_db()

    def tearDown(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()

    def count(self, table):
        conn = connect()
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()

    def do_signup(self, username="a@test.com", password=PW):
        return signup(Credentials(username=username, password=password))

    def do_login(self, username="a@test.com", password=PW):
        resp = Response()
        user = login(Credentials(username=username, password=password), resp)
        return user, resp

    def error_of(self, fn, *args):
        with self.assertRaises(HTTPException) as cm:
            fn(*args)
        return cm.exception

    def status_of(self, fn, *args):
        return self.error_of(fn, *args).status_code


class SignupTest(AuthBase):
    def test_signup_returns_public_info_only(self):
        user = self.do_signup()
        self.assertEqual(user.model_dump(), {"id": user.id, "username": "a@test.com"})

    def test_password_is_stored_as_hash(self):
        self.do_signup()
        conn = connect()
        stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
        conn.close()
        self.assertNotIn(PW, stored)

    def test_username_is_normalized(self):
        self.assertEqual(self.do_signup("  A@Test.COM ").username, "a@test.com")

    def test_duplicate_is_409_case_insensitive(self):
        self.do_signup()
        self.assertEqual(self.status_of(self.do_signup, "A@test.com"), 409)
        self.assertEqual(self.count("users"), 1)

    def test_rule_violations_are_422_and_store_nothing(self):
        for name, pw in [
            ("not-an-email", PW),
            ("", PW),
            (None, PW),
            ("a@test.com", "short"),
            ("a@test.com", None),
            ("a@test.com", "x" * 129),
        ]:
            self.assertEqual(self.status_of(self.do_signup, name, pw), 422, (name, pw))
        self.assertEqual(self.count("users"), 0)


class LoginSessionTest(AuthBase):
    def test_full_flow_signup_login_me_logout(self):
        self.do_signup()
        user, resp = self.do_login()
        cookie = cookie_value(resp)
        self.assertEqual(user.username, "a@test.com")
        self.assertEqual(me(current_user(req(cookie))).username, "a@test.com")

        logout(req(cookie), Response())
        self.assertEqual(self.status_of(current_user, req(cookie)), 401)
        self.assertEqual(self.count("sessions"), 0)

    def test_cookie_attributes(self):
        self.do_signup()
        _, resp = self.do_login()
        header = resp.headers.getlist("set-cookie")[0].lower()
        self.assertIn("httponly", header)
        self.assertIn("samesite=lax", header)
        self.assertIn("max-age=1800", header)

    def test_wrong_password_and_unknown_user_look_the_same(self):
        self.do_signup()
        a = self.error_of(self.do_login, "a@test.com", "wrong-password")
        b = self.error_of(self.do_login, "none@test.com", PW)
        self.assertEqual((a.status_code, a.detail), (b.status_code, b.detail))
        self.assertEqual(a.status_code, 401)

    def test_failed_login_creates_no_session(self):
        self.do_signup()
        self.status_of(self.do_login, "a@test.com", "wrong-password")
        self.assertEqual(self.count("sessions"), 0)

    def test_malformed_login_is_401(self):
        self.assertEqual(self.status_of(self.do_login, None, None), 401)
        self.assertEqual(self.status_of(self.do_login, 1, 2), 401)

    def test_no_cookie_is_401(self):
        self.assertEqual(self.status_of(current_user, req()), 401)

    def test_tampered_cookie_is_401(self):
        self.do_signup()
        _, resp = self.do_login()
        cookie = cookie_value(resp)
        self.assertEqual(self.status_of(current_user, req("x" + cookie)), 401)
        self.assertEqual(self.status_of(current_user, req(cookie[:-2] + "00")), 401)

    def test_expired_session_is_401(self):
        self.do_signup()
        _, resp = self.do_login()
        conn = connect()
        with conn:
            conn.execute("UPDATE sessions SET expires_at = 1")
        conn.close()
        self.assertEqual(self.status_of(current_user, req(cookie_value(resp))), 401)

    def test_logout_without_login_is_401(self):
        self.assertEqual(self.status_of(logout, req(), Response()), 401)

    def test_logout_ends_only_current_session(self):
        self.do_signup()
        _, r1 = self.do_login()
        _, r2 = self.do_login()
        logout(req(cookie_value(r1)), Response())
        self.assertEqual(self.status_of(current_user, req(cookie_value(r1))), 401)
        self.assertEqual(current_user(req(cookie_value(r2))).username, "a@test.com")

    def test_session_without_row_is_401(self):
        self.do_signup()
        _, resp = self.do_login()
        conn = connect()
        with conn:
            conn.execute("DELETE FROM sessions")
        conn.close()
        self.assertEqual(self.status_of(current_user, req(cookie_value(resp))), 401)


class MigratedAccountTest(AuthBase):
    # D-024: 이전용 계정은 처음에 로그인할 수 없고, 처음 가입하는 사람이 비밀번호를 정해 받는다.
    def setUp(self):
        super().setUp()
        conn = connect()
        with conn:
            self.mid = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES ('migrated@test.com', NULL)"
            ).lastrowid
        conn.close()

    def test_cannot_login_before_claim(self):
        self.assertEqual(self.status_of(self.do_login, "migrated@test.com", PW), 401)
        self.assertEqual(self.status_of(self.do_login, "migrated@test.com", ""), 401)
        self.assertEqual(self.count("sessions"), 0)

    def test_first_signup_claims_same_account(self):
        user = self.do_signup("migrated@test.com")
        self.assertEqual(user.id, self.mid)
        self.assertEqual(self.count("users"), 1)
        logged, _ = self.do_login("migrated@test.com")
        self.assertEqual(logged.id, self.mid)

    def test_second_signup_after_claim_is_409_and_keeps_password(self):
        self.do_signup("migrated@test.com")
        self.assertEqual(self.status_of(self.do_signup, "migrated@test.com", "another-fake-pw"), 409)
        self.assertEqual(self.do_login("migrated@test.com")[0].id, self.mid)
        self.assertEqual(self.status_of(self.do_login, "migrated@test.com", "another-fake-pw"), 401)


if __name__ == "__main__":
    unittest.main()
