"""String matching, diff rows, file locks, and atomic writes."""

import re
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from ruocun.tools.edit_file import buildEditHunk, findActualString
from ruocun.tools.paths import atomicWrite, fileLock


@pytest.mark.parametrize(("raw", "old", "expected"), [
    ("hello world", "world", "world"),
    ("auto: enabled", "auto: enabled", "auto: enabled"),
    ('const s = "hello";', 'const s = "hello";', 'const s = "hello";'),
    ("do A, then B", "do A, then B", "do A, then B"),
    ("auto: enabled, done.", "auto: enabled, done.", "auto: enabled, done."),
    ("hello world", "goodbye", None),
    ("anything", "", None),
])
def test_source_find_actual(raw, old, expected):
    assert findActualString(raw, old) == expected


def test_source_find_actual_long():
    long = "x" * 6000
    assert findActualString(long, long) == long
    assert findActualString("y" * 6000, long) is None


def test_source_find_actual_length():
    result = findActualString("auto: enabled", "auto: enabled")
    assert result is not None and len(result) == len("auto: enabled")


_RAW = "import x\nfunction f() {\n  return 1\n}\n"


def test_source_diff_rows():
    rows = buildEditHunk(_RAW, "  return 1", "  return 2", 3)
    assert any(row.startswith(" ") and "function f() {" in row for row in rows)
    assert re.match(r"^-\s*3\s+return 1", next(row for row in rows if row.startswith("-")))
    assert re.match(r"^\+\s*3\s+return 2", next(row for row in rows if row.startswith("+")))


def test_source_diff_missing():
    assert buildEditHunk(_RAW, "不存在", "x", 3) == []


def test_source_diff_without_context():
    assert all(row.startswith(("-", "+")) for row in buildEditHunk(_RAW, "  return 1", "  return 2", 0))


@pytest.mark.parametrize("shared", [True, False])
def test_source_lock_order(tmp_path, shared):
    order = []
    entered, attempted, finished, release = (threading.Event() for _ in range(4))
    first_key, second_key = str(tmp_path / "a"), str(tmp_path / ("a" if shared else "b"))

    def first():
        with fileLock(first_key):
            order.append("1-start")
            entered.set()
            assert release.wait(5)
            order.append("1-end")

    def second():
        attempted.set()
        with fileLock(second_key):
            order.extend(("2-start", "2-end"))
            finished.set()

    with ThreadPoolExecutor(2) as executor:
        one = executor.submit(first)
        assert entered.wait(5)
        two = executor.submit(second)
        try:
            assert attempted.wait(5)
            if shared:
                assert not finished.wait(0.02)
            else:
                assert finished.wait(5)
        finally:
            release.set()
        one.result(timeout=5)
        two.result(timeout=5)
    if shared:
        assert order == ["1-start", "1-end", "2-start", "2-end"]
    else:
        assert order.index("2-end") < order.index("1-end")


def test_source_lock_error_does_not_block_next(tmp_path):
    key = str(tmp_path / "k")
    with pytest.raises(RuntimeError, match="boom"), fileLock(key):
        raise RuntimeError("boom")
    with fileLock(key):
        answer = 42
    assert answer == 42


def test_source_lock_return_and_exception(tmp_path):
    key = str(tmp_path / "r")

    def job():
        with fileLock(key):
            return "ok"

    assert job() == "ok"
    with pytest.raises(RuntimeError, match="x"), fileLock(key):
        raise RuntimeError("x")


def test_source_atomic_write_parents_and_cleanup(tmp_path):
    path = tmp_path / "sub/a.txt"
    atomicWrite(str(path), "hello")
    assert path.read_text(encoding="utf-8") == "hello"
    assert not [item for item in path.parent.iterdir() if ".tmp" in item.name]


def test_source_atomic_write_overwrites(tmp_path):
    path = tmp_path / "a.txt"
    atomicWrite(str(path), "v1")
    atomicWrite(str(path), "v2")
    assert path.read_text(encoding="utf-8") == "v2"
