import tempfile
import unittest
from pathlib import Path

from app.db import connect, init_db


class DbPersistenceTest(unittest.TestCase):
    def test_row_survives_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.db"
            init_db(path)

            conn = connect(path)
            with conn:
                conn.execute(
                    "INSERT INTO tasks (title, description, status) VALUES (?, ?, ?)",
                    ("제목", "설명", "TODO"),
                )
            conn.close()

            conn = connect(path)
            rows = conn.execute("SELECT title, description, status FROM tasks").fetchall()
            conn.close()
            self.assertEqual([tuple(r) for r in rows], [("제목", "설명", "TODO")])

    def test_init_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.db"
            init_db(path)
            conn = connect(path)
            with conn:
                conn.execute(
                    "INSERT INTO tasks (title, status) VALUES (?, ?)", ("a", "TODO")
                )
            conn.close()

            init_db(path)  # 다시 불러도 기존 카드를 지우지 않는다

            conn = connect(path)
            count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            conn.close()
            self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
