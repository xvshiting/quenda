"""
Run execution for Quenda Runtime.

A Run represents a single execution of an agent within a session.
It bridges async Runtime with sync Kernel, and emits events for observability.

ADR-023: Runtime owns the tool phase loop using Kernel primitives.
ADR-027: Skill activation is handled within the Run, not as a separate phase.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import uuid4

from quenda.kernel import Kernel, Message, Model, ModelResponse
from quenda.kernel.types import ToolCall, ToolResult
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
    ToolExecuted,
    RunInterrupted,
)
from quenda.runtime.session import SessionState

if TYPE_CHECKING:
    from quenda.host.compression_policy import CompressionPolicy
    from quenda.host.storage import Storage
    from quenda.runtime.compressor import Compressor
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
class Run:
    """
    A single execution of an agent.

    Runs are created from an Agent and SessionState, execute using Kernel primitives,
    and emit events for observability.

    ADR-023: Runtime owns the execution loop.
    Kernel provides execution primitives (invoke_model, execute_tool).
    """

    id: str
    agent: AgentDefinition
    session: SessionState
    model: Model
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

    async def execute(self, user_message: str) -> AsyncIterator[AnyEvent]:
        """
        Execute the run with a user message.

        ADR-023: Runtime owns the execution loop using Kernel primitives.

        Args:
            user_message: The user's message to process.

        Yields:
            Events describing the execution progress in real-time.
        """
        from quenda.utils.interrupt import is_interrupted, clear_interrupt, InterruptReason

        self.status = RunStatus.RUNNING
        run_start_time = time.perf_counter()

        # Clear any previous interrupt signal
        clear_interrupt()

        # Emit run started
        started = RunStarted(
            agent_name=self.agent.name,
            session_id=self.session.id,
            user_message=user_message,
        )
        self._emit(started)
        yield started

        try:
            # Add user message to session
            self.session.add_user_message(user_message)

            # ADR-015: Check if compression is needed before execution
            compression_events = list(self._check_and_compress())
            for event in compression_events:
                yield event

            # Build messages with system prompt
            messages = self._build_messages()
            original_count = len(messages)

            # Create kernel for execution primitives
            kernel = Kernel(self.model, self.agent.tools)

            # Runtime-owned execution loop
            step_count = 0
            tool_round_count = 0
            error_count = 0
            consecutive_error_count = 0
            final_content: str | None = None
            termination_requested = False
            termination_reason = ""
            iteration = 0
            max_iterations = 100  # Hard guard

            while iteration < max_iterations:
                iteration += 1

                # Check for interrupt
                if is_interrupted():
                    break

                # Invoke model (async wrapper around sync primitive)
                response = await asyncio.get_running_loop().run_in_executor(
                    self._executor,
                    kernel.invoke_model,
                    messages,
                    None,  # Use registered tools
                )

                step_count += 1

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
                if self.termination_policy:
                    elapsed_ms = int((time.perf_counter() - run_start_time) * 1000)
                    from quenda.runtime.termination import TerminationState

                    state = TerminationState(
                        step_count=step_count,
                        tool_round_count=tool_round_count,
                        elapsed_time_ms=elapsed_ms,
                        total_input_tokens=self.session.usage.total_input_tokens,
                        total_output_tokens=self.session.usage.total_output_tokens,
                        total_tokens=self.session.usage.total_tokens,
                        error_count=error_count,
                        consecutive_error_count=consecutive_error_count,
                        run_id=self.id,
                        session_id=self.session.id,
                        agent_name=self.agent.name,
                        last_step_type="model",
                        last_stop_reason=response.stop_reason,
                    )
                    decision = self.termination_policy.should_terminate(state)
                    if decision.should_stop:
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
                    tool_round_count += 1

                    # Phase 3: ToolSelectionPolicy integration
                    approved_calls: list[ToolCall] = []
                    rejected_calls: list[tuple[ToolCall, str]] = []  # (call, reason)

                    if self.tool_selection_policy is not None:
                        from quenda.runtime.tool_policy import (
                            ToolSelectionRequest,
                            RejectedToolCall,
                        )

                        request = ToolSelectionRequest(
                            tool_calls=response.tool_calls,
                            available_tools=self.agent.tools,
                            run_id=self.id,
                            session_id=self.session.id,
                            agent_name=self.agent.name,
                            step_count=step_count,
                            tool_round_count=tool_round_count,
                        )
                        decision = self.tool_selection_policy.select_tools(request)
                        approved_calls = list(decision.approved)
                        rejected_calls = [(r.call, r.reason) for r in decision.rejected]
                    else:
                        # Default: approve all
                        approved_calls = list(response.tool_calls)

                    # Emit ToolPhaseStarted event for trace (ADR-023 Phase 5)
                    from quenda.runtime.events import ToolPhaseStarted

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
                    yield tool_phase_event  # Also yield for observability

                    # Execute tool phase in request order
                    # Build a map of call_id -> ToolResult for ordering
                    tool_results_map: dict[str, ToolResult] = {}

                    for call in response.tool_calls:
                        # Check for interrupt
                        if is_interrupted():
                            break

                        # Check if this call was approved or rejected
                        is_approved = any(c.id == call.id for c in approved_calls)
                        rejection_reason: str | None = None

                        if not is_approved:
                            # Find rejection reason
                            for rejected_call, reason in rejected_calls:
                                if rejected_call.id == call.id:
                                    rejection_reason = reason
                                    break

                        if is_approved:
                            # Execute approved tool
                            raw_result = await asyncio.get_running_loop().run_in_executor(
                                self._executor,
                                kernel.execute_tool,
                                call,
                            )

                            step_count += 1

                            # Track errors
                            if raw_result.is_error:
                                error_count += 1
                                consecutive_error_count += 1
                            else:
                                consecutive_error_count = 0

                            # Phase 4: Apply ToolResultProcessingPolicy
                            processed_content = raw_result.content
                            processed_display_hint = raw_result.display_hint
                            processed_change_preview = raw_result.change_preview
                            processed_result_summary = raw_result.result_summary

                            if self.tool_result_processing_policy is not None:
                                from quenda.runtime.tool_policy import (
                                    ToolResultEnvelope,
                                )

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
                                    # Fallback to passthrough on processing failure
                                    pass

                            # Create processed ToolResult for message writeback
                            result = ToolResult(
                                call_id=raw_result.call_id,
                                name=raw_result.name,
                                content=processed_content,
                                is_error=raw_result.is_error,
                                duration_ms=raw_result.duration_ms,
                                display_hint=processed_display_hint,
                                change_preview=processed_change_preview,
                                result_summary=processed_result_summary,
                            )

                            tool_results_map[call.id] = result

                            # Emit tool executed event with both raw and processed result
                            key_args = self._extract_key_arguments(call.name, call.arguments)
                            result_lines = processed_content.count('\n') + 1 if processed_content else 0

                            tool_event = ToolExecuted(
                                tool_name=result.name,
                                arguments=key_args,
                                result=processed_content,
                                raw_result=raw_result.content,
                                is_error=result.is_error,
                                is_denied=False,  # This was an approved call
                                denial_reason="",
                                duration_ms=result.duration_ms,
                                call_id=result.call_id,
                                result_lines=result_lines,
                                result_truncated=len(processed_content) > 10000 if processed_content else False,
                                display_hint=result.display_hint,
                                change_preview=result.change_preview,
                                result_summary=result.result_summary,
                            )
                            self._emit(tool_event)
                            yield tool_event

                            # Check termination policy after tool step
                            if self.termination_policy:
                                elapsed_ms = int((time.perf_counter() - run_start_time) * 1000)
                                from quenda.runtime.termination import TerminationState

                                state = TerminationState(
                                    step_count=step_count,
                                    tool_round_count=tool_round_count,
                                    elapsed_time_ms=elapsed_ms,
                                    total_input_tokens=self.session.usage.total_input_tokens,
                                    total_output_tokens=self.session.usage.total_output_tokens,
                                    total_tokens=self.session.usage.total_tokens,
                                    error_count=error_count,
                                    consecutive_error_count=consecutive_error_count,
                                    run_id=self.id,
                                    session_id=self.session.id,
                                    agent_name=self.agent.name,
                                    last_step_type="tool",
                                    last_stop_reason=response.stop_reason,
                                )
                                decision = self.termination_policy.should_terminate(state)
                                if decision.should_stop:
                                    termination_requested = True
                                    termination_reason = decision.reason
                                    break
                        else:
                            # Handle rejected call - generate synthetic error result
                            assert rejection_reason is not None
                            error_count += 1
                            consecutive_error_count += 1

                            synthetic_result = ToolResult(
                                call_id=call.id,
                                name=call.name,
                                content=f"Tool execution denied: {rejection_reason}",
                                is_error=True,
                            )
                            tool_results_map[call.id] = synthetic_result

                            # Emit tool executed event for rejected call
                            step_count += 1
                            tool_event = ToolExecuted(
                                tool_name=call.name,
                                arguments=self._extract_key_arguments(call.name, call.arguments),
                                result=synthetic_result.content,
                                raw_result=synthetic_result.content,  # Same as result for rejected calls
                                is_error=True,
                                is_denied=True,  # This was a denied call
                                denial_reason=rejection_reason,
                                duration_ms=0,
                                call_id=call.id,
                                result_lines=1,
                                result_truncated=False,
                            )
                            self._emit(tool_event)
                            yield tool_event

                    # Build tool_results in original request order
                    tool_results = [
                        tool_results_map[call.id]
                        for call in response.tool_calls
                        if call.id in tool_results_map
                    ]

                    # Runtime owns message writeback
                    # Add assistant message with tool calls (preserves original request)
                    messages.append(Message(role="assistant", content=response.tool_calls))
                    # Add user message with tool results (in request order)
                    messages.append(Message(role="user", content=tool_results))

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
                                messages[:] = self._build_messages()

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
                for msg in messages[original_count:]:
                    if msg.role != "system":
                        self.session.messages.append(msg)

                terminated = RunTerminated(
                    reason=termination_reason,
                    steps_completed=step_count,
                    final_content=final_content,
                    duration_ms=int((time.perf_counter() - run_start_time) * 1000),
                )
                self._emit(terminated)
                yield terminated

                self.status = RunStatus.FAILED

                if self.storage:
                    from quenda.host.storage import RunState

                    run_state = RunState(
                        id=self.id,
                        session_id=self.session.id,
                        agent_name=self.agent.name,
                        status="terminated",
                        user_message=user_message,
                        final_content=final_content,
                        step_count=step_count,
                        created_at=self.created_at,
                        completed_at=datetime.now(),
                    )
                    self.storage.save_run(run_state)

                return

            # Handle interruption
            if is_interrupted():
                for msg in messages[original_count:]:
                    if msg.role != "system":
                        self.session.messages.append(msg)

                interrupted = RunInterrupted(
                    reason="user_cancel",
                    steps_completed=step_count,
                )
                self._emit(interrupted)
                yield interrupted

                self.status = RunStatus.FAILED

                if self.storage:
                    from quenda.host.storage import RunState

                    run_state = RunState(
                        id=self.id,
                        session_id=self.session.id,
                        agent_name=self.agent.name,
                        status="interrupted",
                        user_message=user_message,
                        final_content=final_content,
                        step_count=step_count,
                        created_at=self.created_at,
                        completed_at=datetime.now(),
                    )
                    self.storage.save_run(run_state)

                return

            # Normal completion
            for msg in messages[original_count:]:
                if msg.role != "system":
                    self.session.messages.append(msg)

            completed_at = datetime.now()
            total_duration_ms = int((time.perf_counter() - run_start_time) * 1000)
            completed = RunCompleted(
                agent_name=self.agent.name,
                session_id=self.session.id,
                total_steps=step_count,
                final_content=final_content,
                duration_ms=total_duration_ms,
            )
            self._emit(completed)
            yield completed

            self.status = RunStatus.COMPLETED

            if self.storage:
                from quenda.host.storage import RunState

                run_state = RunState(
                    id=self.id,
                    session_id=self.session.id,
                    agent_name=self.agent.name,
                    status="completed",
                    user_message=user_message,
                    final_content=final_content,
                    step_count=step_count,
                    created_at=self.created_at,
                    completed_at=completed_at,
                )
                self.storage.save_run(run_state)

        except Exception as e:
            self.status = RunStatus.FAILED

            error = ErrorOccurred(
                error_message=str(e),
                error_type=type(e).__name__,
            )
            self._emit(error)
            yield error

            if self.storage:
                from quenda.host.storage import RunState

                run_state = RunState(
                    id=self.id,
                    session_id=self.session.id,
                    agent_name=self.agent.name,
                    status="failed",
                    user_message=user_message,
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

    def _build_messages(self) -> list[Message]:
        """
        Build the message list with system prompt and summary blocks.
        """
        messages = []

        if self.agent.system_prompt:
            messages.append(Message(role="system", content=self.agent.system_prompt))

        for block in self.session.summary_blocks:
            messages.append(Message(
                role="system",
                content=f"[历史摘要]\n{block.content}",
            ))

        messages.extend(self.session.messages)

        return messages

    def _check_and_compress(self) -> AsyncIterator[AnyEvent]:
        """
        Check if compression is needed and execute if necessary.
        """
        from quenda.runtime.compression import CompressionStats
        from quenda.runtime.session import SummaryBlock
        from quenda.runtime.token_estimator import TokenEstimator

        if not self.compression_policy:
            return

        messages = self._build_messages()
        estimator = TokenEstimator()
        estimated_tokens = estimator.estimate_messages(messages)

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

        if decision.compress and self.compressor:
            started = CompressionStarted(
                decision=decision,
                session_id=self.session.id,
            )
            self._emit(started)
            yield started

            result = self.compressor.compress(self.session, decision)

            for msg in result.summary_messages:
                self.session.summary_blocks.append(SummaryBlock(
                    content=msg.content,
                    message_range=(0, result.archived_message_count),
                    created_at=datetime.now(),
                    token_count=result.summary_token_count,
                ))

            self.session.archive_refs.extend(result.archive_refs)
            self.session.usage.compression_count += 1
            self.session.usage.last_compressed_at = datetime.now()

            completed = CompressionCompleted(
                result=result,
                session_id=self.session.id,
            )
            self._emit(completed)
            yield completed

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

    async def execute_to_completion(self, user_message: str) -> list[AnyEvent]:
        """
        Execute the run and return all events as a list.
        """
        return [event async for event in self.execute(user_message)]

    def execute_sync(self, user_message: str) -> list[AnyEvent]:
        """
        Execute the run synchronously.
        """
        return asyncio.run(self.execute_to_completion(user_message))