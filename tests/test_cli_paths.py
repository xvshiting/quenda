"""Tests for local path detection in CLI user input."""

from quenda.cli import _is_local_path_reference


def test_parent_relative_path_is_a_local_path_reference() -> None:
    assert _is_local_path_reference("../class01")


def test_plain_text_is_not_a_local_path_reference() -> None:
    assert not _is_local_path_reference("class01")
