"""Host-managed Skill evolution and framework Tool behavior."""

from __future__ import annotations

import json
from pathlib import Path

from quenda.host.permission_manager import PermissionManager
from quenda.host.runner import _resolve_tools
from quenda.host.skill import SkillDiscovery
from quenda.host.skill_evolution import SkillEvolutionManager
from quenda.tools.skill_evolution import (
    ApplySkillEvolutionTool,
    InspectSkillEvolutionTool,
)


def _manager(tmp_path: Path, *, allow: bool = True) -> tuple[SkillEvolutionManager, list]:
    skill = tmp_path / "agent" / "skills" / "demo-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Demo evolution.\n---\n\nOriginal.\n",
        encoding="utf-8",
    )
    permissions = PermissionManager()
    prompts: list = []
    permissions.prompt_handler = lambda request: prompts.append(request) or allow
    discovery = SkillDiscovery(agent_package_path=tmp_path / "agent")
    return (
        SkillEvolutionManager(
            discovery,
            state_root=tmp_path / "agent-home" / ".quenda" / "evolution" / "skills",
            permission_policy=permissions,
        ),
        prompts,
    )


def test_manager_proposes_then_commits_through_non_cacheable_approval(
    tmp_path: Path,
) -> None:
    manager, prompts = _manager(tmp_path)

    proposal = manager.propose(
        "demo-skill",
        {"SKILL.md": "---\nname: demo-skill\ndescription: Demo evolution.\n---\n\nBetter.\n"},
        reason="Observed repeated failure",
        evidence_refs=("run:one",),
        confidence=0.9,
    )
    committed = manager.commit(
        "demo-skill",
        proposal_id=proposal["proposal_id"],
        expected_revision=proposal["base_revision"],
    )

    assert proposal["status"] == "validated"
    assert committed["status"] == "committed"
    assert len(prompts) == 1
    assert prompts[0].kind.value == "skill_evolution.write"
    assert prompts[0].cacheable is False
    assert prompts[0].tool_args["proposal_id"] == proposal["proposal_id"]
    assert "Better." in manager.active_path("demo-skill").joinpath("SKILL.md").read_text()


def test_denied_commit_preserves_active_skill(tmp_path: Path) -> None:
    manager, prompts = _manager(tmp_path, allow=False)
    proposal = manager.propose(
        "demo-skill",
        {"SKILL.md": "---\nname: demo-skill\ndescription: Demo evolution.\n---\n\nNo.\n"},
        reason="Try a change",
    )

    denied = manager.commit(
        "demo-skill",
        proposal_id=proposal["proposal_id"],
        expected_revision=proposal["base_revision"],
    )

    assert denied["status"] == "denied"
    assert len(prompts) == 1
    assert "Original." in manager.active_path("demo-skill").joinpath("SKILL.md").read_text()


def test_framework_tools_keep_inspection_separate_from_mutation(tmp_path: Path) -> None:
    manager, _ = _manager(tmp_path)
    inspect_tool = InspectSkillEvolutionTool(manager)
    apply_tool = ApplySkillEvolutionTool(manager)

    listing = inspect_tool.execute(skill_name="demo-skill")
    proposed = apply_tool.execute(
        action="propose",
        skill_name="demo-skill",
        changes={"references/note.md": "Useful evidence.\n"},
        reason="Add a reusable reference",
    )

    listing_data = json.loads(listing.content)
    proposed_data = json.loads(proposed.content)
    assert not listing.is_error
    assert listing_data["skill_name"] == "demo-skill"
    assert proposed_data["status"] == "validated"
    assert proposed.change_preview == "M references/note.md"
    assert "Useful evidence" not in proposed.content


def test_inspection_lists_persisted_proposals_after_restart(tmp_path: Path) -> None:
    manager, _ = _manager(tmp_path)
    proposed = manager.propose(
        "demo-skill",
        {"references/note.md": "Reusable.\n"},
        reason="Add documentation",
    )

    inspected = manager.inspect("demo-skill")

    assert inspected["proposals"][0]["proposal_id"] == proposed["proposal_id"]
    assert "changes" not in inspected["proposals"][0]


def test_host_binds_skill_evolution_tools_as_framework_tools(tmp_path: Path) -> None:
    manager, _ = _manager(tmp_path)

    tools = _resolve_tools(
        tmp_path,
        None,
        agent_package_path=tmp_path / "agent",
        skill_discovery=manager.discovery,
        skill_evolution_state_root=manager.state_root,
        permission_policy=manager.permission_policy,
    )

    names = {tool.name for tool in tools}
    assert "inspect_skill_evolution" in names
    assert "apply_skill_evolution" in names
