"""CLI tests for Agent Home management and named launchers."""

from pathlib import Path

import pytest

from quenda import cli


def test_agent_create_and_list_use_quenda_home(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path))

    assert cli.main(["agent", "create", "reviewer"]) == 0
    assert cli.main(["agent", "list"]) == 0

    output = capsys.readouterr().out
    assert "Created agent: reviewer" in output
    assert f"reviewer\t{tmp_path / 'agent-reviewer'}" in output


def test_named_agent_uses_current_directory_as_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path))
    assert cli.main(["agent", "create", "reviewer"]) == 0
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    captured: dict[str, object] = {}

    def fake_run_repl(agent_path: Path, workspace: Path, **kwargs) -> int:
        captured["agent_path"] = agent_path
        captured["workspace"] = workspace
        return 0

    monkeypatch.setattr(cli, "run_repl", fake_run_repl)

    assert cli.main(["reviewer"]) == 0
    assert captured == {
        "agent_path": tmp_path / "agent-reviewer",
        "workspace": project,
    }


def test_explicit_agent_run_accepts_external_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path / "home"))
    assert cli.main(["agent", "create", "reviewer"]) == 0
    project = tmp_path / "project"
    project.mkdir()
    captured: dict[str, Path] = {}

    def fake_run_repl(agent_path: Path, workspace: Path, **kwargs) -> int:
        captured["workspace"] = workspace
        return 0

    monkeypatch.setattr(cli, "run_repl", fake_run_repl)

    assert cli.main(["agent", "run", "reviewer", "--workspace", str(project)]) == 0
    assert captured["workspace"] == project
    assert project.is_dir()


def test_explicit_workspace_must_already_exist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path / "home"))
    assert cli.main(["agent", "create", "reviewer"]) == 0
    missing = tmp_path / "misspelled-project"

    assert cli.main(["reviewer", "--workspace", str(missing)]) == 1

    assert not missing.exists()
    assert "Workspace directory not found" in capsys.readouterr().err


def test_create_reports_explicit_launcher_for_builtin_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path))

    assert cli.main(["agent", "create", "run"]) == 0

    assert "quenda agent run run" in capsys.readouterr().out


def test_web_command_starts_optional_server(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_server(*, host: str, port: int, reload: bool) -> int:
        captured.update(host=host, port=port, reload=reload)
        return 0

    monkeypatch.setattr(cli, "_run_web_server", fake_server)

    assert cli.main(["web", "--host", "0.0.0.0", "--port", "9000", "--reload"]) == 0
    assert captured == {"host": "0.0.0.0", "port": 9000, "reload": True}


def test_code_installs_builtin_home_and_uses_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path))
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    captured: dict[str, Path] = {}

    def fake_run_repl(agent_path: Path, workspace: Path, **kwargs) -> int:
        captured.update(agent_path=agent_path, workspace=workspace)
        return 0

    monkeypatch.setattr(cli, "run_repl", fake_run_repl)

    assert cli.main(["code"]) == 0
    assert captured == {
        "agent_path": tmp_path / "agent-quenda-code",
        "workspace": project,
    }


def test_gateway_start_uses_background_manager(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeGateway:
        log_file = Path("gateway.log")

        def start(self, *, host: str, port: int):
            return type(
                "Status",
                (),
                {"host": host, "port": port, "pid": 42},
            )()

    monkeypatch.setattr(cli, "GatewayManager", FakeGateway)

    assert cli.main(["gateway", "start", "--port", "9000"]) == 0
    assert "http://127.0.0.1:9000 (PID 42)" in capsys.readouterr().out
