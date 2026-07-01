"""
Tests for the interactive selector UI.
"""

from unittest.mock import patch, MagicMock

from quenda.interface.selector import select_option, _select_basic
from quenda.host.interactions import InteractionOption, InteractionRequest


class TestSelectOption:
    """Tests for select_option function."""

    def test_select_basic_without_prompt_toolkit(self) -> None:
        """Test basic selection fallback without prompt_toolkit."""
        request = InteractionRequest(
            kind="choice",
            title="Pick one",
            message="Choose an option",
            options=[
                InteractionOption(id="a", label="Option A", description="First"),
                InteractionOption(id="b", label="Option B", description="Second"),
            ],
        )

        # Mock input to select option 1
        with patch("builtins.input", return_value="1"):
            result = _select_basic(request, None, None)
            assert result is not None
            assert isinstance(result, InteractionOption)
            assert result.id == "a"
            assert result.label == "Option A"

    def test_select_basic_with_other(self) -> None:
        """Test basic selection with 'Other...' option."""
        request = InteractionRequest(
            kind="choice",
            title="Pick one",
            options=[
                InteractionOption(id="a", label="Option A"),
            ],
        )

        # Mock input: 2 = "Other...", then custom input
        with patch("builtins.input", side_effect=["2", "custom choice"]):
            result = _select_basic(request, None, None)
            assert result == "custom choice"

    def test_select_basic_cancel(self) -> None:
        """Test basic selection cancellation."""
        request = InteractionRequest(
            kind="choice",
            title="Pick one",
            options=[
                InteractionOption(id="a", label="Option A"),
            ],
        )

        # Mock input: 3 = Cancel (2 options + Other + Cancel = 3)
        with patch("builtins.input", return_value="3"):
            result = _select_basic(request, None, None)
            assert result is None

    def test_select_basic_empty_selects_default(self) -> None:
        """Test that empty input selects default option."""
        request = InteractionRequest(
            kind="choice",
            title="Pick one",
            options=[
                InteractionOption(id="a", label="Option A", is_default=True),
                InteractionOption(id="b", label="Option B"),
            ],
        )

        # Mock empty input
        with patch("builtins.input", return_value=""):
            result = _select_basic(request, None, None)
            assert result is not None
            assert result.id == "a"

    def test_select_basic_keyboard_interrupt(self) -> None:
        """Test that KeyboardInterrupt returns None."""
        request = InteractionRequest(
            kind="choice",
            title="Pick one",
            options=[
                InteractionOption(id="a", label="Option A"),
            ],
        )

        # Mock KeyboardInterrupt
        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            result = _select_basic(request, None, None)
            assert result is None
