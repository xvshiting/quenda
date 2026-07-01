"""
Integration tests for the interaction request flow.

Tests the complete flow:
1. LLM calls request_interaction tool
2. Host detects the tool call
3. Interface renders the choice
4. User selects an option
5. Response is injected for next turn
"""

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch, MagicMock

from quenda.cli import (
    _extract_interaction_requests,
    _handle_interaction_request,
)
from quenda.host import (
    InteractionContext,
    InteractionOption,
    InteractionRegistry,
    extract_skill_activation_requests,
    resolve_skill_activation_requests,
    create_default_interaction_registry,
)
from quenda.runtime.events import ModelResponded


@dataclass
class FakeSession:
    """Minimal fake session for testing."""
    _system_prompt: str = "You are helpful."
    _tools: list = field(default_factory=list)
    mode: str = "chat"
    state: Any = None

    def __post_init__(self) -> None:
        if self.state is None:
            self.state = type("State", (), {"messages": []})()

    @property
    def system_prompt(self) -> str | None:
        return self._system_prompt

    @property
    def tools(self) -> list:
        return self._tools


@dataclass
class FakeAgent:
    """Minimal fake agent for testing."""
    _tools: list = field(default_factory=list)

    @property
    def tools(self) -> list:
        return self._tools


class TestExtractInteractionRequests:
    """Tests for extracting interaction requests from events."""

    def test_no_requests(self) -> None:
        """Test with no request_interaction tool calls."""
        events = [
            ModelResponded(content="Hello!", tool_calls=[], tool_call_details=[], tool_arguments=[]),
        ]
        requests = _extract_interaction_requests(events)
        assert requests == []

    def test_single_request(self) -> None:
        """Test with a single request_interaction tool call."""
        events = [
            ModelResponded(
                content="",
                tool_calls=["call_1"],
                tool_call_details=[{
                    "id": "call_1",
                    "name": "request_interaction",
                    "arguments": {
                        "kind": "choice",
                        "title": "Pick one",
                        "message": "Which option?",
                        "options": [
                            {"id": "a", "label": "Option A"},
                            {"id": "b", "label": "Option B"},
                        ],
                    },
                }],
                tool_arguments=[{
                    "kind": "choice",
                    "title": "Pick one",
                    "message": "Which option?",
                    "options": [
                        {"id": "a", "label": "Option A"},
                        {"id": "b", "label": "Option B"},
                    ],
                }],
            ),
        ]
        requests = _extract_interaction_requests(events)
        assert len(requests) == 1
        assert requests[0]["kind"] == "choice"
        assert requests[0]["title"] == "Pick one"

    def test_mixed_tool_calls(self) -> None:
        """Test with mixed tool calls including request_interaction."""
        events = [
            ModelResponded(
                content="",
                tool_calls=["call_1", "call_2"],
                tool_call_details=[
                    {"id": "call_1", "name": "read_file", "arguments": {"path": "test.py"}},
                    {"id": "call_2", "name": "request_interaction", "arguments": {"kind": "confirm", "title": "Proceed?"}},
                ],
                tool_arguments=[
                    {"path": "test.py"},
                    {"kind": "confirm", "title": "Proceed?"},
                ],
            ),
        ]
        requests = _extract_interaction_requests(events)
        assert len(requests) == 1
        assert requests[0]["kind"] == "confirm"

    def test_multiple_requests(self) -> None:
        """Test with multiple request_interaction calls."""
        events = [
            ModelResponded(
                content="",
                tool_calls=["call_1"],
                tool_call_details=[{"id": "call_1", "name": "request_interaction", "arguments": {"kind": "choice", "title": "First choice"}}],
                tool_arguments=[{"kind": "choice", "title": "First choice"}],
            ),
            ModelResponded(
                content="",
                tool_calls=["call_2"],
                tool_call_details=[{"id": "call_2", "name": "request_interaction", "arguments": {"kind": "confirm", "title": "Second confirm"}}],
                tool_arguments=[{"kind": "confirm", "title": "Second confirm"}],
            ),
        ]
        requests = _extract_interaction_requests(events)
        assert len(requests) == 2


class TestExtractSkillActivationRequests:
    """Tests for extracting request_skill_activation tool calls."""

    def test_extracts_skill_activation_requests(self) -> None:
        events = [
            ModelResponded(
                content="",
                tool_calls=["call_1"],
                tool_call_details=[{
                    "id": "call_1",
                    "name": "request_skill_activation",
                    "arguments": {
                        "skill_name": "code-review",
                        "reason": "Need the review checklist.",
                    },
                }],
                tool_arguments=[{
                    "skill_name": "code-review",
                    "reason": "Need the review checklist.",
                }],
            ),
        ]

        requests = extract_skill_activation_requests(events)
        assert len(requests) == 1
        assert requests[0]["skill_name"] == "code-review"


class TestResolveSkillActivationRequests:
    """Tests for host-side skill activation routing."""

    def test_resolves_available_skill(self) -> None:
        activated_names: list[str] = []

        def activate(skill_names: list[str]) -> list[str]:
            activated_names.extend(skill_names)
            return skill_names

        resolution = resolve_skill_activation_requests(
            [{"skill_name": "code-review"}],
            available_skill_names={"code-review", "testing"},
            active_skill_names=set(),
            activate=activate,
            original_user_message="Please review this code.",
        )

        assert resolution.followup_message is not None
        assert "Activated skills: code-review." in resolution.followup_message
        assert "Original user request: Please review this code." in resolution.followup_message
        assert activated_names == ["code-review"]

    def test_handles_unavailable_and_active_skills(self) -> None:
        def activate(skill_names: list[str]) -> list[str]:
            return skill_names

        resolution = resolve_skill_activation_requests(
            [{"skill_name": "testing"}, {"skill_name": "missing"}],
            available_skill_names={"code-review"},
            active_skill_names={"testing"},
            activate=activate,
            original_user_message="Run tests.",
        )

        assert resolution.followup_message is not None
        assert "Already active: testing." in resolution.followup_message
        assert "Unavailable skills: missing." in resolution.followup_message


class TestSessionRollbackPrimitive:
    """Tests for discarding hidden skill phases from session history."""

    def test_truncates_messages_back_to_turn_start(self) -> None:
        session = FakeSession()
        session.state.messages.extend(["old", "keep", "drop"])

        session.rollback_to = lambda checkpoint: session.state.messages.__delitem__(slice(checkpoint, None))
        session.rollback_to(2)

        assert session.state.messages == ["old", "keep"]


class TestHandleInteractionRequest:
    """Tests for handling interaction requests."""

    def test_choice_interaction(self) -> None:
        """Test handling a choice interaction."""
        registry = create_default_interaction_registry()
        context = InteractionContext(session=FakeSession(), agent=FakeAgent())

        @dataclass
        class MockReplInput:
            responses: list[str]
            index: int = 0

            def get_input(self, prompt: str) -> str:
                resp = self.responses[self.index]
                self.index += 1
                return resp

        repl_input = MockReplInput(["1"])

        request_payload = {
            "kind": "choice",
            "title": "Pick one",
            "options": [
                {"id": "a", "label": "Option A"},
                {"id": "b", "label": "Option B"},
            ],
        }

        # Mock select_option to return the first option
        with patch("quenda.cli.select_option") as mock_select:
            mock_select.return_value = InteractionOption(id="a", label="Option A")
            response = _handle_interaction_request(
                request_payload, registry, context, repl_input
            )

        assert response is not None
        assert "Option A" in response

    def test_confirm_interaction(self) -> None:
        """Test handling a confirm interaction."""
        registry = create_default_interaction_registry()
        context = InteractionContext(session=FakeSession(), agent=FakeAgent())

        @dataclass
        class MockReplInput:
            responses: list[str]
            index: int = 0

            def get_input(self, prompt: str) -> str:
                resp = self.responses[self.index]
                self.index += 1
                return resp

        repl_input = MockReplInput(["y"])

        request_payload = {
            "kind": "confirm",
            "title": "Proceed?",
            "message": "Are you sure?",
        }

        # Mock select_option to return "Yes"
        with patch("quenda.cli.select_option") as mock_select:
            mock_select.return_value = InteractionOption(id="yes", label="Yes")
            response = _handle_interaction_request(
                request_payload, registry, context, repl_input
            )

        assert response is not None
        assert "Yes" in response

    def test_input_interaction(self) -> None:
        """Test handling an input interaction."""
        registry = create_default_interaction_registry()
        context = InteractionContext(session=FakeSession(), agent=FakeAgent())

        @dataclass
        class MockReplInput:
            responses: list[str]
            index: int = 0

            def get_input(self, prompt: str) -> str:
                resp = self.responses[self.index]
                self.index += 1
                return resp

        repl_input = MockReplInput(["my custom input"])

        request_payload = {
            "kind": "input",
            "title": "Enter value",
            "message": "What's your name?",
        }

        response = _handle_interaction_request(
            request_payload, registry, context, repl_input
        )

        assert response is not None
        assert "my custom input" in response

    def test_choice_with_custom_input(self) -> None:
        """Test handling a choice where user selects 'Other...' and enters custom input."""
        registry = create_default_interaction_registry()
        context = InteractionContext(session=FakeSession(), agent=FakeAgent())

        @dataclass
        class MockReplInput:
            responses: list[str]
            index: int = 0

            def get_input(self, prompt: str) -> str:
                resp = self.responses[self.index]
                self.index += 1
                return resp

        repl_input = MockReplInput([])

        request_payload = {
            "kind": "choice",
            "title": "Pick one",
            "options": [
                {"id": "a", "label": "Option A"},
                {"id": "b", "label": "Option B"},
            ],
        }

        # Mock select_option to return custom input string
        with patch("quenda.cli.select_option") as mock_select:
            mock_select.return_value = "custom option C"
            response = _handle_interaction_request(
                request_payload, registry, context, repl_input
            )

        assert response is not None
        assert "custom option C" in response

    def test_choice_cancelled(self) -> None:
        """Test handling a choice where user cancels."""
        registry = create_default_interaction_registry()
        context = InteractionContext(session=FakeSession(), agent=FakeAgent())

        @dataclass
        class MockReplInput:
            responses: list[str]
            index: int = 0

            def get_input(self, prompt: str) -> str:
                resp = self.responses[self.index]
                self.index += 1
                return resp

        repl_input = MockReplInput([])

        request_payload = {
            "kind": "choice",
            "title": "Pick one",
            "options": [
                {"id": "a", "label": "Option A"},
                {"id": "b", "label": "Option B"},
            ],
        }

        # Mock select_option to return None (user cancelled)
        with patch("quenda.cli.select_option") as mock_select:
            mock_select.return_value = None
            response = _handle_interaction_request(
                request_payload, registry, context, repl_input
            )

        assert response is None
