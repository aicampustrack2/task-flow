import unittest

from app.rules import (
    RuleError,
    Status,
    validate_description,
    validate_status,
    validate_title,
)


class TitleRuleTest(unittest.TestCase):
    def test_rejects_empty_and_blank(self):
        for bad in ["", " ", "   \t\n", None, 3]:
            with self.subTest(bad=bad):
                with self.assertRaises(RuleError):
                    validate_title(bad)

    def test_trims(self):
        self.assertEqual(validate_title("  할 일  "), "할 일")


class DescriptionRuleTest(unittest.TestCase):
    def test_optional(self):
        self.assertEqual(validate_description(None), "")
        self.assertEqual(validate_description(""), "")
        self.assertEqual(validate_description("메모"), "메모")

    def test_rejects_non_string(self):
        with self.assertRaises(RuleError):
            validate_description(5)


class StatusRuleTest(unittest.TestCase):
    def test_three_values(self):
        for value in ["TODO", "IN_PROGRESS", "DONE"]:
            self.assertEqual(validate_status(value), Status(value))

    def test_rejects_others(self):
        for bad in ["", "todo", "doing", None, 1]:
            with self.subTest(bad=bad):
                with self.assertRaises(RuleError):
                    validate_status(bad)


if __name__ == "__main__":
    unittest.main()
