"""User-facing slash invocation tests for discovered skills."""

from pathlib import Path

from quenda.host.commands import CommandResult, create_default_registry
from quenda.host.repl import ReplRuntime
from quenda.host.skill import SkillActivator, SkillDiscovery
from quenda.runtime import Agent


class StaticContextBuilder:
    """Minimal context-builder adapter for ReplRuntime tests."""

    def rebuild(self, **_: object) -> str:
        return "rebuilt prompt"


def create_runtime(tmp_path: Path, skill_name: str = "review-work") -> ReplRuntime:
    skill_dir = tmp_path / "skills" / skill_name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"""---
name: {skill_name}
description: Review the requested work.
---
# Review
Review carefully.
""",
        encoding="utf-8",
    )

    discovery = SkillDiscovery(user_workspace_skills_path=tmp_path / "skills")
    activator = SkillActivator(discovery)
    agent = Agent(name="test-agent", system_prompt="original prompt")
    session = agent.open_session()

    return ReplRuntime(
        session=session,
        agent=agent,
        context_builder=StaticContextBuilder(),  # type: ignore[arg-type]
        provider_name="test",
        model_name="test-model",
        registry=create_default_registry(),
        skill_discovery=discovery,
        skill_activator=activator,
        workspace_path=tmp_path,
    )


def test_discovered_skill_can_be_invoked_as_slash_command(tmp_path: Path) -> None:
    runtime = create_runtime(tmp_path)

    result = runtime.execute_command("/review-work inspect the current diff")

    assert isinstance(result, CommandResult)
    assert result.status == "ok"
    assert result.model_input == (
        "[Skill invocation: review-work]\n\nARGUMENTS: inspect the current diff"
    )
    assert runtime.list_active_skill_names() == {"review-work"}


def test_registered_command_wins_when_skill_has_same_name(tmp_path: Path) -> None:
    runtime = create_runtime(tmp_path, skill_name="status")

    result = runtime.execute_command("/status")

    assert isinstance(result, CommandResult)
    assert result.model_input is None
    assert runtime.list_active_skill_names() == set()


def test_discovered_skill_appears_in_slash_completions(tmp_path: Path) -> None:
    runtime = create_runtime(tmp_path)

    assert "/review-work" in runtime.get_completions("/review")
