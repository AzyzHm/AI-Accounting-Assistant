from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent

SOURCE_MAX_LINES = 300
SOURCE_DIRS = ["config", "core", "graph", "knowledge_base", "routes", "schemas", "services"]

TEST_MAX_LINES = 500
TEST_DIRS = ["tests"]


def _line_count(path: Path) -> int:
    return sum(1 for _ in path.open(encoding="utf-8"))


def _oversized_files(dirs: list[str], max_lines: int) -> list[str]:
    offenders = []
    for dir_name in dirs:
        root = BACKEND_ROOT / dir_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            count = _line_count(path)
            if count > max_lines:
                offenders.append(f"{path.relative_to(BACKEND_ROOT)} ({count} lines)")
    return offenders


def test_source_files_stay_under_the_size_guardrail():
    offenders = _oversized_files(SOURCE_DIRS, SOURCE_MAX_LINES)
    assert not offenders, (
        f"These files exceed {SOURCE_MAX_LINES} lines, split them up:\n" + "\n".join(offenders)
    )


def test_test_files_stay_under_the_size_guardrail():
    offenders = _oversized_files(TEST_DIRS, TEST_MAX_LINES)
    assert not offenders, (
        f"These test files exceed {TEST_MAX_LINES} lines, split them up:\n" + "\n".join(offenders)
    )
