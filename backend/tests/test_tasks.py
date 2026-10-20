import os
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app.db import init_db
from app.schemas import TaskCreate
from app.tasks import create_task, list_tasks


class TasksApiTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("TASKFLOW_DB")
        os.environ["TASKFLOW_DB"] = str(Path(self._tmp.name) / "test.db")
        init_db()

    def tearDown(self):
        if self._old is None:
            del os.environ["TASKFLOW_DB"]
        else:
            os.environ["TASKFLOW_DB"] = self._old
        self._tmp.cleanup()

    def test_empty_list_is_success(self):
        self.assertEqual(list_tasks(), [])

    def test_create_starts_as_todo_and_description_optional(self):
        task = create_task(TaskCreate(title="  첫 카드 "))
        self.assertEqual(task.title, "첫 카드")
        self.assertEqual(task.description, "")
        self.assertEqual(task.status, "TODO")

    def test_list_in_id_order(self):
        create_task(TaskCreate(title="a", description="x"))
        create_task(TaskCreate(title="b"))
        self.assertEqual([t.title for t in list_tasks()], ["a", "b"])

    def test_blank_title_rejected_and_not_saved(self):
        for bad in [None, "", "   "]:
            with self.subTest(bad=bad):
                with self.assertRaises(HTTPException) as cm:
                    create_task(TaskCreate(title=bad))
                self.assertEqual(cm.exception.status_code, 422)
        self.assertEqual(list_tasks(), [])


if __name__ == "__main__":
    unittest.main()
