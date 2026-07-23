"""
Run execution for Quenda Runtime.

A Run represents a single execution of an agent within a session.
It bridges async Runtime with sync Kernel, and emits events for observability.

ADR-023: Runtime owns the tool phase loop using Kernel primitives.
ADR-027: Skill activation is handled within the Run, not as a separate phase.
"""

from __future__ import annotations

import asyncio
import base64
import time
from collections.abc import AsyncIterator, Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import uuid4

from quenda.kernel import Kernel, Message, Model, ModelResponse
from quenda.kernel.types import ImageContent, TextContent, ToolCall, ToolResult
from quenda.providers.errors import APIError, ToolCallDecodeError, UnsupportedFeatureError
from quenda.runtime.agent import AgentDefinition
from quenda.runtime.events import (
    AnyEvent,
    CompressionCompleted,
    CompressionStarted,
    ErrorOccurred,
    ModelResponded,
    RunCompleted,
    RunStarted,
    RunTerminated,
    RunInterrupted,
    ToolExecuted,
)
from quenda.runtime.permission import PermissionRequiredError
from quenda.runtime.session import SessionState
from quenda.runtime.state import RunState

if TYPE_CHECKING:
    from quenda.runtime.compression import CompressionDecision
    from quenda.runtime.compressor import Compressor
    from quenda.runtime.ports.compression import CompressionPolicy
    from quenda.runtime.ports.storage import Storage
    from quenda.runtime.termination import TerminationDecision
    from quenda.runtime.termination import TerminationPolicy
    from quenda.runtime.trace import TraceSink
    from quenda.runtime.tool_policy import ToolSelectionPolicy, ToolResultProcessingPolicy


@runtime_checkable
class SkillActivationHandler(Protocol):
    """
    Protocol for handling skill activation requests within a Run.

    ADR-027: When the model calls request_skill_activation tool, this handler
    is invoked to activate the skill and return the updated system prompt.
    """

    def __call__(self, skill_names: list[str]) -> str | None:
        """
        Activate skills and return the updated system prompt.

        Args:
            skill_names: List of skill names to activate.

        Returns:
            The updated system prompt with skill instructions, or None if
            no update is needed (e.g., skills already active or not found).
        """
        ...


class RunStatus(StrEnum):
    """Status of a Run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RunCounters:
    """Mutable execution counters for a run."""

    step_count: int = 0
    tool_round_count: int = 0
    error_count: int = 0
    consecutive_error_count: int = 0


@dataclass
class ToolPhaseOutcome:
    """Result of one runtime-owned tool phase."""

    tool_results: list[ToolResult] = field(default_factory=list)
    termination_reason: str | None = None


@dataclass
class Run:
    """
    A single execution of an agent.

    Runs are created from an Agent and SessionState, execute using Kernel primitives,
    and emit events for observability.

    ADR-023: Runtime owns the execution loop.
    ADR-028: Capability-based model routing.
    Kernel provides execution primitives (invoke_model, execute_tool).
    """

    id: str
    agent: AgentDefinition
    session: SessionState
    model: Model  # Default model (may be overridden by routing)
    status: RunStatus = RunStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    storage: Storage | None = None

    # Compression support (ADR-015): Host injects these
    compression_policy: CompressionPolicy | None = None
    compressor: Compressor | None = None

    # TraceSink support (ADR-016): Host injects this
    trace_sink: TraceSink | None = None

    # TerminationPolicy support (ADR-021): Host injects this
    termination_policy: TerminationPolicy | None = None

    # Tool policies (ADR-023): Host injects these
    tool_selection_policy: ToolSelectionPolicy | None = None
    tool_result_processing_policy: ToolResultProcessingPolicy | None = None

    # Skill activation handler (ADR-027): Host injects this
    skill_activation_handler: SkillActivationHandler | None = None

    # Model routing (ADR-028): Host injects these
    vision_model: Model | None = None
    capability_routing: bool = True

    _event_handlers: list[Callable[[AnyEvent], None]] = field(default_factory=list)
    _executor: ThreadPoolExecutor = field(default_factory=ThreadPoolExecutor)

    @classmethod
    def create(
        cls,
        agent: AgentDefinition,
        session: SessionState,
        model: Model,
        storage: Storage | None = None,
        trace_sink: TraceSink | None = None,
        termination_policy: TerminationPolicy | None = None,
        tool_selection_policy: ToolSelectionPolicy | None = None,
        tool_result_processing_policy: ToolResultProcessingPolicy | None = None,
        vision_model: Model | None = None,
        capability_routing: bool = True,
    ) -> Run:
        """
        Create a new Run.

        Args:
            agent: The agent definition.
            session: The session state to run in.
            model: The model to use.
            storage: Optional storage for persisting run state.
            trace_sink: Optional trace sink for recording events.
            termination_policy: Optional termination policy for run control.
            tool_selection_policy: Optional tool selection policy for gating.
            tool_result_processing_policy: Optional policy for shaping tool results.
            vision_model: Optional vision model for capability routing (ADR-028).
            capability_routing: Whether to enable capability-based routing (ADR-028).

        Returns:
            A new Run instance.
        """
        return cls(
            id=str(uuid4()),
            agent=agent,
            session=session,
            model=model,
            storage=storage,
            trace_sink=trace_sink,
            termination_policy=termination_policy,
            tool_selection_policy=tool_selection_policy,
            tool_result_processing_policy=tool_result_processing_policy,
            vision_model=vision_model,
            capability_routing=capability_routing,
        )

    def on_event(self, handler: Callable[[AnyEvent], None]) -> None:
        """
        Register an event handler.

        Args:
            handler: A function that receives events.
        """
        self._event_handlers.append(handler)

    def _emit(self, event: AnyEvent) -> None:
        """Emit an event to all registered handlers and trace sink."""
        # Replace run_id with this run's ID
        object.__setattr__(event, "run_id", self.id)

        # Notify event handlers
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                pass  # Don't let handler errors propagate

        # Record to trace sink if configured
        if self.trace_sink is not None:
            try:
                self.trace_sink.record(event)
            except Exception:
                pass  # Don't let trace sink errors propagate

    async def execute(self, user_message: str | Sequence[TextContent | ImageContent]) -> AsyncIterator[AnyEvent]:
        """
        Execute the run with a user message.

        ADR-023: Runtime owns the execution loop using Kernel primitives.

        Args:
            user_message: The user's message to process (text or multimodal).

        Yields:
            Events describing the execution progress in real-time.
        """
        from quenda.utils.interrupt import is_interrupted, clear_interrupt, InterruptReason

        self.status = RunStatus.RUNNING
        run_start_time = time.perf_counter()

        # Convert user_message to string for logging/storage
        user_message_str = user_message if isinstance(user_message, str) else "[multimodal message]"

        # Clear any previous interrupt signal
        clear_interrupt()

        # Emit run started
        started = RunStarted(
            agent_name=self.agent.name,
            session_id=self.session.id,
            user_message=user_message_str,
        )
        self._emit(started)
        yield started

        try:
            self._ensure_vision_supported(user_message)

            # Add user message to session
            self.session.add_user_message(user_message)
            self._save_session_checkpoint()
            active_message = self.session.messages[-1]

            # ADR-015: Check if compression is needed before execution
            compression_events = list(self._check_and_compress())
            for event in compression_events:
                yield event

            # Build messages with system prompt
            active_resource_start = self._active_resource_start(active_message)
            messages = self._build_messages(active_resource_start=active_resource_start)
            committed_count = len(messages)

            # Runtime-owned execution loop
            counters = RunCounters()
            final_content: str | None = None
            termination_requested = False
            termination_reason = ""
            iteration = 0
            max_iterations = 100  # Hard guard
            tool_call_decode_retry_used = False
            context_overflow_retry_used = False

            # Current resolved model (may change due to routing)
            current_model = self.model

            while iteration < max_iterations:
                iteration += 1

                # Check for interrupt
                if is_interrupted():
                    break

                # Tool calls and results can grow context substantially within a
                # single run, so enforce the budget before every subsequent call.
                if iteration > 1:
                    compression_events = list(self._check_and_compress())
                    for event in compression_events:
                        yield event
                    if any(
                        isinstance(event, CompressionCompleted)
                        and event.result.archived_message_count > 0
                        for event in compression_events
                    ):
                        messages = self._build_messages(
                            active_resource_start=active_resource_start
                        )
                        committed_count = len(messages)

                # ADR-028: Resolve model based on message capabilities
                resolved_model, routing_event = self._resolve_model_for_messages(messages)
                current_model = resolved_model
                if routing_event:
                    self._emit(routing_event)
                    yield routing_event

                # Create kernel with resolved model
                kernel = Kernel(current_model, self.agent.tools)

                try:
                    # Invoke model (async wrapper around sync primitive)
                    response = await asyncio.get_running_loop().run_in_executor(
                        self._executor,
                        kernel.invoke_model,
                        messages,
                        None,  # Use registered tools
                    )
                except ToolCallDecodeError as e:
                    if tool_call_decode_retry_used:
                        raise
                    tool_call_decode_retry_used = True
                    repair_message = self._tool_call_repair_message(e)
                    messages.append(repair_message)
                    self._commit_session_messages([repair_message])
                    continue
                except APIError as e:
                    if (
                        context_overflow_retry_used
                        or not self._is_context_overflow_error(e)
                    ):
                        raise
                    context_overflow_retry_used = True
                    compression_events = list(self._force_context_compression())
                    for event in compression_events:
                        yield event
                    if not any(
                        isinstance(event, CompressionCompleted)
                        and event.result.archived_message_count > 0
                        for event in compression_events
                    ):
                        raise
                    messages = self._build_messages(
                        active_resource_start=active_resource_start
                    )
                    committed_count = len(messages)
                    continue

                tool_call_decode_retry_used = False

                counters.step_count += 1

                # ADR-015: Accumulate token usage
                self._accumulate_usage(response)

                # Emit model response event
                model_event = ModelResponded(
                    content=response.content,
                    tool_calls=[tc.id for tc in response.tool_calls],  # Call IDs
                    tool_call_details=[
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in response.tool_calls
                    ],
                    # Backward compatible (deprecated)
                    tool_arguments=[tc.arguments for tc in response.tool_calls],
                    stop_reason=response.stop_reason,
                )
                self._emit(model_event)
                yield model_event

                if response.content:
                    final_content = response.content

                # Check termination policy after model step
                decision = self._termination_decision(
                    counters,
                    run_start_time,
                    last_step_type="model",
                    last_stop_reason=response.stop_reason,
                )
                if decision is not None and decision.should_stop:
                    termination_requested = True
                    termination_reason = decision.reason
                    break

                # Check if we should stop (natural completion)
                if response.stop_reason in ("end_turn", "max_tokens", "stop_sequence"):
                    # Add final assistant message if has content
                    if response.content:
                        messages.append(Message(role="assistant", content=response.content))
                    break

                # Tool phase: Runtime owns execution (ADR-023)
                if response.tool_calls:
                    tool_phase = ToolPhaseOutcome()
                    async for event in self._run_tool_phase(
                        kernel,
                        response,
                        counters,
                        run_start_time,
                        tool_phase,
                    ):
                        yield event
                    if tool_phase.termination_reason is not None:
                        termination_requested = True
                        termination_reason = tool_phase.termination_reason

                    tool_results = tool_phase.tool_results

                    # Runtime owns message writeback
                    # Add assistant message with tool calls (preserves original request)
                    assistant_tool_message = Message(role="assistant", content=response.tool_calls)
                    messages.append(assistant_tool_message)
                    # Add user message with tool results (in request order)
                    tool_result_message = Message(role="user", content=tool_results)
                    messages.append(tool_result_message)
                    self._commit_session_messages([
                        assistant_tool_message,
                        tool_result_message,
                    ])
                    committed_count = len(messages)

                    # ADR-027: Handle skill activation within the same Run
                    # Detect skill_activation results and update prompt for next step
                    if self.skill_activation_handler:
                        skill_names_to_activate = self._extract_skill_activation_requests(tool_results)
                        if skill_names_to_activate:
                            updated_prompt = self.skill_activation_handler(skill_names_to_activate)
                            if updated_prompt:
                                # Update the agent's system prompt for subsequent steps
                                object.__setattr__(self.agent, 'system_prompt', updated_prompt)
                                # Rebuild messages with the new prompt
                                messages[:] = self._build_messages(
                                    active_resource_start=active_resource_start
                                )
                                committed_count = len(messages)

                    resource_activation_messages = self._build_resource_activation_messages(tool_results)
                    if resource_activation_messages:
                        messages.extend(resource_activation_messages)
                        self._commit_session_messages(resource_activation_messages)
                        committed_count = len(messages)

                    # Check if interrupted during tool phase
                    if is_interrupted():
                        break

                    # Check if terminated during tool phase
                    if termination_requested:
                        break

                    # Continue to next iteration (model will respond to tool results)

            # Handle termination (policy-triggered stop)
            if termination_requested:
                # Update session with messages
                self._commit_session_messages(messages[committed_count:])

                terminated = RunTerminated(
                    reason=termination_reason,
                    steps_completed=counters.step_count,
                    final_content=final_content,
                    duration_ms=int((time.perf_counter() - run_start_time) * 1000),
                )
                self._emit(terminated)
                yield terminated

                self.status = RunStatus.FAILED

                if self.storage:
                    run_state = RunState(
                        id=self.id,
                        session_id=self.session.id,
                        agent_name=self.agent.name,
                        status="terminated",
                        user_message=user_message_str,
                        final_content=final_content,
                        step_count=counters.step_count,
                        created_at=self.created_at,
                        completed_at=datetime.now(),
                    )
                    self.storage.save_run(run_state)

                return

            # Handle interruption
            if is_interrupted():
                self._commit_session_messages(messages[committed_count:])

                interrupted = RunInterrupted(
                    reason="user_cancel",
                    steps_completed=counters.step_count,
                )
                self._emit(interrupted)
                yield interrupted

                self.status = RunStatus.FAILED

                if self.storage:
                    run_state = RunState(
                        id=self.id,
                        session_id=self.session.id,
                        agent_name=self.agent.name,
                        status="interrupted",
                        user_message=user_message_str,
                        final_content=final_content,
                        step_count=counters.step_count,
                        created_at=self.created_at,
                        completed_at=datetime.now(),
                    )
                    self.storage.save_run(run_state)

                return

            # Normal completion
            self._commit_session_messages(messages[committed_count:])

            completed_at = datetime.now()
            total_duration_ms = int((time.perf_counter() - run_start_time) * 1000)
            completed = RunCompleted(
                agent_name=self.agent.name,
                session_id=self.session.id,
                total_steps=counters.step_count,
                final_content=final_content,
                duration_ms=total_duration_ms,
            )
            self._emit(completed)
            yield completed

            self.status = RunStatus.COMPLETED

            if self.storage:
                run_state = RunState(
                    id=self.id,
                    session_id=self.session.id,
                    agent_name=self.agent.name,
                    status="completed",
                    user_message=user_message_str,
                    final_content=final_content,
                    step_count=counters.step_count,
                    created_at=self.created_at,
                    completed_at=completed_at,
                )
                self.storage.save_run(run_state)

        except Exception as e:
            self.status = RunStatus.FAILED

            self._save_session_checkpoint()

            error = ErrorOccurred(
                error_message=str(e),
                error_type=type(e).__name__,
            )
            self._emit(error)
            yield error

            if self.storage:
                run_state = RunState(
                    id=self.id,
                    session_id=self.session.id,
                    agent_name=self.agent.name,
                    status="failed",
                    user_message=user_message_str,
                    final_content=None,
                    step_count=0,
                    created_at=self.created_at,
                    completed_at=datetime.now(),
                )
                self.storage.save_run(run_state)

    def _extract_key_arguments(self, tool_name: str, arguments: dict) -> dict[str, object]:
        """
        Extract key arguments for display.

        If _summary is present, use that as the display.
        Otherwise, show tool name only.
        """
        summary = arguments.get("_summary")
        if summary and isinstance(summary, str):
            return {"_summary": summary}
        return {}

    def _commit_session_messages(self, messages: Sequence[Message]) -> None:
        """Append committed loop messages to session history and persist a checkpoint."""
        committed = False
        for message in messages:
            if message.role == "system":
                continue
            self.session.messages.append(message)
            committed = True

        if committed:
            self._save_session_checkpoint()

    def _save_session_checkpoint(self) -> None:
        """Persist the current session state when storage is configured."""
        if self.storage is None:
            return
        self.storage.save_session(self.session)

    def _tool_call_repair_message(self, error: ToolCallDecodeError) -> Message:
        """Build a compact model-facing repair prompt for invalid tool arguments."""
        tool_name = error.tool_name or "the requested tool"
        location = (
            f" at character {error.error_position}"
            if error.error_position is not None
            else ""
        )
        return Message(
            role="user",
            content=(
                "[Internal recovery]\n"
                f"Your previous response attempted to call `{tool_name}`, but its "
                f"arguments were not valid JSON{location}. The tool was not executed. "
                "Regenerate only the intended tool call with valid JSON arguments. "
                "Do not restart the task or repeat earlier successful tool calls."
            ),
        )

    def _termination_decision(
        self,
        counters: RunCounters,
        run_start_time: float,
        *,
        last_step_type: str,
        last_stop_reason: str | None,
    ) -> "TerminationDecision | None":
        """Evaluate the configured termination policy for the current run state."""
        if self.termination_policy is None:
            return None

        from quenda.runtime.termination import TerminationState

        elapsed_ms = int((time.perf_counter() - run_start_time) * 1000)
        state = TerminationState(
            step_count=counters.step_count,
            tool_round_count=counters.tool_round_count,
            elapsed_time_ms=elapsed_ms,
            total_input_tokens=self.session.usage.total_input_tokens,
            total_output_tokens=self.session.usage.total_output_tokens,
            total_tokens=self.session.usage.total_tokens,
            error_count=counters.error_count,
            consecutive_error_count=counters.consecutive_error_count,
            run_id=self.id,
            session_id=self.session.id,
            agent_name=self.agent.name,
            last_step_type=last_step_type,
            last_stop_reason=last_stop_reason,
        )
        return self.termination_policy.should_terminate(state)

    def _select_tool_calls(
        self,
        tool_calls: list[ToolCall],
        counters: RunCounters,
    ) -> tuple[list[ToolCall], list[tuple[ToolCall, str]]]:
        """Apply ToolSelectionPolicy and return approved and rejected calls."""
        if self.tool_selection_policy is None:
            return list(tool_calls), []

        from quenda.runtime.tool_policy import ToolSelectionRequest

        request = ToolSelectionRequest(
            tool_calls=tool_calls,
            available_tools=self.agent.tools,
            run_id=self.id,
            session_id=self.session.id,
            agent_name=self.agent.name,
            step_count=counters.step_count,
            tool_round_count=counters.tool_round_count,
        )
        decision = self.tool_selection_policy.select_tools(request)
        return list(decision.approved), [(r.call, r.reason) for r in decision.rejected]

    async def _run_tool_phase(
        self,
        kernel: Kernel,
        response: ModelResponse,
        counters: RunCounters,
        run_start_time: float,
        outcome: ToolPhaseOutcome,
    ) -> AsyncIterator[AnyEvent]:
        """Run one Runtime-owned tool phase and yield events as they happen."""
        from quenda.runtime.events import ToolPhaseStarted
        from quenda.utils.interrupt import is_interrupted

        counters.tool_round_count += 1

        approved_calls, rejected_calls = self._select_tool_calls(
            response.tool_calls,
            counters,
        )

        policy_name = (
            type(self.tool_selection_policy).__name__
            if self.tool_selection_policy
            else "AllowAllToolSelectionPolicy"
        )
        tool_phase_event = ToolPhaseStarted(
            requested_calls=[
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in response.tool_calls
            ],
            approved_calls=[tc.id for tc in approved_calls],
            rejected_calls=[
                {"id": rc[0].id, "name": rc[0].name, "reason": rc[1]}
                for rc in rejected_calls
            ],
            policy_name=policy_name,
        )
        self._emit(tool_phase_event)
        yield tool_phase_event

        approved_by_id = {call.id for call in approved_calls}
        rejection_by_id = {call.id: reason for call, reason in rejected_calls}
        tool_results_map: dict[str, ToolResult] = {}

        for call in response.tool_calls:
            if is_interrupted():
                break

            if call.id in approved_by_id:
                raw_result = await self._execute_tool_with_permission(
                    kernel,
                    call,
                    counters.step_count,
                    counters.error_count,
                    counters.consecutive_error_count,
                )

                counters.step_count += 1

                if raw_result.is_error:
                    counters.error_count += 1
                    counters.consecutive_error_count += 1
                else:
                    counters.consecutive_error_count = 0

                result = self._process_tool_result(raw_result)
                tool_results_map[call.id] = result

                tool_event = self._tool_executed_event(
                    call,
                    raw_result=raw_result,
                    result=result,
                )
                self._emit(tool_event)
                yield tool_event

                decision = self._termination_decision(
                    counters,
                    run_start_time,
                    last_step_type="tool",
                    last_stop_reason=response.stop_reason,
                )
                if decision is not None and decision.should_stop:
                    outcome.termination_reason = decision.reason
                    break
                continue

            rejection_reason = rejection_by_id.get(call.id)
            assert rejection_reason is not None
            counters.error_count += 1
            counters.consecutive_error_count += 1

            synthetic_result = self._denied_tool_result(call, rejection_reason)
            tool_results_map[call.id] = synthetic_result

            counters.step_count += 1
            tool_event = self._tool_denied_event(
                call,
                synthetic_result,
                rejection_reason,
            )
            self._emit(tool_event)
            yield tool_event

        outcome.tool_results = [
            tool_results_map[call.id]
            for call in response.tool_calls
            if call.id in tool_results_map
        ]

    def _process_tool_result(self, raw_result: ToolResult) -> ToolResult:
        """Apply ToolResultProcessingPolicy while preserving raw trace data elsewhere."""
        processed_content = raw_result.content
        processed_display_hint = raw_result.display_hint
        processed_change_preview = raw_result.change_preview
        processed_result_summary = raw_result.result_summary

        if self.tool_result_processing_policy is not None:
            from quenda.runtime.tool_policy import ToolResultEnvelope

            envelope = ToolResultEnvelope(
                call_id=raw_result.call_id,
                tool_name=raw_result.name,
                raw_content=raw_result.content,
                is_error=raw_result.is_error,
                duration_ms=raw_result.duration_ms,
                display_hint=raw_result.display_hint,
                change_preview=raw_result.change_preview,
                result_summary=raw_result.result_summary,
            )

            try:
                processed = self.tool_result_processing_policy.process_result(envelope)
                processed_content = processed.content
                processed_display_hint = processed.display_hint
                processed_change_preview = processed.change_preview
                processed_result_summary = processed.result_summary
            except Exception:
                pass

        return ToolResult(
            call_id=raw_result.call_id,
            name=raw_result.name,
            content=processed_content,
            is_error=raw_result.is_error,
            duration_ms=raw_result.duration_ms,
            display_hint=processed_display_hint,
            change_preview=processed_change_preview,
            result_summary=processed_result_summary,
            image_content=raw_result.image_content,
        )

    def _tool_executed_event(
        self,
        call: ToolCall,
        *,
        raw_result: ToolResult,
        result: ToolResult,
    ) -> ToolExecuted:
        """Build the event for an approved tool execution."""
        result_lines = result.content.count("\n") + 1 if result.content else 0
        return ToolExecuted(
            tool_name=result.name,
            arguments=self._extract_key_arguments(call.name, call.arguments),
            result=result.content,
            raw_result=raw_result.content,
            is_error=result.is_error,
            is_denied=False,
            denial_reason="",
            duration_ms=result.duration_ms,
            call_id=result.call_id,
            result_lines=result_lines,
            result_truncated=len(result.content) > 10000 if result.content else False,
            display_hint=result.display_hint,
            change_preview=result.change_preview,
            result_summary=result.result_summary,
        )

    def _denied_tool_result(self, call: ToolCall, reason: str) -> ToolResult:
        """Create the loop-visible result for a rejected tool call."""
        return ToolResult(
            call_id=call.id,
            name=call.name,
            content=f"Tool execution denied: {reason}",
            is_error=True,
        )

    def _tool_denied_event(
        self,
        call: ToolCall,
        result: ToolResult,
        reason: str,
    ) -> ToolExecuted:
        """Build the event for a rejected tool call."""
        return ToolExecuted(
            tool_name=call.name,
            arguments=self._extract_key_arguments(call.name, call.arguments),
            result=result.content,
            raw_result=result.content,
            is_error=True,
            is_denied=True,
            denial_reason=reason,
            duration_ms=0,
            call_id=call.id,
            result_lines=1,
            result_truncated=False,
        )

    def _extract_skill_activation_requests(self, tool_results: list[ToolResult]) -> list[str]:
        """
        Extract skill activation requests from tool results.

        ADR-027: Detect skill_activation results and return the skill names.

        Args:
            tool_results: List of tool execution results.

        Returns:
            List of skill names that were requested for activation.
        """
        skill_names: list[str] = []
        for result in tool_results:
            # Check if this is a skill activation result
            if result.name == "request_skill_activation":
                # Extract skill name from result_summary (format: "skill_activation:<name>")
                summary = result.result_summary
                if summary and summary.startswith("skill_activation:"):
                    skill_name = summary[len("skill_activation:"):].strip()
                    if skill_name:
                        skill_names.append(skill_name)
        return skill_names

    async def _execute_tool_with_permission(
        self,
        kernel: Kernel,
        call: ToolCall,
        step_count: int,
        error_count: int,
        consecutive_error_count: int,
    ) -> ToolResult:
        """
        Execute a tool.

        Permission is hard-denied at the runtime boundary.
        If a tool raises PermissionRequiredError, it is converted into
        a denied ToolResult immediately.

        Args:
            kernel: The kernel to execute the tool.
            call: The tool call to execute.
            step_count: Current step count (for logging).
            error_count: Current error count.
            consecutive_error_count: Current consecutive error count.

        Returns:
            ToolResult on success, or a denied ToolResult on permission error.
        """
        try:
            # Try executing the tool
            raw_result = await asyncio.get_running_loop().run_in_executor(
                self._executor,
                kernel.execute_tool,
                call,
            )
            return raw_result

        except PermissionRequiredError as e:
            request = e.request
            return ToolResult(
                call_id=call.id,
                name=call.name,
                content=f"Permission denied: {request.reason or 'Access not allowed'}",
                is_error=True,
            )

    def _build_messages(self, *, active_resource_start: int | None = None) -> list[Message]:
        """
        Build the message list with system prompt and summary blocks.

        Multimodal resources from previous turns are projected as lightweight
        placeholders so they remain visible in history without forcing every
        later turn through a vision-capable model.
        """
        messages = []

        if self.agent.system_prompt:
            messages.append(Message(role="system", content=self.agent.system_prompt))

        for block in self.session.summary_blocks:
            messages.append(Message(
                role="system",
                content=f"[历史摘要]\n{block.content}",
            ))

        resource_context = self._build_resource_context()
        if resource_context:
            messages.append(Message(role="system", content=resource_context))

        for index, message in enumerate(self.session.messages):
            if active_resource_start is not None and index < active_resource_start:
                messages.append(self._deactivate_message_resources(message))
            else:
                messages.append(message)

        return messages

    def _deactivate_message_resources(self, message: Message) -> Message:
        """Return a model-context copy with image payloads replaced by text placeholders."""
        content = message.content
        if not isinstance(content, list | tuple):
            return message

        deactivated: list[object] = []
        changed = False

        for block in content:
            if isinstance(block, ImageContent):
                deactivated.append(TextContent(text=self._image_placeholder(block)))
                changed = True
            elif isinstance(block, ToolResult) and block.image_content is not None:
                suffix = "\n\n[Image content from this historical tool result is not currently attached.]"
                deactivated.append(replace(
                    block,
                    content=f"{block.content}{suffix}",
                    image_content=None,
                ))
                changed = True
            else:
                deactivated.append(block)

        if not changed:
            return message

        return Message(role=message.role, content=deactivated)  # type: ignore[arg-type]

    def _image_placeholder(self, image: ImageContent) -> str:
        if image.image_url:
            return f"[Image resource: {image.image_url}. Raw content is not currently attached.]"
        if image.media_type:
            return f"[Image resource: {image.media_type}. Raw content is not currently attached.]"
        return "[Image resource. Raw content is not currently attached.]"

    def _active_resource_start(self, active_message: Message) -> int:
        for index, message in enumerate(self.session.messages):
            if message is active_message:
                return index
        return len(self.session.messages)

    def _build_resource_context(self) -> str:
        if not self.session.image_refs:
            return ""

        lines = [
            "[Session Resources]",
            "Historical resources are available but raw content is not attached by default.",
            "If raw visual details are needed, call activate_resource(resource_id, purpose).",
        ]
        for ref_id, ref in sorted(self.session.image_refs.items()):
            lines.append(
                f"- [Resource {ref_id}] type=image filename={ref.display_name()} "
                f"media_type={ref.source.media_type} source={ref.source.scheme} "
                f"{self._resource_location(ref.source.uri)} raw=not_attached"
            )
        return "\n".join(lines)

    def _resource_location(self, uri: str) -> str:
        if uri.startswith("file://"):
            return f"path={uri[7:]}"
        if uri.startswith(("http://", "https://")):
            return f"url={uri}"
        if uri.startswith("data:"):
            return "uri=data:<inline>"
        return f"uri={uri}"

    def _extract_resource_activation_requests(self, tool_results: list[ToolResult]) -> list[str]:
        resource_ids: list[str] = []
        for result in tool_results:
            if result.name != "activate_resource":
                continue
            summary = result.result_summary
            if summary and summary.startswith("resource_activation:"):
                resource_id = summary[len("resource_activation:"):].strip()
                if resource_id:
                    resource_ids.append(resource_id)
        return resource_ids

    def _build_resource_activation_messages(self, tool_results: list[ToolResult]) -> list[Message]:
        messages: list[Message] = []
        for resource_id in self._extract_resource_activation_requests(tool_results):
            image = self._resolve_image_resource(resource_id)
            if image is None:
                messages.append(Message(
                    role="user",
                    content=f"Resource activation failed: {resource_id} is not available.",
                ))
                continue
            messages.append(Message(
                role="user",
                content=[
                    TextContent(text=f"[Activated resource {resource_id}: raw image content attached.]"),
                    image,
                ],
            ))
        return messages

    def _resolve_image_resource(self, resource_id: str) -> ImageContent | None:
        ref = self.session.get_image_ref(resource_id)
        if ref is None:
            return None

        source = ref.source
        if source.scheme == "file":
            path = source.uri[7:] if source.uri.startswith("file://") else source.uri
            try:
                with open(path, "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
            except OSError:
                return None
            return ImageContent(media_type=source.media_type, data=data)

        if source.scheme in ("https", "http"):
            return ImageContent(image_url=source.uri)

        if source.scheme == "data":
            data = source.uri.split(",", 1)[1] if "," in source.uri else source.uri
            return ImageContent(media_type=source.media_type, data=data)

        return None

    def _resolve_model_for_messages(self, messages: list[Message]) -> tuple[Model, "ModelRouted | None"]:
        """
        Resolve the appropriate model for the given messages using capability routing.

        ADR-028: Capability-based model routing.

        Args:
            messages: The messages to analyze for capability requirements.

        Returns:
            Tuple of (resolved_model, optional ModelRouted event).
            The event is None if no routing was needed (default model used).
        """
        from quenda.runtime.routing import ModelRequirementResolver, ModelRouter, ModelRoutingResult
        from quenda.runtime.events import ModelRouted

        # If routing disabled or no vision model configured, use default
        if not self.capability_routing or self.vision_model is None:
            return self.model, None

        # Resolve requirements from messages
        resolver = ModelRequirementResolver()
        requirements = resolver.resolve(messages)

        # Route to appropriate model
        router = ModelRouter()
        try:
            result = router.route(
                requirements=requirements,
                default_model=self.model,
                capability_models={"vision": self.vision_model},
            )

            # If routing occurred, emit event
            if result.resolved_role != "default":
                event = ModelRouted(
                    requested_role=result.requested_role,
                    resolved_role=result.resolved_role,
                    provider=result.model.provider.id,
                    model_id=result.model.id,
                    required_capabilities=result.required_capabilities,
                    reason=result.reason,
                )
                return result.model, event

            return result.model, None

        except UnsupportedFeatureError:
            # Re-raise with more context
            raise

    def _ensure_vision_supported(self, user_message: str | Sequence[TextContent | ImageContent]) -> None:
        """
        Fail fast when image blocks are present but no vision model is available.

        This is a compatibility check before routing. The actual routing happens
        in _resolve_model_for_messages.

        ADR-028: This method is kept for backward compatibility but delegates
        to the routing system.
        """
        if isinstance(user_message, str):
            return

        has_image = any(isinstance(item, ImageContent) for item in user_message)
        if not has_image:
            return

        # Check if default model supports vision
        model_spec = getattr(self.model, "spec", None)
        supports_vision = bool(getattr(model_spec, "vision", False))
        if supports_vision:
            return

        # Check if vision model is configured
        if self.vision_model is not None:
            return

        # No vision support available
        model_id = getattr(self.model, "id", "current model")
        raise UnsupportedFeatureError(
            f"Model {model_id} does not support image input and no vision model is configured. "
            "Choose a vision-capable model or configure a vision model in config.yaml.",
            feature="vision",
        )

    def _check_and_compress(self) -> AsyncIterator[AnyEvent]:
        """
        Check if compression is needed and execute if necessary.
        """
        from quenda.runtime.compression import CompressionStats
        from quenda.runtime.token_estimator import TokenEstimator

        if not self.compression_policy:
            return

        messages = self._build_messages()
        estimator = TokenEstimator()
        estimated_tokens = (
            estimator.estimate_messages(messages)
            + estimator.estimate_tools(self.agent.tools)
        )

        stats = CompressionStats(
            estimated_input_tokens=estimated_tokens,
            message_count=len(messages),
            context_window=self.model.spec.context_window if self.model.spec else None,
            reserved_output_tokens=self.model.spec.max_output_tokens if self.model.spec else None,
            summary_token_count=sum(b.token_count for b in self.session.summary_blocks),
            hot_message_count=len(self.session.messages),
            session_id=self.session.id,
            agent_name=self.agent.name,
            mode=self.session.metadata.get("mode", "chat"),
            cumulative_usage=self.session.usage,
        )

        decision = self.compression_policy.should_compress(stats)

        if decision.compress:
            if decision.target_budget_tokens is not None:
                fixed_messages = [
                    message
                    for message in messages
                    if message.role == "system"
                ]
                fixed_tokens = (
                    estimator.estimate_messages(fixed_messages)
                    + estimator.estimate_tools(self.agent.tools)
                )
                decision = replace(
                    decision,
                    target_budget_tokens=max(
                        8_000,
                        decision.target_budget_tokens - fixed_tokens - 4_000,
                    ),
                )
            yield from self._compress(decision)

    def _force_context_compression(self) -> AsyncIterator[AnyEvent]:
        """Force one conservative compression after a provider overflow response."""
        from quenda.runtime.compression import CompressionDecision

        if not self.compressor:
            return

        yield from self._compress(CompressionDecision(
            compress=True,
            keep_last_n_messages=4,
            target_budget_tokens=None,
            archive_raw_messages=True,
            summarizer_id="default",
            reason="provider rejected request as input too long",
        ))

    def _compress(self, decision: CompressionDecision) -> AsyncIterator[AnyEvent]:
        """Execute and apply a compression decision."""
        from quenda.runtime.session import SummaryBlock

        if not self.compressor:
            return

        started = CompressionStarted(
            decision=decision,
            session_id=self.session.id,
        )
        self._emit(started)
        yield started

        result = self.compressor.compress(self.session, decision)

        replacement_blocks = [
            SummaryBlock(
                content=msg.content,
                message_range=(0, result.archived_message_count),
                created_at=datetime.now(),
                token_count=result.summary_token_count,
            )
            for msg in result.summary_messages
        ]
        if replacement_blocks:
            self.session.summary_blocks = replacement_blocks

        self.session.archive_refs.extend(result.archive_refs)
        if result.archived_message_count > 0:
            self.session.usage.compression_count += 1
            self.session.usage.last_compressed_at = datetime.now()
            self._save_session_checkpoint()

        completed = CompressionCompleted(
            result=result,
            session_id=self.session.id,
        )
        self._emit(completed)
        yield completed

    @staticmethod
    def _is_context_overflow_error(error: APIError) -> bool:
        """Recognize common provider messages for an oversized model request."""
        message = str(error).lower()
        return any(marker in message for marker in (
            "input too long",
            "context length",
            "context_length_exceeded",
            "maximum context",
            "token limit",
            "too many tokens",
        ))

    def _accumulate_usage(self, response: ModelResponse) -> None:
        """
        Accumulate token usage from model response.
        """
        if not response.usage:
            return

        self.session.usage.total_input_tokens += response.usage.input_tokens
        self.session.usage.total_output_tokens += response.usage.output_tokens
        self.session.usage.total_tokens += (
            response.usage.input_tokens + response.usage.output_tokens
        )

        if response.usage.cached_input_tokens:
            current = self.session.usage.total_cached_input_tokens or 0
            self.session.usage.total_cached_input_tokens = current + response.usage.cached_input_tokens

        if response.usage.reasoning_tokens:
            current = self.session.usage.total_reasoning_tokens or 0
            self.session.usage.total_reasoning_tokens = current + response.usage.reasoning_tokens

    async def execute_to_completion(self, user_message: str | Sequence[TextContent | ImageContent]) -> list[AnyEvent]:
        """
        Execute the run and return all events as a list.
        """
        return [event async for event in self.execute(user_message)]

    def execute_sync(self, user_message: str | Sequence[TextContent | ImageContent]) -> list[AnyEvent]:
        """
        Execute the run synchronously.
        """
        return asyncio.run(self.execute_to_completion(user_message))
