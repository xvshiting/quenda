"""Gateway process lifecycle tests."""

from __future__ import annotations

import json
from pathlib import Path

from quenda.gateway import GatewayManager


def test_status_cleans_stale_state(tmp_path: Path, monkeypatch) -> None:
    manager = GatewayManager(tmp_path)
    manager.state_dir.mkdir(parents=True)
    manager.state_file.write_text(
        json.dumps({"pid": 999, "host": "127.0.0.1", "port": 8000}),
        encoding="utf-8",
    )
    monkeypatch.setattr(manager, "_is_gateway_process", lambda pid: False)

    assert manager.status().running is False
    assert not manager.state_file.exists()


def test_logs_returns_bounded_tail(tmp_path: Path) -> None:
    manager = GatewayManager(tmp_path)
    manager.state_dir.mkdir(parents=True)
    manager.log_file.write_text("one\ntwo\nthree\n", encoding="utf-8")

    assert manager.tail_logs(2) == "two\nthree"


def test_restart_reuses_previous_binding(tmp_path: Path, monkeypatch) -> None:
    manager = GatewayManager(tmp_path)
    manager.state_dir.mkdir(parents=True)
    manager.state_file.write_text(
        json.dumps({"pid": 123, "host": "0.0.0.0", "port": 9000}),
        encoding="utf-8",
    )
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(manager, "stop", lambda: calls.append(("stop", None)) or True)

    def fake_start(*, host: str, port: int):
        calls.append((host, port))
        return "started"

    monkeypatch.setattr(manager, "start", fake_start)

    assert manager.restart() == "started"
    assert calls == [("stop", None), ("0.0.0.0", 9000)]
