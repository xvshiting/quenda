"""Web Agent service integration with local Agent Homes."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from quenda.host import AgentHomeManager
from quenda.web.services.agent_service import AgentService


@pytest.mark.asyncio
async def test_create_list_update_and_delete_agent_home(tmp_path: Path) -> None:
    service = AgentService(manager=AgentHomeManager(tmp_path))
    created = await service.create_agent(
        SimpleNamespace(
            name="reviewer",
            source=None,
            description="Reviews changes",
            system_prompt="Review evidence carefully.",
            config_yaml=None,
        )
    )

    assert created.id == "reviewer"
    assert created.system_prompt == "Review evidence carefully."
    assert (tmp_path / "agent-reviewer" / "IDENTITY.md").is_file()
    assert (tmp_path / "agent-reviewer" / "SOUL.md").is_file()
    assert "reviewer" in [agent.id for agent in await service.list_agents()]

    updated = await service.update_agent(
        "reviewer",
        SimpleNamespace(
            name=None,
            description="Senior reviewer",
            system_prompt="Find behavioral risks.",
            config_yaml="tools:\n  bundles: [core]\n",
        ),
    )
    assert updated is not None
    assert updated.description == "Senior reviewer"
    assert updated.system_prompt == "Find behavioral risks."

    assert await service.delete_agent("reviewer") is True
    assert not (tmp_path / "agent-reviewer").exists()


@pytest.mark.asyncio
async def test_invalid_agent_identifier_cannot_escape_home(tmp_path: Path) -> None:
    service = AgentService(manager=AgentHomeManager(tmp_path / "quenda"))
    outside = tmp_path / "outside"
    outside.mkdir()

    assert await service.get_agent("../outside") is None
    assert await service.delete_agent("../outside") is False
    assert outside.is_dir()
