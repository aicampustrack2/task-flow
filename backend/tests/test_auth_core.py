import tempfile
import unittest
from pathlib import Path

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
from app.db import connect, init_db

# 테스트용 가짜 값이다.
PW = "fake-password-1"
SECRET = "fake-secret-for-test"


class PasswordTest(unittest.TestCase):
    def test_hash_is_not_plain_text(self):
        h = hash_password(PW)
        self.assertNotIn(PW, h)
        self.assertTrue(h.startswith("scrypt$"))

    def test_same_password_gets_different_hash(self):
        self.assertNotEqual(hash_password(PW), hash_password(PW))

    def test_verify_success_and_failure(self):
        h = hash_password(PW)
        self.assertTrue(verify_password(PW, h))
        self.assertFalse(verify_password("wrong-password", h))

    def test_no_hash_never_matches(self):
        self.assertFalse(verify_password(PW, None))
        self.assertFalse(verify_password("", None))
        self.assertFalse(verify_password(PW, ""))

    def test_broken_hash_does_not_raise(self):
        self.assertFalse(verify_password(PW, "garbage"))
        self.assertFalse(verify_password(PW, "scrypt$x$y$z$a$b"))


class SessionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        path = Path(self._tmp.name) / "test.db"
        init_db(path)
        self.conn = connect(path)
        with self.conn:
            self.uid = self.conn.execute(
                "INSERT INTO users (username) VALUES ('a@test.com')"
            ).lastrowid

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_valid_session_returns_user(self):
        sid = create_session(self.conn, self.uid, now=1000)
        self.assertEqual(get_session_user_id(self.conn, sid, now=1000 + 10), self.uid)

    def test_expires_after_30_minutes_from_login(self):
        sid = create_session(self.conn, self.uid, now=1000)
        end = 1000 + SESSION_TTL_SECONDS
        self.assertEqual(get_session_user_id(self.conn, sid, now=end - 1), self.uid)
        self.assertIsNone(get_session_user_id(self.conn, sid, now=end))

    def test_reading_does_not_extend(self):
        sid = create_session(self.conn, self.uid, now=1000)
        get_session_user_id(self.conn, sid, now=1000 + 1500)
        self.assertIsNone(get_session_user_id(self.conn, sid, now=1000 + SESSION_TTL_SECONDS))

    def test_unknown_session_is_none(self):
        self.assertIsNone(get_session_user_id(self.conn, "nope", now=1000))

    def test_deleted_session_is_none(self):
        sid = create_session(self.conn, self.uid, now=1000)
        delete_session(self.conn, sid)
        self.assertIsNone(get_session_user_id(self.conn, sid, now=1001))

    def test_session_ids_are_unique(self):
        ids = {create_session(self.conn, self.uid, now=1000) for _ in range(20)}
        self.assertEqual(len(ids), 20)

    def test_login_cleans_expired_sessions_only(self):
        old = create_session(self.conn, self.uid, now=1000)
        later = 1000 + SESSION_TTL_SECONDS + 1
        fresh = create_session(self.conn, self.uid, now=later)
        ids = {r[0] for r in self.conn.execute("SELECT id FROM sessions")}
        self.assertNotIn(old, ids)
        self.assertIn(fresh, ids)

    def test_new_login_keeps_other_live_session(self):
        first = create_session(self.conn, self.uid, now=1000)
        second = create_session(self.conn, self.uid, now=1100)
        self.assertEqual(get_session_user_id(self.conn, first, now=1200), self.uid)
        self.assertEqual(get_session_user_id(self.conn, second, now=1200), self.uid)


class CookieTest(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(read_cookie(sign_cookie("abc_-123", SECRET), SECRET), "abc_-123")

    def test_tampered_id_rejected(self):
        value = sign_cookie("abc", SECRET)
        self.assertIsNone(read_cookie("xyz" + value[3:], SECRET))

    def test_tampered_signature_rejected(self):
        value = sign_cookie("abc", SECRET)
        self.assertIsNone(read_cookie(value[:-1] + ("0" if value[-1] != "0" else "1"), SECRET))

    def test_other_secret_rejected(self):
        self.assertIsNone(read_cookie(sign_cookie("abc", SECRET), "another-fake-secret"))

    def test_missing_or_malformed_rejected(self):
        for bad in (None, "", "abc", ".", "abc.", ".sig"):
            self.assertIsNone(read_cookie(bad, SECRET))


if __name__ == "__main__":
    unittest.main()
