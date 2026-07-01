"""
Tests for RequestInteractionTool.
"""

from quenda.tools import RequestInteractionTool


class TestRequestInteractionTool:
    """Test the framework-reserved interaction request tool."""

    def test_tool_properties(self) -> None:
        """Test basic tool properties."""
        tool = RequestInteractionTool()
        assert tool.name == "request_interaction"
        assert "user interaction" in tool.description.lower()

    def test_parameters_schema(self) -> None:
        """Test parameters schema has required fields."""
        tool = RequestInteractionTool()
        params = tool.parameters

        assert params["type"] == "object"
        assert "kind" in params["properties"]
        assert "title" in params["properties"]
        assert "message" in params["properties"]
        assert "options" in params["properties"]

        # kind should have enum
        kind_prop = params["properties"]["kind"]
        assert "enum" in kind_prop
        assert "choice" in kind_prop["enum"]
        assert "confirm" in kind_prop["enum"]

        # required fields
        assert "kind" in params["required"]
        assert "title" in params["required"]

    def test_execute_returns_placeholder(self) -> None:
        """Test execute returns placeholder result."""
        tool = RequestInteractionTool()
        result = tool.execute(kind="choice", title="Pick one")

        assert result.name == "request_interaction"
        assert "queued" in result.content.lower()
        assert result.is_error is False
