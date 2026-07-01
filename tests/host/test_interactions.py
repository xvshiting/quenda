"""
Tests for the Host interaction request system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from kora.host import (
    InteractionContext,
    InteractionOption,
    InteractionRequest,
    InteractionRegistry,
    ChoiceInteraction,
    ConfirmInteraction,
    InputInteraction,
    MenuInteraction,
    create_default_interaction_registry,
    load_agent_interactions,
)
from kora.interface import render_interaction_request


@dataclass
class FakeSessionState:
    metadata: dict[str, Any] = field(default_factory=dict)


class FakeSession:
    def __init__(self) -> None:
        self._state = FakeSessionState()
        self._system_prompt = "You are helpful."
        self._tools: list = []

    @property
    def state(self) -> FakeSessionState:
        return self._state

    @property
    def system_prompt(self) -> str | None:
        return self._system_prompt

    @property
    def tools(self) -> list:
        return self._tools

    @property
    def mode(self) -> str:
        return self._state.metadata.get("mode", "chat")

    @mode.setter
    def mode(self, value: str) -> None:
        self._state.metadata["mode"] = value


class FakeAgent:
    def __init__(self) -> None:
        self._tools: list = []

    @property
    def tools(self) -> list:
        return self._tools


def make_context() -> InteractionContext:
    return InteractionContext(session=FakeSession(), agent=FakeAgent())


class TestDefaultInteractionRegistry:
    def test_has_builtin_interactions(self) -> None:
        registry = create_default_interaction_registry()
        kinds = {interaction.kind for interaction in registry.list_interactions()}
        assert kinds == {"choice", "confirm", "input", "menu"}

    def test_registry_lookup(self) -> None:
        registry = create_default_interaction_registry()
        assert isinstance(registry.get("choice"), ChoiceInteraction)
        assert isinstance(registry.get("confirm"), ConfirmInteraction)
        assert isinstance(registry.get("input"), InputInteraction)
        assert isinstance(registry.get("menu"), MenuInteraction)


class TestChoiceInteraction:
    def test_choice_validation(self) -> None:
        interaction = ChoiceInteraction()
        request = InteractionRequest(kind="choice", title="Pick one")
        errors = interaction.validate(request, make_context())
        assert errors
        assert "requires at least one option" in errors[0]

    def test_choice_suggestions(self) -> None:
        interaction = ChoiceInteraction()
        request = InteractionRequest(
            kind="choice",
            title="Pick one",
            options=[
                InteractionOption(id="a", label="Alpha", is_default=True),
                InteractionOption(id="b", label="Beta"),
            ],
        )
        suggestions = interaction.get_suggestions(request, make_context())
        assert [option.id for option in suggestions] == ["a", "b"]


class TestInteractionRendering:
    def test_render_menu(self) -> None:
        registry = create_default_interaction_registry()
        request = InteractionRequest(
            kind="choice",
            title="Next step",
            message="What should we do?",
            options=[
                InteractionOption(id="read", label="Read more files", is_default=True),
                InteractionOption(id="edit", label="Start editing"),
            ],
        )

        output = render_interaction_request(request, registry=registry, context=make_context())

        assert "Next step" in output
        assert "What should we do?" in output
        assert "Read more files" in output
        assert "default" in output


class TestAgentLocalInteractionLoading:
    def test_load_agent_interactions(self) -> None:
        with TemporaryDirectory() as tmpdir:
            agent_path = Path(tmpdir)
            interactions_dir = agent_path / "extensions" / "interactions"
            interactions_dir.mkdir(parents=True)

            interaction_file = interactions_dir / "custom.py"
            interaction_file.write_text(
                """
from kora.host.interactions import InteractionOption

class CustomInteraction:
    @property
    def kind(self):
        return "custom"

    @property
    def description(self):
        return "Custom interaction"

    @property
    def usage(self):
        return "custom"

    def validate(self, request, context):
        return []

    def get_suggestions(self, request, context):
        return [InteractionOption(id="one", label="One")]

def register(registry):
    registry.register(CustomInteraction())
""",
                encoding="utf-8",
            )

            registry = InteractionRegistry()
            loaded = load_agent_interactions(agent_path, registry)

            assert loaded == 1
            assert registry.get("custom") is not None
