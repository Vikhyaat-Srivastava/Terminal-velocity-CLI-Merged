"""
test_sanity.py — a standalone test file with ZERO imports from your
project (no cli, no repopilot, nothing). Save this ANYWHERE and run
pytest on it to confirm pytest itself is working correctly, separate
from any project import/path issues.

If this file collects and passes, pytest is fine — the problem is
specifically your project's imports or folder structure.
If THIS file also shows "collected 0 items", the problem is pytest's
discovery/config itself (e.g. testpaths in pyproject.toml), not your code.
"""


def test_basic_math():
    assert 1 + 1 == 2


def test_string_operations():
    assert "hello".upper() == "HELLO"
    assert "hello world".split() == ["hello", "world"]


def test_list_operations():
    items = [3, 1, 4, 1, 5, 9, 2, 6]
    assert sorted(items) == [1, 1, 2, 3, 4, 5, 6, 9]
    assert max(items) == 9
    assert len(items) == 8


def test_dictionary_lookup():
    config = {"name": "repopilot", "version": "0.1.0"}
    assert config["name"] == "repopilot"
    assert config.get("missing_key") is None


def test_exception_handling():
    import pytest

    with pytest.raises(ZeroDivisionError):
        1 / 0


def test_file_operations(tmp_path):
    # tmp_path is a built-in pytest fixture — no project code needed
    test_file = tmp_path / "sample.txt"
    test_file.write_text("hello from pytest")
    assert test_file.read_text() == "hello from pytest"
    assert test_file.exists()


def test_intentional_failure_example():
    # Leave this UNCOMMENTED once to confirm you can actually SEE a
    # failure reported correctly — then comment it back out.
    # assert 1 == 2, "this should fail on purpose"
    assert True
