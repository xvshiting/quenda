"""Lifecycle management for the local Quenda HTTP gateway."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GatewayStatus:
    """Observable state of the managed gateway process."""

    running: bool
    pid: int | None = None
    host: str | None = None
    port: int | None = None
    started_at: float | None = None


class GatewayManager:
    """Start and stop one background Web UI process for this Quenda Home."""

    def __init__(self, root: Path | None = None) -> None:
        configured = Path(os.environ["QUENDA_HOME"]) if "QUENDA_HOME" in os.environ else None
        quenda_root = (root or configured or Path.home() / ".quenda").expanduser()
        self.state_dir = quenda_root / "gateway"
        self.state_file = self.state_dir / "gateway.json"
        self.log_file = self.state_dir / "gateway.log"

    def status(self) -> GatewayStatus:
        """Return current managed state, cleaning up stale state files."""
        state = self._read_state()
        if state is None:
            return GatewayStatus(running=False)
        pid = state.get("pid")
        if not isinstance(pid, int) or not self._is_gateway_process(pid):
            self.state_file.unlink(missing_ok=True)
            return GatewayStatus(running=False)
        return GatewayStatus(
            running=True,
            pid=pid,
            host=str(state.get("host", "127.0.0.1")),
            port=int(state.get("port", 8000)),
            started_at=float(state.get("started_at", 0)),
        )

    def start(self, *, host: str = "127.0.0.1", port: int = 8000) -> GatewayStatus:
        """Start the gateway in a detached child process."""
        current = self.status()
        if current.running:
            raise RuntimeError(f"Gateway is already running with PID {current.pid}")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "quenda.web.app:app",
            "--host",
            host,
            "--port",
            str(port),
        ]
        with self.log_file.open("a", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        # Catch import, lifespan, and bind failures without claiming success.
        startup_deadline = time.monotonic() + 1.0
        while time.monotonic() < startup_deadline:
            return_code = process.poll()
            if return_code is not None:
                raise RuntimeError(
                    f"Gateway exited during startup with code {return_code}; see {self.log_file}"
                )
            time.sleep(0.05)
        state = {
            "pid": process.pid,
            "host": host,
            "port": port,
            "started_at": time.time(),
            "python": sys.executable,
        }
        self.state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        return GatewayStatus(running=True, **{key: state[key] for key in ("pid", "host", "port", "started_at")})

    def stop(self, *, timeout: float = 5.0) -> bool:
        """Stop the managed gateway, escalating only if graceful shutdown stalls."""
        current = self.status()
        if not current.running or current.pid is None:
            return False
        os.kill(current.pid, signal.SIGTERM)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self._process_exists(current.pid):
                self.state_file.unlink(missing_ok=True)
                return True
            time.sleep(0.05)
        if self._is_gateway_process(current.pid):
            os.kill(current.pid, signal.SIGKILL)
        self.state_file.unlink(missing_ok=True)
        return True

    def restart(self, *, host: str | None = None, port: int | None = None) -> GatewayStatus:
        """Restart using explicit values or the last recorded binding."""
        state = self._read_state() or {}
        next_host = host or str(state.get("host", "127.0.0.1"))
        next_port = port if port is not None else int(state.get("port", 8000))
        self.stop()
        return self.start(host=next_host, port=next_port)

    def tail_logs(self, lines: int = 50) -> str:
        """Return the last bounded set of log lines."""
        if not self.log_file.is_file():
            return ""
        content = self.log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(content[-max(lines, 0) :])

    def _read_state(self) -> dict[str, Any] | None:
        if not self.state_file.is_file():
            return None
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.state_file.unlink(missing_ok=True)
            return None
        return state if isinstance(state, dict) else None

    @staticmethod
    def _process_exists(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return False
        return True

    def _is_gateway_process(self, pid: int) -> bool:
        if not self._process_exists(pid):
            return False
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        command = result.stdout
        return "uvicorn" in command and "quenda.web.app:app" in command


__all__ = ["GatewayManager", "GatewayStatus"]
