"""Web application serving contract."""

import asyncio

from fastapi.testclient import TestClient

from quenda.web.app import app
from quenda.web.models.session import SessionAttachment
from quenda.web.services.session_service import TurnRequest, TurnResult


def test_root_serves_web_application(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path / "quenda"))
    with TestClient(app) as client:
        response = client.get("/")
        health = client.get("/api/health")
        providers = client.get("/api/models/providers")
        system = client.get("/api/system")
        capabilities = client.get("/api/system/capabilities")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<div id="root"></div>' in response.text
    assert health.json() == {"status": "ok"}
    assert providers.status_code == 200
    assert any(provider["id"] == "jdcloud" for provider in providers.json())
    assert all("configured" in provider for provider in providers.json())
    assert system.status_code == 200
    assert "quenda_home" in system.json()
    assert capabilities.status_code == 200
    assert capabilities.json()["schema_version"] == "quenda.capabilities/v1"
    assert (tmp_path / "quenda" / "agent-quenda-code" / "workspace").is_dir()


def test_management_and_chat_api_form_one_working_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path / "quenda"))

    async def fake_runner(request: TurnRequest) -> TurnResult:
        return TurnResult(content=f"{request.agent_id} answered: {request.message}")

    with TestClient(app) as client:
        client.app.state.session_service._runner = fake_runner
        agent = client.post(
            "/api/agents",
            json={"name": "reviewer", "description": "Reviews code"},
        )
        assert agent.status_code == 200, agent.text

        workspace_path = tmp_path / "project"
        workspace = client.post(
            "/api/workspaces",
            json={"name": "project", "path": str(workspace_path)},
        )
        assert workspace.status_code == 200, workspace.text
        workspace_id = workspace.json()["id"]

        session = client.post(
            "/api/sessions",
            json={"agent_id": "reviewer", "workspace_id": workspace_id},
        )
        assert session.status_code == 200, session.text
        session_id = session.json()["id"]

        response = client.post(
            f"/api/sessions/{session_id}/send",
            json={"message": "Find the risk", "stream": False},
        )
        assert response.status_code == 200, response.text
        assert response.json()["agent_message"]["content"] == (
            "reviewer answered: Find the risk"
        )

        messages = client.get(f"/api/sessions/{session_id}/messages")
        assert [item["role"] for item in messages.json()] == ["user", "assistant"]


def test_restart_lists_agents_and_sessions_with_scalar_default_model(
    tmp_path,
    monkeypatch,
) -> None:
    """Persisted provider/model shorthand must survive Web service reloads."""
    quenda_home = tmp_path / "quenda"
    monkeypatch.setenv("QUENDA_HOME", str(quenda_home))

    with TestClient(app, raise_server_exceptions=False) as client:
        agent = client.post("/api/agents", json={"name": "reviewer"})
        assert agent.status_code == 200, agent.text
        session = client.post("/api/sessions", json={"agent_id": "reviewer"})
        assert session.status_code == 200, session.text

        agent_home = quenda_home / "agent-reviewer"
        (agent_home / "config.yaml").write_text(
            "models:\n  default: jdcloud/GLM-5\n",
            encoding="utf-8",
        )

        agents = client.get("/api/agents")
        sessions = client.get("/api/sessions")

    assert agents.status_code == 200, agents.text
    assert sessions.status_code == 200, sessions.text
    reviewer = next(item for item in agents.json() if item["id"] == "reviewer")
    assert (reviewer["provider"], reviewer["model"]) == ("jdcloud", "GLM-5")
    persisted = next(item for item in sessions.json() if item["agent_id"] == "reviewer")
    assert (persisted["provider"], persisted["model"]) == ("jdcloud", "GLM-5")


def test_interaction_api_pauses_and_continues_chat(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path / "quenda"))
    calls: list[TurnRequest] = []

    async def interactive_runner(request: TurnRequest) -> TurnResult:
        calls.append(request)
        if len(calls) == 1:
            return TurnResult(
                content="",
                interaction={
                    "id": "interaction-api",
                    "request": {
                        "kind": "confirm",
                        "title": "Apply changes?",
                        "message": "This will modify files.",
                    },
                },
            )
        return TurnResult(content="Changes applied.")

    with TestClient(app) as client:
        client.app.state.session_service._runner = interactive_runner
        assert client.post("/api/agents", json={"name": "reviewer"}).status_code == 200
        session_id = client.post(
            "/api/sessions", json={"agent_id": "reviewer"}
        ).json()["id"]

        paused = client.post(
            f"/api/sessions/{session_id}/send", json={"message": "Apply it"}
        )
        assert paused.status_code == 200
        assert paused.json()["interaction"]["title"] == "Apply changes?"
        pending = client.get(
            f"/api/sessions/{session_id}/interactions", params={"pending_only": True}
        )
        assert pending.json()[0]["options"][0]["id"] == "yes"

        continued = client.post(
            f"/api/sessions/{session_id}/interactions/interaction-api/respond",
            json={
                "answers": [
                    {
                        "question_id": "interaction-api",
                        "selected_option_ids": ["yes"],
                    }
                ]
            },
        )

        assert continued.status_code == 200, continued.text
        assert continued.json()["agent_message"]["content"] == "Changes applied."
        assert calls[1].message == "[User confirmed: Yes]"


def test_websocket_uses_the_real_session_service(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path / "quenda"))

    async def fake_runner(request: TurnRequest) -> TurnResult:
        if request.on_delta is not None:
            request.on_delta("WebSocket ")
            request.on_delta("answer: ")
        return TurnResult(content=f"WebSocket answer: {request.message}")

    with TestClient(app) as client:
        client.app.state.session_service._runner = fake_runner
        agent = client.post("/api/agents", json={"name": "reviewer"})
        assert agent.status_code == 200
        session = client.post("/api/sessions", json={"agent_id": "reviewer"})
        session_id = session.json()["id"]

        with client.websocket_connect(f"/ws/sessions/{session_id}") as socket:
            socket.send_json({"type": "user_message", "content": "Review this"})
            assert socket.receive_json()["type"] == "stream_start"
            assert socket.receive_json()["content"] == "WebSocket "
            assert socket.receive_json()["content"] == "answer: "
            finished = socket.receive_json()

        assert finished["type"] == "stream_end"
        assert finished["content"] == "WebSocket answer: Review this"


def test_websocket_interrupt_cancels_the_active_turn(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path / "quenda"))

    async def cancellable_runner(request: TurnRequest) -> TurnResult:
        assert request.cancellation_token is not None
        while not request.cancellation_token.is_cancelled:
            await asyncio.sleep(0.01)
        return TurnResult(content="")

    with TestClient(app) as client:
        client.app.state.session_service._runner = cancellable_runner
        assert client.post("/api/agents", json={"name": "reviewer"}).status_code == 200
        session_id = client.post(
            "/api/sessions", json={"agent_id": "reviewer"}
        ).json()["id"]

        with client.websocket_connect(f"/ws/sessions/{session_id}") as socket:
            socket.send_json({"type": "user_message", "content": "Keep going"})
            assert socket.receive_json()["type"] == "stream_start"
            socket.send_json({"type": "interrupt"})
            interrupted = socket.receive_json()

        assert interrupted["type"] == "stream_interrupted"


def test_websocket_can_answer_an_interaction(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path / "quenda"))
    calls: list[TurnRequest] = []

    async def interactive_runner(request: TurnRequest) -> TurnResult:
        calls.append(request)
        if len(calls) == 1:
            return TurnResult(
                content="",
                interaction={
                    "id": "ws-interaction",
                    "request": {
                        "kind": "choice",
                        "title": "Pick one",
                        "options": [{"id": "a", "label": "Option A"}],
                    },
                },
            )
        return TurnResult(content="Continued over WebSocket")

    with TestClient(app) as client:
        client.app.state.session_service._runner = interactive_runner
        assert client.post("/api/agents", json={"name": "reviewer"}).status_code == 200
        session_id = client.post(
            "/api/sessions", json={"agent_id": "reviewer"}
        ).json()["id"]

        with client.websocket_connect(f"/ws/sessions/{session_id}") as socket:
            socket.send_json({"type": "user_message", "content": "Start"})
            assert socket.receive_json()["type"] == "stream_start"
            requested = socket.receive_json()
            assert requested["type"] == "interaction_requested"
            socket.send_json(
                {
                    "type": "interaction_response",
                    "interaction_id": "ws-interaction",
                    "answers": [
                        {
                            "question_id": "ws-interaction",
                            "selected_option_ids": ["a"],
                        }
                    ],
                }
            )
            completed = socket.receive_json()

        assert completed["type"] == "stream_end"
        assert completed["content"] == "Continued over WebSocket"
        assert calls[1].message == "[User selected: Option A]"


def test_agent_image_attachment_is_served_inline(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path / "quenda"))

    async def image_runner(request: TurnRequest) -> TurnResult:
        attachment_dir = tmp_path / "quenda" / "sessions" / request.session_id / "attachments"
        attachment_dir.mkdir(parents=True, exist_ok=True)
        image_path = attachment_dir / "a1b2c3d4-preview.png"
        image_path.write_bytes(b"png")
        return TurnResult(
            content="Generated image",
            attachments=(
                SessionAttachment(
                    id="a1b2c3d4",
                    name="preview.png",
                    media_type="image/png",
                    size=3,
                    path=str(image_path),
                ),
            ),
        )

    with TestClient(app) as client:
        client.app.state.session_service._runner = image_runner
        assert client.post("/api/agents", json={"name": "artist"}).status_code == 200
        session_id = client.post(
            "/api/sessions", json={"agent_id": "artist"}
        ).json()["id"]
        sent = client.post(
            f"/api/sessions/{session_id}/send", json={"message": "Draw it"}
        )
        assert sent.status_code == 200

        image = client.get(f"/api/sessions/{session_id}/attachments/a1b2c3d4")

        assert image.status_code == 200
        assert image.headers["content-type"].startswith("image/png")
        assert image.headers["content-disposition"].startswith("inline")
