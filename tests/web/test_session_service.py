"""Session service end-to-end behavior with an injected runtime."""

import base64
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from quenda.host import AgentHomeManager, find_builtin_agent
from quenda.runtime.events import (
    EvolutionCompleted,
    EvolutionFailed,
    ModelResponded,
    ModelRetrying,
    PromptCacheObserved,
)
from quenda.web.models.session import SessionActivity, SessionAttachment
from quenda.web.services.session_service import SessionService, TurnRequest, TurnResult
from quenda.web.tools import PublishAttachmentTool


@pytest.mark.asyncio
async def test_session_uses_runner_and_persists_messages(tmp_path: Path) -> None:
    manager = AgentHomeManager(tmp_path / "quenda")
    manager.create("reviewer")
    calls: list[TurnRequest] = []

    async def runner(request: TurnRequest) -> TurnResult:
        calls.append(request)
        return TurnResult(content="Real runtime response")

    service = SessionService(
        tmp_path / "sessions",
        agent_manager=manager,
        runner=runner,
    )
    session = await service.create_session(
        SimpleNamespace(agent_id="reviewer", workspace_id=None, title="Review")
    )

    result = await service.send_message(session.id, "Review this")
    messages = await service.get_messages(session.id)

    assert result is not None
    assert result["agent_message"]["content"] == "Real runtime response"
    assert [(call.agent_id, call.workspace_id, call.session_id, call.message) for call in calls] == [
        ("reviewer", None, session.id, "Review this")
    ]
    assert messages is not None
    assert [message.role for message in messages] == ["user", "assistant"]
    assert (await service.get_session(session.id)).message_count == 2  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_assistant_message_persists_turn_usage_duration_and_run_id(
    tmp_path: Path,
) -> None:
    manager = AgentHomeManager(tmp_path / "quenda")
    manager.create("reviewer")

    async def runner(request: TurnRequest) -> TurnResult:
        return TurnResult(
            content="Measured response",
            run_id="run-measured",
            input_tokens=120,
            output_tokens=30,
            duration_ms=875,
        )

    service = SessionService(
        tmp_path / "sessions", agent_manager=manager, runner=runner
    )
    session = await service.create_session(
        SimpleNamespace(agent_id="reviewer", workspace_id=None, title=None)
    )

    await service.send_message(session.id, "Measure this")
    messages = await service.get_messages(session.id)
    updated = await service.get_session(session.id)

    assert messages is not None
    assistant = messages[-1]
    assert assistant.run_id == "run-measured"
    assert assistant.input_tokens == 120
    assert assistant.output_tokens == 30
    assert assistant.tokens == 150
    assert assistant.duration_ms == 875
    assert updated is not None and updated.total_tokens == 150


def test_retry_activity_keeps_the_concrete_failure_reason() -> None:
    activity = SessionService._activity_from_event(
        ModelRetrying(
            provider="volcengine-coding",
            model_id="deepseek-v4-flash",
            attempt=3,
            max_attempts=4,
            delay_seconds=2,
            error_type="NetworkError",
            error_message="Connection failed: Request timed out.",
        )
    )

    assert activity.summary == (
        "Retrying volcengine-coding/deepseek-v4-flash · attempt 3/4 · "
        "Request timed out"
    )
    assert activity.detail["error_message"] == "Connection failed: Request timed out."


def test_legacy_retry_activity_gets_a_useful_network_reason() -> None:
    activity = SessionActivity(
        id="legacy-retry",
        type="model_retrying",
        title="Model Retrying",
        summary="Retrying model · attempt 2/4",
        created_at=datetime.now(),
        detail={"error_type": "NetworkError"},
    )

    enriched = SessionService._enrich_persisted_activity(activity)

    assert enriched.summary.endswith("· Network request failed")


def test_prompt_cache_activity_exposes_estimates_without_prompt_content() -> None:
    activity = SessionService._activity_from_event(
        PromptCacheObserved(
            assembly_digest="assembly-digest",
            stable_prefix_digest="prefix-digest",
            segment_count=5,
            reused_prefix_segment_count=4,
            estimated_reused_prefix_tokens=320,
        )
    )

    assert activity.title == "Prompt cache"
    assert activity.summary == "Reused 4/5 prompt segments · ~320 tokens"
    assert "content" not in activity.detail


def test_model_activity_exposes_provider_reported_cache_usage() -> None:
    activity = SessionService._activity_from_event(
        ModelResponded(
            input_tokens=900,
            output_tokens=100,
            cached_input_tokens=700,
            cache_creation_input_tokens=50,
        )
    )

    assert activity.summary == (
        "Model returned a response · 700 cached input tokens · "
        "50 cache-write tokens"
    )
    assert activity.detail["input_tokens"] == 900
    assert activity.detail["cached_input_tokens"] == 700
    assert activity.detail["cache_creation_input_tokens"] == 50


def test_memory_evolution_activity_reports_commits_and_isolated_failures() -> None:
    completed = SessionService._activity_from_event(
        EvolutionCompleted(
            triggered=True,
            write_mode="automatic",
            proposal_count=2,
            committed_count=1,
            rejected_count=1,
        )
    )
    failed = SessionService._activity_from_event(
        EvolutionFailed(
            error_type="NetworkError",
            error_message="Evolution model unavailable",
        )
    )

    assert completed.title == "Memory evolution"
    assert completed.summary == "Evaluated 2 proposal(s) · committed 1 · staged 0"
    assert failed.status == "error"
    assert failed.summary == "Evolution model unavailable"


@pytest.mark.asyncio
async def test_interaction_request_can_be_answered_and_continues_the_session(
    tmp_path: Path,
) -> None:
    manager = AgentHomeManager(tmp_path / "quenda")
    manager.create("reviewer")
    calls: list[TurnRequest] = []

    async def runner(request: TurnRequest) -> TurnResult:
        calls.append(request)
        if len(calls) == 1:
            return TurnResult(
                content="",
                interaction={
                    "id": "interaction-1",
                    "run_id": "run-1",
                    "request": {
                        "kind": "choice",
                        "title": "Choose a review depth",
                        "message": "How thorough should I be?",
                        "options": [
                            {"id": "quick", "label": "Quick"},
                            {"id": "deep", "label": "Deep"},
                        ],
                    },
                },
            )
        return TurnResult(content="Continuing with a deep review.")

    service = SessionService(
        tmp_path / "sessions", agent_manager=manager, runner=runner
    )
    session = await service.create_session(
        SimpleNamespace(agent_id="reviewer", workspace_id=None, title=None)
    )

    paused = await service.send_message(session.id, "Review this")

    assert paused is not None
    assert paused["agent_message"] is None
    assert paused["interaction"]["status"] == "pending"
    assert (await service.get_interactions(session.id))[0].title == "Choose a review depth"

    continued = await service.respond_to_interaction(
        session.id,
        "interaction-1",
        [{"question_id": "interaction-1", "selected_option_ids": ["deep"]}],
    )

    assert continued is not None
    assert continued["agent_message"]["content"] == "Continuing with a deep review."
    assert calls[1].message == "[User selected: Deep]"
    assert (await service.get_interactions(session.id))[0].status == "answered"


@pytest.mark.asyncio
async def test_interaction_response_rejects_multiple_values_for_single_choice(
    tmp_path: Path,
) -> None:
    manager = AgentHomeManager(tmp_path / "quenda")
    manager.create("reviewer")

    async def runner(request: TurnRequest) -> TurnResult:
        return TurnResult(
            content="",
            interaction={
                "id": "single-choice",
                "request": {
                    "kind": "choice",
                    "title": "Pick one",
                    "options": [
                        {"id": "a", "label": "A"},
                        {"id": "b", "label": "B"},
                    ],
                },
            },
        )

    service = SessionService(
        tmp_path / "sessions", agent_manager=manager, runner=runner
    )
    session = await service.create_session(
        SimpleNamespace(agent_id="reviewer", workspace_id=None, title=None)
    )
    await service.send_message(session.id, "Ask me")

    with pytest.raises(ValueError, match="Only one option"):
        await service.respond_to_interaction(
            session.id,
            "single-choice",
            [{"question_id": "single-choice", "selected_option_ids": ["a", "b"]}],
        )


@pytest.mark.asyncio
async def test_session_rejects_unknown_agent(tmp_path: Path) -> None:
    service = SessionService(
        tmp_path / "sessions",
        agent_manager=AgentHomeManager(tmp_path / "quenda"),
    )

    with pytest.raises(ValueError, match="not found"):
        await service.create_session(
            SimpleNamespace(agent_id="missing", workspace_id=None, title=None)
        )


@pytest.mark.asyncio
async def test_session_identifier_cannot_escape_storage(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    service = SessionService(tmp_path / "sessions")

    assert await service.get_session("../outside") is None
    assert await service.delete_session("../outside") is False
    assert outside.is_dir()


@pytest.mark.asyncio
async def test_empty_runtime_response_is_reported_as_failure(tmp_path: Path) -> None:
    manager = AgentHomeManager(tmp_path / "quenda")
    manager.create("reviewer")

    async def empty_runner(request: TurnRequest) -> TurnResult:
        return TurnResult(content="")

    service = SessionService(
        tmp_path / "sessions",
        agent_manager=manager,
        runner=empty_runner,
    )
    session = await service.create_session(
        SimpleNamespace(agent_id="reviewer", workspace_id=None, title=None)
    )

    with pytest.raises(RuntimeError, match="empty response"):
        await service.send_message(session.id, "hello")


@pytest.mark.asyncio
async def test_attachments_and_runtime_activity_share_one_turn_interface(tmp_path: Path) -> None:
    manager = AgentHomeManager(tmp_path / "quenda")
    manager.create("reviewer")
    captured: list[TurnRequest] = []

    async def runner(request: TurnRequest) -> TurnResult:
        captured.append(request)
        return TurnResult(
            content="I received the files.",
            activities=(
                SessionActivity(
                    id="activity-1",
                    type="tool_executed",
                    title="read_file",
                    summary="notes.txt",
                    created_at=datetime.now(),
                    detail={"result": "hello"},
                ),
            ),
        )

    service = SessionService(tmp_path / "sessions", agent_manager=manager, runner=runner)
    session = await service.create_session(
        SimpleNamespace(agent_id="reviewer", workspace_id=None, title=None)
    )
    attachment = SimpleNamespace(
        name="notes.txt",
        media_type="text/plain",
        data=base64.b64encode(b"hello").decode(),
    )

    await service.send_message(session.id, "Read this", attachments=[attachment])
    messages = await service.get_messages(session.id)
    activities = await service.get_activities(session.id)

    assert messages is not None and messages[0].attachments[0].name == "notes.txt"
    assert captured[0].attachments[0].record.path.endswith("notes.txt")
    assert activities is not None and activities[0].title == "read_file"
    assert await service.get_attachment_path(session.id, messages[0].attachments[0].id)


@pytest.mark.asyncio
async def test_agent_published_attachment_is_stored_on_assistant_message(
    tmp_path: Path,
) -> None:
    manager = AgentHomeManager(tmp_path / "quenda")
    manager.create("reviewer")
    published_path = tmp_path / "sessions" / "placeholder" / "result.csv"
    published_path.parent.mkdir(parents=True)
    published_path.write_text("a,b\n1,2\n")

    async def runner(request: TurnRequest) -> TurnResult:
        return TurnResult(
            content="Here is the report.",
            attachments=(
                SessionAttachment(
                    id="published1",
                    name="result.csv",
                    media_type="text/csv",
                    size=8,
                    path=str(published_path),
                ),
            ),
        )

    service = SessionService(
        tmp_path / "sessions", agent_manager=manager, runner=runner
    )
    session = await service.create_session(
        SimpleNamespace(agent_id="reviewer", workspace_id=None, title=None)
    )

    await service.send_message(session.id, "Create a report")
    messages = await service.get_messages(session.id)

    assert messages is not None
    assert messages[-1].role == "assistant"
    assert messages[-1].attachments[0].name == "result.csv"


@pytest.mark.asyncio
async def test_agent_can_reply_with_only_a_published_attachment(tmp_path: Path) -> None:
    manager = AgentHomeManager(tmp_path / "quenda")
    manager.create("reviewer")
    file_path = tmp_path / "result.zip"
    file_path.write_bytes(b"zip")

    async def runner(request: TurnRequest) -> TurnResult:
        return TurnResult(
            content="",
            attachments=(
                SessionAttachment(
                    id="abc12345",
                    name="result.zip",
                    media_type="application/zip",
                    size=3,
                    path=str(file_path),
                ),
            ),
        )

    service = SessionService(
        tmp_path / "sessions", agent_manager=manager, runner=runner
    )
    session = await service.create_session(
        SimpleNamespace(agent_id="reviewer", workspace_id=None, title=None)
    )

    result = await service.send_message(session.id, "Send the archive")

    assert result is not None
    assert result["agent_message"]["content"] == ""
    assert result["agent_message"]["attachments"][0]["name"] == "result.zip"


@pytest.mark.asyncio
async def test_slash_commands_include_skills_and_can_switch_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path / "quenda"))
    manager = AgentHomeManager(tmp_path / "quenda")
    source = find_builtin_agent("quenda-code")
    assert source is not None
    home = manager.create("reviewer", source=source)
    skill = home.path / "skills" / "summarizer"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: summarizer\ndescription: Summarize supplied material\n---\n\nSummarize.\n"
    )
    service = SessionService(tmp_path / "sessions", agent_manager=manager)
    session = await service.create_session(
        SimpleNamespace(agent_id="reviewer", workspace_id=None, title=None)
    )

    commands = await service.list_commands(session.id, "/")
    result = await service.send_message(session.id, "/model jdcloud/GLM-4.7")
    activated = await service.send_message(session.id, "/skill activate summarizer")
    skills = await service.send_message(session.id, "/skill list")
    updated = await service.get_session(session.id)

    assert commands is not None
    assert {command["name"] for command in commands} >= {"model", "skill", "summarizer"}
    assert result is not None and "Switched" in result["agent_message"]["content"]
    assert activated is not None and "Activated" in activated["agent_message"]["content"]
    assert skills is not None and "summarizer" in skills["agent_message"]["content"]
    assert updated is not None and (updated.provider, updated.model) == ("jdcloud", "GLM-4.7")


@pytest.mark.asyncio
async def test_web_runtime_exposes_publish_attachment_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QUENDA_HOME", str(tmp_path / "quenda"))
    manager = AgentHomeManager(tmp_path / "quenda")
    source = find_builtin_agent("quenda-code")
    assert source is not None
    manager.create("reviewer", source=source)
    service = SessionService(tmp_path / "sessions", agent_manager=manager)
    session = await service.create_session(
        SimpleNamespace(agent_id="reviewer", workspace_id=None, title=None)
    )

    prepared = await service._prepare_runtime(session.id)

    assert prepared is not None
    setup, runtime_session, _runtime, _registry = prepared
    publishers = [
        tool for tool in setup.agent.tools if isinstance(tool, PublishAttachmentTool)
    ]
    assert len(publishers) == 1
    assert any(tool.name == "publish_attachment" for tool in runtime_session.tools)
