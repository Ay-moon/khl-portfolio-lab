from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from validate_sql import validate_sql_text


class ValidateSqlTests(unittest.TestCase):
    def test_validate_sql_text_accepts_normal_sql(self) -> None:
        issues = validate_sql_text(
            """
CREATE TABLE dbo.Example(
    Id INT PRIMARY KEY
);
"""
        )
        self.assertEqual(issues, [])

    def test_validate_sql_text_flags_todo(self) -> None:
        issues = validate_sql_text("-- TODO: replace this script")
        self.assertTrue(any("TODO" in issue for issue in issues))

    def test_validate_sql_text_flags_merge_conflict_marker(self) -> None:
        issues = validate_sql_text("<<<<<<< HEAD\nSELECT 1;\n=======\nSELECT 2;\n>>>>>>> main")
        self.assertTrue(any("merge conflict" in issue for issue in issues))

    def test_validate_sql_text_flags_missing_keyword(self) -> None:
        issues = validate_sql_text("just some text")
        self.assertTrue(any("keywords" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
