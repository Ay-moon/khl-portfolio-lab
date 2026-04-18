from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_KEYWORD_RE = re.compile(
    r"\b(CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|MERGE|SELECT|WITH|EXEC)\b",
    flags=re.IGNORECASE,
)


@dataclass
class ValidationIssue:
    path: Path
    message: str


def collect_sql_files(sql_root: Path) -> list[Path]:
    return sorted(p for p in sql_root.rglob("*.sql") if p.is_file())


def validate_sql_text(content: str) -> list[str]:
    issues: list[str] = []
    trimmed = content.strip()

    if not trimmed:
        issues.append("file is empty")
        return issues

    if "TODO" in content.upper():
        issues.append("contains TODO placeholder")

    if "<<<<<<<" in content or "=======" in content or ">>>>>>>" in content:
        issues.append("contains unresolved merge conflict markers")

    if SQL_KEYWORD_RE.search(content) is None:
        issues.append("missing expected SQL keywords")

    return issues


def validate_sql_files(files: list[Path]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for path in files:
        content = path.read_text(encoding="utf-8")
        for message in validate_sql_text(content):
            issues.append(ValidationIssue(path=path, message=message))
    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate SQL files for CI quality gates.")
    parser.add_argument(
        "--sql-root",
        default=str(REPO_ROOT / "data-platform" / "sql"),
        help="Root directory containing SQL files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sql_root = Path(args.sql_root).resolve()

    if not sql_root.exists():
        raise RuntimeError(f"SQL root does not exist: {sql_root}")

    files = collect_sql_files(sql_root)
    if not files:
        raise RuntimeError(f"No SQL files found under: {sql_root}")

    issues = validate_sql_files(files)
    if issues:
        for issue in issues:
            print(f"[FAIL] {issue.path}: {issue.message}")
        raise SystemExit(1)

    print(f"SQL validation passed: {len(files)} file(s) checked under {sql_root}")


if __name__ == "__main__":
    main()
