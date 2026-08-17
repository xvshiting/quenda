"""Persistent Web sessions backed by the Quenda Host and Runtime."""

from __future__ import annotations

import base64
import binascii
import json
import re
import time
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass, is_dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from quenda.host import (
    AgentHomeManager,
    ReplRuntime,
    build_prompt_cache_event,
    create_default_registry,
    load_agent_commands,
    setup_agent,
)
from quenda.host.loader import ModelsConfig
from quenda.kernel.types import ImageContent, TextContent
from quenda.providers import get_provider_registry
from quenda.runtime.events import (
    AnyEvent,
    ErrorOccurred,
    InteractionRequested,
    ModelResponseDelta,
    RunInterrupted,
    RunPaused,
    RunTerminated,
)
from quenda.runtime.cancellation import CancellationToken
from quenda.web.models.session import (
    SessionActivity,
    SessionAttachment,
    SessionInfo,
    SessionInteraction,
    SessionMessage,
    SessionUsage,
)
from quenda.web.services.workspace_service import WorkspaceService

_SESSION_ID = re.compile(r"^[0-9a-f]{8}$")
_ATTACHMENT_ID = re.compile(r"^[0-9a-f]{8}$")
_MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
_MAX_TOTAL_ATTACHMENT_BYTES = 50 * 1024 * 1024
_MAX_ATTACHMENTS = 8
_MAX_ACTIVITY_TEXT = 50_000


@dataclass(frozen=True)
class TurnAttachment:
    """One validated attachment available to a Runtime turn."""

    record: SessionAttachment
    data: str


@dataclass(frozen=True)
class TurnRequest:
    """Everything the Runtime needs for one Web conversation turn."""

    agent_id: str
    workspace_id: str | None
    session_id: str
    message: str
    attachments: tuple[TurnAttachment, ...] = ()
    provider: str | None = None
    model: str | None = None
    on_delta: Callable[[str], None] | None = None
    cancellation_token: CancellationToken | None = None


@dataclass(frozen=True)
class TurnResult:
    """Observable result of one turn, including its activity trace."""

    content: str
    activities: tuple[SessionActivity, ...] = ()
    run_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    provider: str | None = None
    model: str | None = None
    error: str | None = None
    interaction: dict[str, Any] | None = None
    attachments: tuple[SessionAttachment, ...] = ()
    activities_persisted: bool = False


AgentRunner = Callable[[TurnRequest], Awaitable[TurnResult]]


class SessionService:
    """Manage Web session metadata, messages, attachments, and Runtime turns."""

    def __init__(
        self,
        sessions_dir: Path | None = None,
        *,
        agent_manager: AgentHomeManager | None = None,
        workspace_service: WorkspaceService | None = None,
        runner: AgentRunner | None = None,
    ) -> None:
        self.sessions_dir = sessions_dir or Path.home() / ".quenda" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.agent_manager = agent_manager or AgentHomeManager()
        self.workspace_service = workspace_service
        self._runner = runner or self._run_agent

    async def list_sessions(
        self,
        agent_id: str | None = None,
        workspace_id: str | None = None,
        limit: int = 50,
    ) -> list[SessionInfo]:
        """List sessions, optionally filtered by agent or workspace."""
        sessions: list[SessionInfo] = []
        for session_dir in self.sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue
            session = await self._load_session_info(session_dir.name)
            if session is None:
                continue
            if agent_id and session.agent_id != agent_id:
                continue
            if workspace_id and session.workspace_id != workspace_id:
                continue
            sessions.append(session)
        sessions.sort(key=lambda item: item.updated_at, reverse=True)
        return [await self._enrich_session(session) for session in sessions[:limit]]

    async def create_session(self, request: Any) -> SessionInfo:
        """Create a session against an installed Agent Home."""
        try:
            home = self.agent_manager.get(request.agent_id)
        except ValueError as exc:
            raise ValueError(f"Invalid agent: {request.agent_id}") from exc
        if home is None:
            raise ValueError(f"Agent '{request.agent_id}' not found")
        if request.workspace_id and self.workspace_service is not None:
            if await self.workspace_service.get_workspace(request.workspace_id) is None:
                raise ValueError(f"Workspace '{request.workspace_id}' not found")

        provider = getattr(request, "provider", None)
        model = getattr(request, "model", None)
        self._validate_model(provider, model)
        session_id = uuid.uuid4().hex[:8]
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        session = SessionInfo(
            id=session_id,
            agent_id=request.agent_id,
            workspace_id=request.workspace_id,
            title=request.title or f"Session {session_id}",
            created_at=now,
            updated_at=now,
            provider=provider,
            model=model,
        )
        await self._update_session_info(session)
        return await self._enrich_session(session)

    async def update_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        update_model: bool = False,
    ) -> SessionInfo | None:
        """Update user-facing metadata or the model used by future turns."""
        session = await self._load_session_info(session_id)
        if session is None:
            return None
        if update_model:
            self._validate_model(provider, model)
            session.provider = provider
            session.model = model
        if title is not None:
            session.title = title.strip() or session.title
        session.updated_at = datetime.now()
        await self._update_session_info(session)
        return await self._enrich_session(session)

    async def get_session(self, session_id: str) -> SessionInfo | None:
        """Get one session by its opaque identifier."""
        if not _SESSION_ID.fullmatch(session_id):
            return None
        session = await self._load_session_info(session_id)
        return await self._enrich_session(session) if session is not None else None

    async def delete_session(self, session_id: str) -> bool:
        """Delete only the selected Web session directory."""
        if not _SESSION_ID.fullmatch(session_id):
            return False
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            return False
        import shutil

        shutil.rmtree(session_dir)
        return True

    async def get_messages(
        self, session_id: str, offset: int = 0, limit: int = 100
    ) -> list[SessionMessage] | None:
        """Get persisted conversational messages."""
        if not _SESSION_ID.fullmatch(session_id):
            return None
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            return None
        data = self._read_json(session_dir / "messages.json", default=[])
        if not isinstance(data, list):
            return []
        return [SessionMessage(**item) for item in data][offset : offset + limit]

    async def get_activities(self, session_id: str) -> list[SessionActivity] | None:
        """Get model, routing, tool, command, and error activity for a session."""
        if not _SESSION_ID.fullmatch(session_id):
            return None
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            return None
        data = self._read_json(session_dir / "activities.json", default=[])
        if not isinstance(data, list):
            return []
        return [
            self._enrich_persisted_activity(SessionActivity(**item))
            for item in data
        ]

    async def get_interactions(
        self, session_id: str, *, pending_only: bool = False
    ) -> list[SessionInteraction] | None:
        """Return durable interaction requests so a refreshed UI can resume them."""
        if not _SESSION_ID.fullmatch(session_id):
            return None
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            return None
        data = self._read_json(session_dir / "interactions.json", default=[])
        if not isinstance(data, list):
            return []
        interactions = [SessionInteraction(**item) for item in data]
        return [item for item in interactions if item.status == "pending"] if pending_only else interactions

    async def get_attachment_path(self, session_id: str, attachment_id: str) -> Path | None:
        """Resolve one recorded attachment without accepting arbitrary paths."""
        if not _SESSION_ID.fullmatch(session_id) or not _ATTACHMENT_ID.fullmatch(attachment_id):
            return None
        messages = await self.get_messages(session_id)
        if messages is None:
            return None
        attachment = next(
            (
                attachment
                for message in messages
                for attachment in message.attachments
                if attachment.id == attachment_id
            ),
            None,
        )
        if attachment is None:
            interactions = await self.get_interactions(session_id) or []
            attachment = next(
                (
                    item
                    for interaction in interactions
                    for item in interaction.attachments
                    if item.id == attachment_id
                ),
                None,
            )
        if attachment is None:
            return None
        root = (self.sessions_dir / session_id / "attachments").resolve()
        path = Path(attachment.path).resolve()
        return path if path.is_file() and path.is_relative_to(root) else None

    async def send_message(
        self,
        session_id: str,
        message: str,
        *,
        attachments: Sequence[Any] = (),
        stream: bool = True,
        on_delta: Callable[[str], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> dict[str, Any] | None:
        """Persist and execute one message through the shared turn interface."""
        session = await self.get_session(session_id)
        if session is None:
            return None
        if await self._pending_interaction(session_id) is not None:
            raise ValueError("Answer the pending interaction before sending another message")
        clean_message = message.strip()
        if not clean_message and not attachments:
            raise ValueError("Message or attachment is required")

        stored_attachments = self._store_attachments(session_id, attachments)
        user_message = SessionMessage(
            id=uuid.uuid4().hex[:8],
            session_id=session_id,
            role="user",
            content=clean_message,
            attachments=[item.record for item in stored_attachments],
            created_at=datetime.now(),
        )
        await self._save_message(session_id, user_message)

        result = await self._runner(
            TurnRequest(
                agent_id=session.agent_id,
                workspace_id=session.workspace_id,
                session_id=session_id,
                message=clean_message,
                attachments=tuple(stored_attachments),
                provider=session.provider,
                model=session.model,
                on_delta=on_delta,
                cancellation_token=cancellation_token,
            )
        )
        return await self._finish_turn(session_id, result, user_message=user_message)

    async def respond_to_interaction(
        self,
        session_id: str,
        interaction_id: str,
        answers: Sequence[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Validate a Web response and continue the paused Runtime session."""
        session = await self.get_session(session_id)
        if session is None:
            return None
        interaction = await self._pending_interaction(session_id)
        if interaction is None or interaction.id != interaction_id:
            raise ValueError("This interaction is no longer pending")

        continuation = self._interaction_continuation(interaction, answers)
        result = await self._runner(
            TurnRequest(
                agent_id=session.agent_id,
                workspace_id=session.workspace_id,
                session_id=session_id,
                message=continuation,
                provider=session.provider,
                model=session.model,
            )
        )
        if interaction.attachments:
            result = replace(
                result,
                attachments=tuple(interaction.attachments) + result.attachments,
            )
        await self._mark_interaction_answered(session_id, interaction_id, answers)
        return await self._finish_turn(session_id, result)

    async def list_commands(self, session_id: str, input_text: str = "") -> list[dict[str, Any]] | None:
        """Expose Slash commands and structured candidates to any Web client."""
        prepared = await self._prepare_runtime(session_id)
        if prepared is None:
            return None
        _setup, _runtime_session, runtime, registry = prepared
        value = input_text.lstrip("/")
        command_name, separator, args = value.partition(" ")
        if separator and registry.has(command_name):
            candidates = runtime.get_command_candidates(command_name, args)
            return [
                {
                    "name": command_name,
                    "value": candidate.value,
                    "label": candidate.label,
                    "description": candidate.description,
                    "kind": candidate.kind,
                }
                for candidate in candidates
            ]

        partial = command_name.lower()
        return [
            {
                "name": command.name,
                "value": f"/{command.name}",
                "label": f"/{command.name}",
                "description": command.description,
                "usage": command.usage,
                "kind": "command",
            }
            for command in sorted(registry.list_commands(), key=lambda item: item.name)
            if not partial or command.name.startswith(partial)
        ]

    async def get_usage(self, session_id: str) -> SessionUsage | None:
        session = await self.get_session(session_id)
        if session is None:
            return None
        messages = await self.get_messages(session_id) or []
        return SessionUsage(
            session_id=session_id,
            total_input_tokens=sum(message.input_tokens or 0 for message in messages),
            total_output_tokens=sum(message.output_tokens or 0 for message in messages),
            total_tokens=sum(message.tokens or 0 for message in messages),
            message_count=session.message_count,
        )

    async def _finish_turn(
        self,
        session_id: str,
        result: TurnResult,
        *,
        user_message: SessionMessage | None = None,
    ) -> dict[str, Any]:
        """Persist one completed or paused turn using the same Web response shape."""
        if not result.activities_persisted:
            await self._save_activities(session_id, result.activities)
        if result.provider or result.model:
            await self.update_session(
                session_id,
                provider=result.provider,
                model=result.model,
                update_model=True,
            )
        if result.error:
            raise RuntimeError(result.error)
        if result.interaction is not None:
            interaction = self._interaction_from_result(session_id, result.interaction)
            await self._save_interaction(session_id, interaction)
            return {
                "user_message": user_message.model_dump(mode="json") if user_message else None,
                "agent_message": None,
                "interaction": interaction.model_dump(mode="json"),
                "activities": [activity.model_dump(mode="json") for activity in result.activities],
            }
        if not result.content.strip() and not result.attachments:
            raise RuntimeError(
                "The model returned an empty response. Check the agent's provider, model, and credentials."
            )

        assistant_message = SessionMessage(
            id=uuid.uuid4().hex[:8],
            session_id=session_id,
            role="assistant",
            content=result.content,
            created_at=datetime.now(),
            tokens=result.input_tokens + result.output_tokens,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            duration_ms=result.duration_ms,
            run_id=result.run_id or None,
            attachments=list(result.attachments),
        )
        await self._save_message(session_id, assistant_message)
        return {
            "user_message": user_message.model_dump(mode="json") if user_message else None,
            "agent_message": assistant_message.model_dump(mode="json"),
            "interaction": None,
            "activities": [activity.model_dump(mode="json") for activity in result.activities],
        }

    def _interaction_from_result(
        self, session_id: str, value: dict[str, Any]
    ) -> SessionInteraction:
        request = value.get("request") if isinstance(value.get("request"), dict) else value
        questions = request.get("questions") or []
        options = request.get("options") or []
        if not questions and request.get("kind") == "confirm" and not options:
            options = [
                {"id": "yes", "label": "Yes", "description": "Proceed", "is_default": True},
                {"id": "no", "label": "No", "description": "Cancel"},
            ]
        return SessionInteraction(
            id=str(value.get("id") or value.get("call_id") or uuid.uuid4().hex),
            session_id=session_id,
            run_id=str(value.get("run_id") or ""),
            kind=str(request.get("kind") or "choice"),
            title=str(request.get("title") or request.get("header") or "Interaction required"),
            message=str(request.get("message") or request.get("question") or ""),
            options=self._json_safe(options),
            questions=self._json_safe(questions),
            default_option_id=request.get("default_option_id"),
            multiple=bool(request.get("multiple", False)),
            required=bool(request.get("required", True)),
            created_at=datetime.now(),
            attachments=list(value.get("attachments") or []),
        )

    async def _pending_interaction(self, session_id: str) -> SessionInteraction | None:
        interactions = await self.get_interactions(session_id, pending_only=True)
        return interactions[-1] if interactions else None

    async def _save_interaction(
        self, session_id: str, interaction: SessionInteraction
    ) -> None:
        path = self.sessions_dir / session_id / "interactions.json"
        data = self._read_json(path, default=[])
        stored = data if isinstance(data, list) else []
        stored.append(interaction.model_dump(mode="json"))
        self._write_json(path, stored)

    async def _mark_interaction_answered(
        self, session_id: str, interaction_id: str, answers: Sequence[dict[str, Any]]
    ) -> None:
        path = self.sessions_dir / session_id / "interactions.json"
        data = self._read_json(path, default=[])
        stored = data if isinstance(data, list) else []
        for item in stored:
            if item.get("id") == interaction_id:
                item["status"] = "answered"
                item["answered_at"] = datetime.now().isoformat()
                item["response"] = self._json_safe(list(answers))
        self._write_json(path, stored)

    @staticmethod
    def _interaction_continuation(
        interaction: SessionInteraction, answers: Sequence[dict[str, Any]]
    ) -> str:
        questions = interaction.questions or [
            {
                "id": interaction.id,
                "title": interaction.title,
                "kind": interaction.kind,
                "options": interaction.options,
                "required": interaction.required,
            }
        ]
        answer_map = {str(item.get("question_id")): item for item in answers}
        rendered: list[str] = []
        for question in questions:
            question_id = str(question.get("id") or interaction.id)
            answer = answer_map.get(question_id)
            required = bool(question.get("required", True))
            if answer is None:
                if required:
                    raise ValueError(f"Answer required for '{question.get('title') or question_id}'")
                continue
            option_ids = [str(value) for value in answer.get("selected_option_ids") or []]
            options = question.get("options") or interaction.options
            multiple = bool(question.get("multiple", interaction.multiple))
            if not multiple and len(option_ids) > 1:
                raise ValueError(f"Only one option may be selected for '{question_id}'")
            labels = [
                str(option.get("label") or option.get("id"))
                for option in options
                if str(option.get("id")) in option_ids
            ]
            value = str(answer.get("value") or "").strip()
            if not labels and not value and required:
                raise ValueError(f"Answer required for '{question.get('title') or question_id}'")
            if option_ids and len(labels) != len(option_ids):
                raise ValueError(f"Unknown option in answer for '{question_id}'")
            rendered_value = ", ".join(labels) if labels else value
            rendered.append(f"{question_id}: {rendered_value}")
        if not rendered:
            return "[User skipped the optional interaction.]"
        if interaction.questions:
            return "[User answers: " + "; ".join(rendered) + "]"
        value = rendered[0].split(": ", 1)[-1]
        if interaction.kind == "confirm":
            return f"[User confirmed: {value}]"
        if interaction.kind in {"choice", "menu"}:
            return f"[User selected: {value}]"
        return f"[User input: {value}]"

    async def _run_agent(self, request: TurnRequest) -> TurnResult:
        """Execute text, Slash commands, skills, and attachments through Quenda Host."""
        turn_started = time.perf_counter()
        prepared = await self._prepare_runtime(
            request.session_id,
            provider=request.provider,
            model=request.model,
        )
        if prepared is None:
            return TurnResult(content="", error="Unable to initialize this session")
        setup, runtime_session, runtime, _registry = prepared
        from quenda.web.tools import PublishAttachmentTool

        publisher = next(
            (
                tool
                for tool in setup.agent.tools
                if isinstance(tool, PublishAttachmentTool)
            ),
            None,
        )
        if publisher is None:
            return TurnResult(content="", error="Web attachment publishing is unavailable")
        usage_before = (
            runtime_session.state.usage.total_input_tokens,
            runtime_session.state.usage.total_output_tokens,
        )

        model_input = request.message
        command_activities: list[SessionActivity] = []
        if model_input.startswith("/") and not request.attachments:
            command_result = runtime.execute_command(model_input)
            if command_result is not None:
                command_activities.append(
                    SessionActivity(
                        id=uuid.uuid4().hex,
                        run_id=f"command-{uuid.uuid4().hex[:12]}",
                        type="command",
                        title=model_input.split(maxsplit=1)[0],
                        summary=command_result.message,
                        status="completed" if command_result.status == "ok" else "error",
                        created_at=datetime.now(),
                        detail={"input": model_input, "state_patch": command_result.state_patch},
                    )
                )
                self._append_activity(request.session_id, command_activities[-1])
                runtime_session.save()
                if command_result.model_input is None:
                    return TurnResult(
                        content=command_result.message or "Command completed.",
                        activities=tuple(command_activities),
                        run_id=command_activities[-1].run_id,
                        duration_ms=round((time.perf_counter() - turn_started) * 1000),
                        provider=runtime.state.provider_name,
                        model=runtime.state.model_name,
                        activities_persisted=True,
                    )
                model_input = command_result.model_input

        cache_observation = runtime.refresh_context()
        payload = self._build_runtime_message(model_input, request.attachments)
        observed_activities: list[SessionActivity] = []

        def observe(event: AnyEvent) -> None:
            if isinstance(event, ModelResponseDelta):
                if request.on_delta is not None:
                    request.on_delta(event.content)
                return
            activity = self._activity_from_event(event)
            observed_activities.append(activity)
            self._append_activity(request.session_id, activity)

        if cache_observation is not None:
            observe(build_prompt_cache_event(cache_observation))

        response, events = await runtime_session.send_collecting(
            payload,
            on_event=observe,
            skill_activation_handler=runtime.create_skill_activation_handler(),
            cancellation_token=request.cancellation_token,
        )
        runtime_session.save()
        activities = command_activities + observed_activities
        run_id = next((activity.run_id for activity in activities if activity.run_id), "")
        input_tokens = max(
            0, runtime_session.state.usage.total_input_tokens - usage_before[0]
        )
        output_tokens = max(
            0, runtime_session.state.usage.total_output_tokens - usage_before[1]
        )
        duration_ms = round((time.perf_counter() - turn_started) * 1000)
        error = next((event for event in events if isinstance(event, ErrorOccurred)), None)
        if error is not None:
            return TurnResult(
                content="",
                activities=tuple(activities),
                run_id=run_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
                provider=runtime.state.provider_name,
                model=runtime.state.model_name,
                error=error.error_message or error.error_type or "Agent run failed",
                attachments=tuple(publisher.published),
                activities_persisted=True,
            )
        interaction_event = next(
            (event for event in events if isinstance(event, InteractionRequested)), None
        )
        if interaction_event is not None:
            return TurnResult(
                content="",
                activities=tuple(activities),
                run_id=run_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
                provider=runtime.state.provider_name,
                model=runtime.state.model_name,
                interaction={
                    "id": interaction_event.call_id,
                    "run_id": run_id,
                    "request": interaction_event.request,
                    "attachments": [
                        attachment.model_dump(mode="json")
                        for attachment in publisher.published
                    ],
                },
                attachments=tuple(publisher.published),
                activities_persisted=True,
            )
        if any(isinstance(event, RunPaused) for event in events):
            return TurnResult(
                content="",
                activities=tuple(activities),
                run_id=run_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
                provider=runtime.state.provider_name,
                model=runtime.state.model_name,
                error="The agent paused without a valid interaction request",
                attachments=tuple(publisher.published),
                activities_persisted=True,
            )
        if any(isinstance(event, RunInterrupted | RunTerminated) for event in events):
            return TurnResult(
                content="",
                activities=tuple(activities),
                run_id=run_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
                provider=runtime.state.provider_name,
                model=runtime.state.model_name,
                error="The agent run ended before producing a response",
                attachments=tuple(publisher.published),
                activities_persisted=True,
            )
        return TurnResult(
            content=response,
            activities=tuple(activities),
            run_id=run_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            provider=runtime.state.provider_name,
            model=runtime.state.model_name,
            attachments=tuple(publisher.published),
            activities_persisted=True,
        )

    async def _prepare_runtime(
        self,
        session_id: str,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> tuple[Any, Any, ReplRuntime, Any] | None:
        session = await self.get_session(session_id)
        if session is None:
            return None
        home = self.agent_manager.prepare(session.agent_id)
        if home is None:
            raise ValueError(f"Agent '{session.agent_id}' not found")
        workspace = home.workspace
        if session.workspace_id is not None:
            if self.workspace_service is None:
                raise ValueError("Workspace service is unavailable")
            registered = await self.workspace_service.get_workspace(session.workspace_id)
            if registered is None:
                raise ValueError(f"Workspace '{session.workspace_id}' not found")
            workspace = Path(registered.path)

        setup = setup_agent(
            home.path,
            workspace,
            provider=provider or session.provider,
            model=model or session.model,
        )
        if setup is None:
            raise ValueError(f"Unable to initialize agent '{session.agent_id}'")
        from quenda.web.tools import PublishAttachmentTool

        setup.agent.add_tools(
            [
                PublishAttachmentTool(
                    workspace,
                    self.sessions_dir / session_id / "attachments",
                )
            ]
        )
        runtime_session = setup.agent.load_session(session_id)
        if runtime_session is None:
            runtime_session = setup.agent.open_session(session_id=session_id)
        registry = create_default_registry()
        load_agent_commands(home.path, registry)
        runtime = ReplRuntime(
            session=runtime_session,
            agent=setup.agent,
            context_builder=setup.context_builder,
            provider_name=setup.provider_name,
            model_name=setup.model_name,
            registry=registry,
            compressor=setup.compressor,
            agent_package_path=home.path,
            skill_discovery=setup.skill_discovery,
            skill_activator=setup.skill_activator,
            workspace_path=workspace,
            prompt_assembly=setup.context_snapshot.prompt_assembly,
        )
        runtime.set_host_binding(setup.binding)
        stored_skills = runtime_session.state.metadata.get("skills", [])
        if isinstance(stored_skills, list):
            runtime.activate_skills(
                [str(name) for name in stored_skills],
                transient=False,
            )
        return setup, runtime_session, runtime, registry

    def _store_attachments(
        self, session_id: str, attachments: Sequence[Any]
    ) -> list[TurnAttachment]:
        if len(attachments) > _MAX_ATTACHMENTS:
            raise ValueError(f"A message can contain at most {_MAX_ATTACHMENTS} attachments")
        result: list[TurnAttachment] = []
        total_size = 0
        attachment_dir = self.sessions_dir / session_id / "attachments"
        for item in attachments:
            if isinstance(item, dict):
                name_value = item.get("name", "attachment")
                media_value = item.get("media_type", "application/octet-stream")
                data_value = item.get("data", "")
            else:
                name_value = getattr(item, "name", "attachment")
                media_value = getattr(item, "media_type", "application/octet-stream")
                data_value = getattr(item, "data", "")
            name = Path(str(name_value)).name
            media_type = str(media_value)
            encoded = str(data_value)
            if "," in encoded and encoded.startswith("data:"):
                encoded = encoded.split(",", 1)[1]
            try:
                payload = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError(f"Attachment '{name}' is not valid base64") from exc
            if len(payload) > _MAX_ATTACHMENT_BYTES:
                raise ValueError(f"Attachment '{name}' exceeds the 25 MB limit")
            total_size += len(payload)
            if total_size > _MAX_TOTAL_ATTACHMENT_BYTES:
                raise ValueError("Attachments exceed the 50 MB message limit")
            attachment_id = uuid.uuid4().hex[:8]
            attachment_dir.mkdir(parents=True, exist_ok=True)
            path = attachment_dir / f"{attachment_id}-{name}"
            path.write_bytes(payload)
            record = SessionAttachment(
                id=attachment_id,
                name=name,
                media_type=media_type,
                size=len(payload),
                path=str(path),
            )
            result.append(TurnAttachment(record=record, data=encoded))
        return result

    @staticmethod
    def _build_runtime_message(
        message: str, attachments: Sequence[TurnAttachment]
    ) -> str | Sequence[TextContent | ImageContent]:
        if not attachments:
            return message
        blocks: list[TextContent | ImageContent] = [TextContent(text=message or "Review these files.")]
        file_references: list[str] = []
        for attachment in attachments:
            if attachment.record.media_type.startswith("image/"):
                blocks.append(
                    ImageContent(
                        media_type=attachment.record.media_type,
                        data=attachment.data,
                    )
                )
            else:
                file_references.append(
                    f"- {attachment.record.name} ({attachment.record.media_type}, "
                    f"{attachment.record.size} bytes): {attachment.record.path}"
                )
        if file_references:
            blocks.append(
                TextContent(
                    text="Attached files are available locally:\n" + "\n".join(file_references)
                )
            )
        return blocks

    @staticmethod
    def _retry_reason(message: str) -> str:
        """Return a compact, user-facing reason without losing diagnostics."""
        normalized = message.strip()
        lowered = normalized.lower()
        if "timed out" in lowered or "timeout" in lowered:
            return "Request timed out"
        if "name resolution" in lowered or "dns" in lowered:
            return "DNS lookup failed"
        if "connection reset" in lowered:
            return "Connection was reset"
        if "ssl" in lowered or "certificate" in lowered:
            return "TLS connection failed"
        if normalized.startswith("Connection failed: "):
            normalized = normalized.removeprefix("Connection failed: ")
        return normalized.rstrip(".")

    @staticmethod
    def _activity_from_event(event: AnyEvent) -> SessionActivity:
        data = asdict(event) if is_dataclass(event) else dict(vars(event))
        event_type = str(data.pop("type", type(event).__name__))
        event_id = str(data.pop("id", uuid.uuid4().hex))
        timestamp = data.pop("timestamp", datetime.now())
        run_id = str(data.pop("run_id", ""))
        duration_ms = int(data.get("duration_ms", 0) or 0)
        status = "completed"
        title = event_type.replace("_", " ").title()
        summary = ""
        if event_type in {"model_called", "model_routed", "model_retrying"}:
            target = "/".join(filter(None, [str(data.get("provider", "")), str(data.get("model_id", ""))]))
            if event_type == "model_retrying":
                summary = f"Retrying {target} · attempt {data.get('attempt', 1)}/{data.get('max_attempts', 1)}"
                reason = SessionService._retry_reason(str(data.get("error_message") or ""))
                if reason:
                    summary += f" · {reason}"
            elif event_type == "model_routed":
                summary = f"Routed this step to {target}"
            else:
                summary = f"Calling {target} · iteration {data.get('iteration', 1)}"
        elif event_type == "model_responded":
            tool_count = len(data.get("tool_call_details") or [])
            summary = (
                f"Model requested {tool_count} tool call{'s' if tool_count != 1 else ''}"
                if tool_count
                else "Model returned a response"
            )
            cached_tokens = int(data.get("cached_input_tokens", 0) or 0)
            created_tokens = int(
                data.get("cache_creation_input_tokens", 0) or 0
            )
            if cached_tokens:
                summary += f" · {cached_tokens} cached input tokens"
            if created_tokens:
                summary += f" · {created_tokens} cache-write tokens"
        elif event_type == "prompt_cache_observed":
            title = "Prompt cache"
            reused = int(data.get("reused_prefix_segment_count", 0) or 0)
            total = int(data.get("segment_count", 0) or 0)
            tokens = int(data.get("estimated_reused_prefix_tokens", 0) or 0)
            summary = f"Reused {reused}/{total} prompt segments · ~{tokens} tokens"
        elif event_type == "evolution_completed":
            title = "Memory evolution"
            if not data.get("triggered"):
                summary = "No evolution evaluation needed"
            else:
                summary = (
                    f"Evaluated {int(data.get('proposal_count', 0) or 0)} proposal(s)"
                    f" · committed {int(data.get('committed_count', 0) or 0)}"
                    f" · staged {int(data.get('staged_count', 0) or 0)}"
                )
        elif event_type == "evolution_failed":
            title = "Memory evolution"
            summary = str(data.get("error_message") or "Evolution evaluation failed")
            status = "error"
        elif event_type == "tool_phase_started":
            approved = len(data.get("approved_calls") or [])
            rejected = len(data.get("rejected_calls") or [])
            summary = f"Prepared {approved} tool call{'s' if approved != 1 else ''}"
            if rejected:
                summary += f" · rejected {rejected}"
        elif event_type == "tool_executed":
            title = str(data.get("tool_name") or "Tool executed")
            hint = str(data.get("display_hint") or "")
            result_summary = str(data.get("result_summary") or "")
            if title == "publish_attachment":
                summary = f"Sent {hint or 'a file'} to the chat"
            else:
                summary = " · ".join(value for value in (hint, result_summary) if value)
            summary = summary or "Tool completed"
            if data.get("is_error") or data.get("is_denied"):
                status = "error"
        elif event_type == "run_started":
            summary = f"{data.get('agent_name') or 'Agent'} started working"
        elif event_type == "run_completed":
            summary = f"Completed {data.get('total_steps', 0)} step(s)"
        elif event_type == "error_occurred":
            summary = str(data.get("error_message") or data.get("error_type") or "")
            status = "error"
        elif event_type == "interaction_requested":
            request = data.get("request") if isinstance(data.get("request"), dict) else {}
            title = str(request.get("title") or request.get("header") or "Input requested")
            summary = str(request.get("message") or request.get("question") or "Waiting for your answer")
            status = "needs_input"
        elif event_type == "permission_requested":
            summary = "Waiting for permission"
            status = "needs_input"
        elif event_type == "run_paused":
            summary = "Waiting for your answer"
            status = "needs_input"
        detail = SessionService._json_safe(data)
        return SessionActivity(
            id=event_id,
            run_id=run_id,
            type=event_type,
            title=title,
            summary=summary,
            status=status,
            created_at=timestamp if isinstance(timestamp, datetime) else datetime.now(),
            duration_ms=duration_ms,
            detail=detail if isinstance(detail, dict) else {"value": detail},
        )

    @staticmethod
    def _enrich_persisted_activity(activity: SessionActivity) -> SessionActivity:
        """Improve older retry records with any diagnostic detail they retain."""
        if activity.type != "model_retrying" or "Request timed out" in activity.summary:
            return activity
        reason = SessionService._retry_reason(
            str(activity.detail.get("error_message") or "")
        )
        if not reason and activity.detail.get("error_type") == "NetworkError":
            reason = "Network request failed"
        return activity.model_copy(
            update={"summary": f"{activity.summary} · {reason}"}
        ) if reason else activity

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): SessionService._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [SessionService._json_safe(item) for item in value]
        if isinstance(value, str) and len(value) > _MAX_ACTIVITY_TEXT:
            return value[:_MAX_ACTIVITY_TEXT] + "\n…[truncated]"
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    async def _load_session_info(self, session_id: str) -> SessionInfo | None:
        if not _SESSION_ID.fullmatch(session_id):
            return None
        path = self.sessions_dir / session_id / "session.json"
        data = self._read_json(path, default=None)
        return SessionInfo(**data) if isinstance(data, dict) else None

    async def _save_message(self, session_id: str, message: SessionMessage) -> None:
        path = self.sessions_dir / session_id / "messages.json"
        data = self._read_json(path, default=[])
        messages = data if isinstance(data, list) else []
        messages.append(message.model_dump(mode="json"))
        self._write_json(path, messages)
        session = await self._load_session_info(session_id)
        if session is not None:
            session.message_count += 1
            session.total_tokens += message.tokens or 0
            session.updated_at = datetime.now()
            await self._update_session_info(session)

    async def _save_activities(
        self, session_id: str, activities: Sequence[SessionActivity]
    ) -> None:
        for activity in activities:
            self._append_activity(session_id, activity)

    def _append_activity(self, session_id: str, activity: SessionActivity) -> None:
        """Append one event immediately so polling clients see live progress."""
        path = self.sessions_dir / session_id / "activities.json"
        data = self._read_json(path, default=[])
        stored = data if isinstance(data, list) else []
        stored.append(activity.model_dump(mode="json"))
        self._write_json(path, stored)

    async def _update_session_info(self, session: SessionInfo) -> None:
        path = self.sessions_dir / session.id / "session.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(path, session.model_dump(mode="json"))

    async def _enrich_session(self, session: SessionInfo) -> SessionInfo:
        home = self.agent_manager.get(session.agent_id)
        agent_name = home.name if home is not None else session.agent_id
        workspace_name = None
        workspace_path = None
        if session.workspace_id and self.workspace_service is not None:
            workspace = await self.workspace_service.get_workspace(session.workspace_id)
            if workspace is not None:
                workspace_name = workspace.name
                workspace_path = workspace.path
        elif home is not None:
            workspace_name = "Agent default"
            workspace_path = str(home.workspace)

        provider = session.provider
        model = session.model
        if home is not None and (provider is None or model is None):
            config_path = home.path / "config.yaml"
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
            config = config if isinstance(config, dict) else {}
            default_model = ModelsConfig.from_dict(config.get("models") or {}).default
            provider = provider or (default_model.provider if default_model else None)
            model = model or (default_model.model if default_model else None)

        return session.model_copy(
            update={
                "agent_name": agent_name,
                "workspace_name": workspace_name,
                "workspace_path": workspace_path,
                "provider": provider,
                "model": model,
            }
        )

    @staticmethod
    def _validate_model(provider: str | None, model: str | None) -> None:
        if provider is None and model is None:
            return
        if not provider or not model:
            raise ValueError("Provider and model must be selected together")
        try:
            get_provider_registry().get_model(provider, model)
        except KeyError as exc:
            raise ValueError(f"Unknown model: {provider}/{model}") from exc

    @staticmethod
    def _read_json(path: Path, *, default: Any) -> Any:
        if not path.is_file():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        """Atomically replace JSON read concurrently by polling clients."""
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)


__all__ = ["SessionService", "TurnAttachment", "TurnRequest", "TurnResult"]
