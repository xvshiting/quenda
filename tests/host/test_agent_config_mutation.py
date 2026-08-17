"""Guarded, revisioned Agent configuration mutation behavior."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from quenda.host.config_mutation import AgentConfigEditor
from quenda.host.permission_manager import PermissionManager
from quenda.tools.agent_config import ApplyAgentConfigPatchTool


def _agent_home(tmp_path: Path) -> Path:
    home = tmp_path / "agent-demo"
    home.mkdir()
    (home / "AGENT.md").write_text(
        "---\nname: demo\n---\nDemo agent.\n",
        encoding="utf-8",
    )
    (home / "agent.yaml").write_text('{"name":"demo"}\n', encoding="utf-8")
    (home / "config.yaml").write_text(
        """providers:
  local:
    type: llama-server
    url: http://127.0.0.1:8080/v1
    key: super-secret
    models:
      - id: local-model
models:
  default: local/local-model
tools:
  bundles: [core]
""",
        encoding="utf-8",
    )
    return home


def test_preview_is_valid_redacted_and_side_effect_free(tmp_path: Path) -> None:
    home = _agent_home(tmp_path)
    original = (home / "config.yaml").read_text(encoding="utf-8")
    editor = AgentConfigEditor(home, workspace_path=tmp_path)

    result = editor.apply(
        {"providers": {"local": {"key": "replacement-secret"}}},
        commit=False,
    )

    assert result.status == "preview"
    assert result.valid
    assert not result.committed
    assert "super-secret" not in result.diff
    assert "replacement-secret" not in result.diff
    assert "<redacted>" in result.diff
    assert (home / "config.yaml").read_text(encoding="utf-8") == original
    assert not (home / ".quenda" / "config-journal.jsonl").exists()


def test_commit_requires_approval_and_writes_revision_atomically(tmp_path: Path) -> None:
    home = _agent_home(tmp_path)
    prompts = []
    permissions = PermissionManager()
    permissions.prompt_handler = lambda request: prompts.append(request) or True
    editor = AgentConfigEditor(
        home,
        workspace_path=tmp_path,
        permission_policy=permissions,
    )
    before = editor.current_revision()

    result = editor.apply(
        {"compression": {"enabled": True, "threshold": 0.75}},
        commit=True,
        expected_revision=before,
    )

    assert result.status == "committed"
    assert result.committed
    assert result.base_revision == before
    assert result.revision != before
    assert len(prompts) == 1
    assert prompts[0].kind.value == "agent_config.write"
    assert prompts[0].cacheable is False
    assert "patch" not in prompts[0].tool_args
    written = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
    assert written["compression"]["threshold"] == 0.75
    backup = home / ".quenda" / "config-revisions" / f"{before}.yaml"
    assert backup.is_file()
    journal = home / ".quenda" / "config-journal.jsonl"
    record = json.loads(journal.read_text(encoding="utf-8").splitlines()[-1])
    assert record["base_revision"] == before
    assert record["revision"] == result.revision
    assert record["changed_keys"] == ["compression"]


def test_invalid_or_stale_patch_never_prompts_or_writes(tmp_path: Path) -> None:
    home = _agent_home(tmp_path)
    original = (home / "config.yaml").read_text(encoding="utf-8")
    prompts = []
    permissions = PermissionManager()
    permissions.prompt_handler = lambda request: prompts.append(request) or True
    editor = AgentConfigEditor(
        home,
        workspace_path=tmp_path,
        permission_policy=permissions,
    )

    invalid = editor.apply(
        {"tools": {"bundles": ["does-not-exist"]}},
        commit=True,
    )
    stale = editor.apply(
        {"compression": {"enabled": True}},
        commit=True,
        expected_revision="stale-revision",
    )

    assert invalid.status == "invalid"
    assert not invalid.valid
    assert stale.status == "conflict"
    assert prompts == []
    assert (home / "config.yaml").read_text(encoding="utf-8") == original


def test_denied_patch_preserves_current_config(tmp_path: Path) -> None:
    home = _agent_home(tmp_path)
    original = (home / "config.yaml").read_text(encoding="utf-8")
    permissions = PermissionManager()
    permissions.prompt_handler = lambda request: False
    editor = AgentConfigEditor(home, permission_policy=permissions)

    result = editor.apply({"compression": {"enabled": True}}, commit=True)

    assert result.status == "denied"
    assert not result.committed
    assert (home / "config.yaml").read_text(encoding="utf-8") == original


def test_framework_tool_previews_then_commits_against_preview_revision(
    tmp_path: Path,
) -> None:
    home = _agent_home(tmp_path)
    permissions = PermissionManager()
    permissions.prompt_handler = lambda request: True
    tool = ApplyAgentConfigPatchTool(
        workspace=tmp_path,
        agent_package_path=home,
        permission_policy=permissions,
    )
    patch = {"compression": {"enabled": True}}

    preview = tool.execute(patch=patch)
    preview_data = json.loads(preview.content)
    committed = tool.execute(
        patch=patch,
        commit=True,
        expected_revision=preview_data["base_revision"],
    )
    committed_data = json.loads(committed.content)

    assert not preview.is_error
    assert preview_data["status"] == "preview"
    assert not committed.is_error
    assert committed_data["status"] == "committed"
