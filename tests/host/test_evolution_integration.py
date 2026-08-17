"""Host wiring for automatic post-Run memory evolution."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from quenda.host.runner import setup_agent
from quenda.kernel.types import Message, ModelResponse
from quenda.runtime.events import EvolutionCompleted


class SequencedModel:
    def __init__(self) -> None:
        self.calls = 0
        self.id = "model"
        self.spec = SimpleNamespace(
            context_window=32_000,
            max_output_tokens=2_000,
            vision=False,
        )
        self.provider = SimpleNamespace(
            id="test",
            spec=SimpleNamespace(timeout=None, max_retries=0),
        )

    def invoke(self, messages: list[Message], *, tools: list[object]) -> ModelResponse:
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(content="好的，我会记住。")
        return ModelResponse(
            content=(
                '{"proposals":[{"target":"user_profile",'
                '"proposed_content":"# User\\n\\n- Prefer concise answers.\\n",'
                '"reason":"The user explicitly stated this preference",'
                '"confidence":0.98}]}'
            )
        )


class StaticRegistry:
    def __init__(self, model: SequencedModel) -> None:
        self.model = model

    def get_model(self, provider: str, model: str) -> SequencedModel:
        return self.model


@pytest.mark.asyncio
async def test_agent_config_wires_automatic_evolution_after_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    agent_home = tmp_path / "agent"
    workspace = tmp_path / "workspace"
    agent_home.mkdir()
    workspace.mkdir()
    (agent_home / "agent.yaml").write_text("version: 1\n", encoding="utf-8")
    (agent_home / "AGENT.md").write_text(
        "---\nname: evolving-agent\n---\nAssistant.", encoding="utf-8"
    )
    (agent_home / "config.yaml").write_text(
        """
model_provider: test
model_name: model
evolution:
  enabled: true
  write_mode: automatic
  every_n_user_turns: 5
  on_explicit_signal: true
  min_confidence: 0.8
tools:
  bundles: []
""",
        encoding="utf-8",
    )
    model = SequencedModel()
    setup = setup_agent(
        agent_home,
        workspace,
        provider_registry=StaticRegistry(model),  # type: ignore[arg-type]
        tools=[],
    )
    assert setup is not None
    session = setup.agent.open_session()
    events = []

    result = await session.send(
        "Please remember that I prefer concise answers",
        on_event=events.append,
    )

    assert result == "好的，我会记住。"
    assert model.calls == 2
    assert (agent_home / "USER.md").read_text(encoding="utf-8") == (
        "# User\n\n- Prefer concise answers.\n"
    )
    evolution = next(event for event in events if isinstance(event, EvolutionCompleted))
    assert evolution.committed_count == 1
