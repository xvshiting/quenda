"""
Tests for Runtime layer.
"""

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from quenda.kernel import Message, Model, ModelResponse, Tool, ToolCall, ToolResult
from quenda.kernel.types import ImageContent, ImageRef, ImageSource, TextContent
from quenda.providers.errors import APIError, ToolCallDecodeError
from quenda.runtime.compression import (
    CompressionDecision,
    CompressionResult,
)
from quenda.runtime import (
    AgentConfig,
    ErrorOccurred,
    JsonlTraceSink,
    NullTraceSink,
    Run,
    RunCompleted,
    RunStarted,
    RunStatus,
    RunTerminated,
    SessionState,
    ToolExecuted,
    TraceSink,
)


class FakeTool:
    """A fake tool for testing."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo tool"

    @property
    def parameters(self) -> dict[str, object]:
        return {"type": "object", "properties": {"msg": {"type": "string"}}}

    def execute(self, **kwargs: object) -> ToolResult:
        return ToolResult(call_id="", name="echo", content=f"Echo: {kwargs.get('msg', '')}")


class FakeModel:
    """A fake model for testing."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = list(responses)

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        if self.responses:
            return self.responses.pop(0)
        return ModelResponse(content="Done", stop_reason="end_turn")


class FailingSecondModel:
    """A fake model that fails after returning a tool request."""

    def __init__(self) -> None:
        self.invocation_count = 0

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        self.invocation_count += 1
        if self.invocation_count == 1:
            return ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"msg": "hello"})],
                stop_reason="tool_use",
            )
        raise ValueError("invalid tool JSON")


class InvalidToolJsonThenToolModel:
    """A fake model that recovers after invalid tool-call JSON feedback."""

    def __init__(self) -> None:
        self.invocations: list[list[Message]] = []

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        self.invocations.append(list(messages))
        if len(self.invocations) == 1:
            raise ToolCallDecodeError(
                "bad json",
                tool_call_id="c1",
                tool_name="echo",
                raw_arguments='{"msg": "hello"',
                error_position=15,
            )
        if len(self.invocations) == 2:
            return ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"msg": "hello"})],
                stop_reason="tool_use",
            )
        return ModelResponse(content="Done", stop_reason="end_turn")


class RecordingStorage:
    """Minimal storage that records session checkpoints."""

    def __init__(self) -> None:
        self.saved_sessions: list[list[Message]] = []

    def save_session(self, state: SessionState) -> None:
        self.saved_sessions.append(list(state.messages))

    def save_run(self, run: object) -> None:
        pass


class CountingCompressionPolicy:
    """Compress on the second budget check, after one tool round."""

    def __init__(self) -> None:
        self.calls = 0

    def should_compress(self, stats: object) -> CompressionDecision:
        self.calls += 1
        return CompressionDecision(
            compress=self.calls == 2,
            keep_last_n_messages=2,
            target_budget_tokens=100,
            archive_raw_messages=False,
            summarizer_id="test",
            reason="test threshold",
        )


class RecordingCompressor:
    """Small deterministic compressor for runtime integration tests."""

    def __init__(self) -> None:
        self.calls = 0

    def compress(
        self,
        session: SessionState,
        decision: CompressionDecision,
    ) -> CompressionResult:
        self.calls += 1
        archived = max(0, len(session.messages) - decision.keep_last_n_messages)
        if archived:
            session.messages = session.messages[archived:]
        return CompressionResult(
            summary_messages=[Message(role="system", content="compressed")] if archived else [],
            archived_message_count=archived,
            archive_refs=[],
            summary_token_count=1 if archived else 0,
        )


class OverflowOnceModel:
    """Provider rejects the first request as oversized, then accepts retry."""

    def __init__(self) -> None:
        self.invocation_count = 0
        self.spec = SimpleNamespace(
            vision=False,
            context_window=202_752,
            max_output_tokens=None,
        )

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        self.invocation_count += 1
        if self.invocation_count == 1:
            raise APIError("Input too long: token limit is 202752")
        return ModelResponse(content="Recovered", stop_reason="end_turn")


class CapturingModel:
    """A fake model that records the messages it receives."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = list(responses)
        self.invocations: list[list[Message]] = []
        self.spec = SimpleNamespace(vision=True, context_window=None, max_output_tokens=None)

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        self.invocations.append(list(messages))
        if self.responses:
            return self.responses.pop(0)
        return ModelResponse(content="Done", stop_reason="end_turn")


class RoutingCaptureModel:
    """A fake model with provider metadata for capability routing tests."""

    def __init__(self, *, vision: bool, responses: list[ModelResponse] | None = None) -> None:
        self.responses = list(responses or [])
        self.invocations: list[list[Message]] = []
        self.spec = SimpleNamespace(vision=vision, context_window=None, max_output_tokens=None)
        self.provider = SimpleNamespace(id="fake")
        self.id = "vision" if vision else "default"

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        self.invocations.append(list(messages))
        if self.responses:
            return self.responses.pop(0)
        return ModelResponse(content=self.id, stop_reason="end_turn")


class TestSessionState:
    """Tests for SessionState."""

    def test_session_create(self) -> None:
        """Test creating a session state."""
        session = SessionState.create("test-agent")
        assert session.agent_name == "test-agent"
        assert session.id  # Should have an ID
        assert len(session) == 0

    def test_session_create_with_id(self) -> None:
        """Test creating a session state with custom ID."""
        session = SessionState.create("test-agent", session_id="custom-id")
        assert session.id == "custom-id"

    def test_session_add_messages(self) -> None:
        """Test adding messages to session."""
        session = SessionState.create("test-agent")
        session.add_user_message("Hello")

        assert len(session) == 1
        assert session.messages[0].role == "user"

    def test_session_clear(self) -> None:
        """Test clearing session."""
        session = SessionState.create("test-agent")
        session.add_user_message("Hello")
        session.clear()
        assert len(session) == 0


class TestSummarizerCompressor:
    """Tests for token-budgeted history compaction."""

    def test_compression_respects_hot_history_budget_and_merges_summary(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from datetime import datetime

        from quenda.runtime.compressor import SummarizerCompressor
        from quenda.runtime.session import SummaryBlock
        from quenda.runtime.token_estimator import TokenEstimator

        session = SessionState.create("test")
        session.summary_blocks.append(SummaryBlock(
            content="prior durable fact",
            message_range=(0, 4),
            created_at=datetime.now(),
            token_count=5,
        ))
        for index in range(20):
            session.add_user_message(f"message {index}: " + ("x" * 1_000))

        compressor = SummarizerCompressor(model=FakeModel([]))  # type: ignore[arg-type]
        summarized: list[Message] = []

        def fake_summarize(messages: list[Message]) -> str:
            summarized.extend(messages)
            return "merged summary"

        monkeypatch.setattr(compressor, "_summarize", fake_summarize)
        result = compressor.compress(session, CompressionDecision(
            compress=True,
            keep_last_n_messages=10,
            target_budget_tokens=1_500,
            archive_raw_messages=False,
            summarizer_id="test",
            reason="budget",
        ))

        assert result.archived_message_count > 10
        assert TokenEstimator().estimate_messages(session.messages) <= 1_500
        assert any(
            isinstance(message.content, str)
            and "prior durable fact" in message.content
            for message in summarized
        )


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_agent_config_basic(self) -> None:
        """Test basic agent config."""
        tool = FakeTool()
        agent = AgentConfig(
            name="test",
            system_prompt="You are helpful.",
            tools=[tool],
        )

        assert agent.name == "test"
        assert agent.system_prompt == "You are helpful."
        assert len(agent.tools) == 1

    def test_agent_config_no_system_prompt(self) -> None:
        """Test agent config without system prompt."""
        agent = AgentConfig(name="simple")
        assert agent.system_prompt is None
        assert agent.tools == []


class TestRun:
    """Tests for Run."""

    @pytest.mark.asyncio
    async def test_run_simple(self) -> None:
        """Test a simple run."""
        tool = FakeTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(content="Hello!", stop_reason="end_turn"),
        ])

        run = Run.create(agent, session, model)
        events = await run.execute_to_completion("Hi")

        # Should have started and completed
        assert any(isinstance(e, RunStarted) for e in events)
        assert any(isinstance(e, RunCompleted) for e in events)

    @pytest.mark.asyncio
    async def test_run_with_tool_call(self) -> None:
        """Test run with tool call."""
        tool = FakeTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"msg": "hello"})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        run = Run.create(agent, session, model)
        events = await run.execute_to_completion("Say hello")

        # Should have tool executed event
        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 1
        assert tool_events[0].tool_name == "echo"
        assert "Echo:" in tool_events[0].result

    @pytest.mark.asyncio
    async def test_run_rechecks_compression_after_tool_round(self) -> None:
        """Context budget is rechecked before the next model invocation."""
        from datetime import datetime

        from quenda.runtime.session import SummaryBlock

        agent = AgentConfig(name="test", tools=[FakeTool()])
        session = SessionState.create("test")
        session.summary_blocks.append(SummaryBlock(
            content="old summary",
            message_range=(0, 5),
            created_at=datetime.now(),
            token_count=10,
        ))
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"msg": "hello"})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])
        model.spec = SimpleNamespace(  # type: ignore[attr-defined]
            vision=False,
            context_window=202_752,
            max_output_tokens=None,
        )
        policy = CountingCompressionPolicy()
        compressor = RecordingCompressor()

        run = Run.create(agent, session, model)
        run.compression_policy = policy
        run.compressor = compressor
        events = await run.execute_to_completion("Say hello")

        assert any(event.type == "compression_completed" for event in events)
        assert policy.calls >= 2
        assert compressor.calls == 1
        assert len(session.summary_blocks) == 1
        assert session.summary_blocks[0].content == "compressed"
        assert any(isinstance(event, RunCompleted) for event in events)

    @pytest.mark.asyncio
    async def test_run_compresses_and_retries_context_overflow_once(self) -> None:
        """A provider overflow gets one forced compression retry."""
        agent = AgentConfig(name="test")
        session = SessionState.create("test")
        for index in range(8):
            session.add_user_message(f"old message {index}")
        model = OverflowOnceModel()
        compressor = RecordingCompressor()

        run = Run.create(agent, session, model)
        run.compressor = compressor
        events = await run.execute_to_completion("current request")

        assert model.invocation_count == 2
        assert compressor.calls == 1
        assert any(event.type == "compression_completed" for event in events)
        assert any(isinstance(event, RunCompleted) for event in events)
        assert not any(isinstance(event, ErrorOccurred) for event in events)

    @pytest.mark.asyncio
    async def test_run_with_system_prompt(self) -> None:
        """Test run with system prompt."""
        agent = AgentConfig(
            name="test",
            system_prompt="You are a helpful assistant.",
        )
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(content="OK", stop_reason="end_turn"),
        ])

        run = Run.create(agent, session, model)
        events = await run.execute_to_completion("Hi")

        # Check that run completed
        completed = [e for e in events if isinstance(e, RunCompleted)]
        assert len(completed) == 1

    @pytest.mark.asyncio
    async def test_run_kernel_exception_reports_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that kernel failures are surfaced instead of hanging."""
        agent = AgentConfig(name="test")
        session = SessionState.create("test")
        model = FakeModel([])

        run = Run.create(agent, session, model)

        def fake_invoke_model(self, messages, tools=None):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

        monkeypatch.setattr("quenda.runtime.run.Kernel.invoke_model", fake_invoke_model)

        events = await run.execute_to_completion("Hi")

        assert any(isinstance(e, ErrorOccurred) for e in events)
        assert run.status == RunStatus.FAILED
        assert not any(isinstance(e, RunCompleted) for e in events)

    @pytest.mark.asyncio
    async def test_run_checkpoints_tool_results_before_later_model_failure(self) -> None:
        """Tool side effects/results should survive a later model failure."""
        tool = FakeTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FailingSecondModel()
        storage = RecordingStorage()

        run = Run.create(agent, session, model, storage=storage)  # type: ignore[arg-type]
        events = await run.execute_to_completion("Say hello")

        assert any(isinstance(e, ToolExecuted) for e in events)
        assert any(isinstance(e, ErrorOccurred) for e in events)
        assert run.status == RunStatus.FAILED

        assert len(session.messages) == 3
        assert session.messages[0].role == "user"
        assert session.messages[1].role == "assistant"
        assert session.messages[1].content[0].name == "echo"  # type: ignore[index,union-attr]
        assert session.messages[2].role == "user"
        assert session.messages[2].content[0].content == "Echo: hello"  # type: ignore[index,union-attr]

        checkpoint_lengths = [len(messages) for messages in storage.saved_sessions]
        assert 1 in checkpoint_lengths
        assert 3 in checkpoint_lengths

    @pytest.mark.asyncio
    async def test_run_repairs_invalid_tool_call_json_once(self) -> None:
        """Invalid tool-call JSON should be repaired within the same run."""
        tool = FakeTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = InvalidToolJsonThenToolModel()

        run = Run.create(agent, session, model)
        events = await run.execute_to_completion("Say hello")

        assert any(isinstance(e, ToolExecuted) for e in events)
        assert any(isinstance(e, RunCompleted) for e in events)
        assert not any(isinstance(e, ErrorOccurred) for e in events)

        assert len(model.invocations) == 3
        repair_messages = [
            message for message in model.invocations[1]
            if isinstance(message.content, str) and "[Internal recovery]" in message.content
        ]
        assert repair_messages
        assert "echo" in repair_messages[0].content
        assert "valid JSON arguments" in repair_messages[0].content

    @pytest.mark.asyncio
    async def test_run_updates_session(self) -> None:
        """Test that run updates session."""
        agent = AgentConfig(name="test")
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(content="Hello!", stop_reason="end_turn"),
        ])

        run = Run.create(agent, session, model)
        await run.execute_to_completion("Hi")

        # Session should have the user message
        assert len(session) >= 1
        assert session.messages[0].role == "user"

    def test_run_sync(self) -> None:
        """Test synchronous run."""
        agent = AgentConfig(name="test")
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(content="Done", stop_reason="end_turn"),
        ])

        run = Run.create(agent, session, model)
        events = run.execute_sync("Hi")

        assert any(isinstance(e, RunCompleted) for e in events)


class TestTraceSink:
    """Tests for TraceSink."""

    def test_null_trace_sink(self) -> None:
        """Test NullTraceSink does nothing."""
        sink = NullTraceSink()
        event = RunStarted(agent_name="test", session_id="s1", user_message="hello")
        sink.record(event)  # Should not raise

    def test_jsonl_trace_sink(self) -> None:
        """Test JsonlTraceSink writes to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "trace.jsonl"
            sink = JsonlTraceSink(path)

            event = RunStarted(agent_name="test", session_id="s1", user_message="hello")
            sink.record(event)

            # Verify file was created
            assert path.exists()

            # Verify content
            content = path.read_text()
            assert "run_started" in content
            assert "test" in content

    def test_jsonl_trace_sink_creates_parent_dirs(self) -> None:
        """Test JsonlTraceSink creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "trace.jsonl"
            sink = JsonlTraceSink(path)

            event = RunStarted(agent_name="test", session_id="s1", user_message="hello")
            sink.record(event)

            assert path.exists()

    def test_trace_sink_integration_with_run(self) -> None:
        """Test TraceSink integration with Run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "trace.jsonl"
            sink = JsonlTraceSink(path)

            agent = AgentConfig(name="test")
            session = SessionState.create("test")
            model = FakeModel([
                ModelResponse(content="Done", stop_reason="end_turn"),
            ])

            run = Run.create(agent, session, model, trace_sink=sink)
            assert run.trace_sink is sink

            # Emit an event
            event = RunStarted(agent_name="test", session_id="s1", user_message="hello")
            run._emit(event)

            # Verify trace was written
            content = path.read_text()
            assert "run_started" in content

    @pytest.mark.asyncio
    async def test_trace_sink_records_run_events(self) -> None:
        """Test TraceSink records all events during run execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "trace.jsonl"
            sink = JsonlTraceSink(path)

            agent = AgentConfig(name="test")
            session = SessionState.create("test")
            model = FakeModel([
                ModelResponse(content="Done", stop_reason="end_turn"),
            ])

            run = Run.create(agent, session, model, trace_sink=sink)
            await run.execute_to_completion("Hi")

            # Verify multiple events were recorded
            content = path.read_text()
            lines = content.strip().split("\n")

            # Should have at least RunStarted and RunCompleted
            assert len(lines) >= 2
            assert any("run_started" in line for line in lines)
            assert any("run_completed" in line for line in lines)

    def test_run_without_trace_sink(self) -> None:
        """Test Run works without trace_sink."""
        agent = AgentConfig(name="test")
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(content="Done", stop_reason="end_turn"),
        ])

        run = Run.create(agent, session, model)
        assert run.trace_sink is None

        # Emit should not raise
        event = RunStarted(agent_name="test", session_id="s1", user_message="hello")
        run._emit(event)


class TestTerminationPolicy:
    """Tests for TerminationPolicy."""

    def test_never_terminate_policy(self) -> None:
        """Test NeverTerminatePolicy never stops."""
        from quenda.runtime.termination import NeverTerminatePolicy, TerminationState

        policy = NeverTerminatePolicy()
        state = TerminationState(
            step_count=100,
            tool_round_count=50,
            elapsed_time_ms=60000,
            total_input_tokens=10000,
            total_output_tokens=5000,
            total_tokens=15000,
            error_count=0,
            consecutive_error_count=0,
            run_id="test",
            session_id="s1",
            agent_name="test",
        )
        decision = policy.should_terminate(state)
        assert decision.should_stop is False

    def test_max_steps_policy(self) -> None:
        """Test MaxStepsPolicy stops after limit."""
        from quenda.runtime.termination import MaxStepsPolicy, TerminationState

        policy = MaxStepsPolicy(max_steps=10)

        # Below limit
        state_below = TerminationState(
            step_count=5,
            tool_round_count=2,
            elapsed_time_ms=1000,
            total_input_tokens=1000,
            total_output_tokens=500,
            total_tokens=1500,
            error_count=0,
            consecutive_error_count=0,
            run_id="test",
            session_id="s1",
            agent_name="test",
        )
        decision = policy.should_terminate(state_below)
        assert decision.should_stop is False

        # At limit
        state_at = TerminationState(
            step_count=10,
            tool_round_count=5,
            elapsed_time_ms=5000,
            total_input_tokens=5000,
            total_output_tokens=2500,
            total_tokens=7500,
            error_count=0,
            consecutive_error_count=0,
            run_id="test",
            session_id="s1",
            agent_name="test",
        )
        decision = policy.should_terminate(state_at)
        assert decision.should_stop is True
        assert "max_steps" in decision.reason

    def test_composite_policy(self) -> None:
        """Test CompositeTerminationPolicy combines policies."""
        from quenda.runtime.termination import (
            CompositeTerminationPolicy,
            MaxStepsPolicy,
            NeverTerminatePolicy,
            TerminationState,
        )

        policy = CompositeTerminationPolicy([
            MaxStepsPolicy(max_steps=10),
            NeverTerminatePolicy(),
        ])

        # First policy wins
        state = TerminationState(
            step_count=15,
            tool_round_count=7,
            elapsed_time_ms=10000,
            total_input_tokens=10000,
            total_output_tokens=5000,
            total_tokens=15000,
            error_count=0,
            consecutive_error_count=0,
            run_id="test",
            session_id="s1",
            agent_name="test",
        )
        decision = policy.should_terminate(state)
        assert decision.should_stop is True
        assert "max_steps" in decision.reason

    def test_run_accepts_termination_policy(self) -> None:
        """Test Run.create accepts termination_policy."""
        from quenda.runtime.termination import MaxStepsPolicy

        agent = AgentConfig(name="test")
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(content="Done", stop_reason="end_turn"),
        ])

        policy = MaxStepsPolicy(max_steps=10)
        run = Run.create(agent, session, model, termination_policy=policy)
        assert run.termination_policy is policy

    @pytest.mark.asyncio
    async def test_run_terminates_with_policy(self) -> None:
        """Test Run terminates when policy triggers."""
        from quenda.runtime.termination import MaxStepsPolicy

        tool = FakeTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"msg": "hello"})],
                stop_reason="tool_use",
            ),
            ModelResponse(
                tool_calls=[ToolCall(id="c2", name="echo", arguments={"msg": "world"})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        # Stop after 3 steps (1 model + 1 tool + 1 model = 3 steps)
        policy = MaxStepsPolicy(max_steps=3)
        run = Run.create(agent, session, model, termination_policy=policy)
        events = await run.execute_to_completion("Test")

        # Should have RunTerminated, not RunCompleted
        terminated = [e for e in events if isinstance(e, RunTerminated)]
        completed = [e for e in events if isinstance(e, RunCompleted)]

        assert len(terminated) == 1
        assert len(completed) == 0
        assert "max_steps" in terminated[0].reason
        assert terminated[0].steps_completed == 3

    def test_run_without_termination_policy(self) -> None:
        """Test Run works without termination_policy."""
        agent = AgentConfig(name="test")
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(content="Done", stop_reason="end_turn"),
        ])

        run = Run.create(agent, session, model)
        assert run.termination_policy is None


class TestToolSelectionPolicy:
    """Tests for ToolSelectionPolicy integration."""

    @pytest.mark.asyncio
    async def test_run_with_allow_all_policy(self) -> None:
        """Test AllowAllToolSelectionPolicy allows all tool calls."""
        from quenda.runtime.tool_policy import AllowAllToolSelectionPolicy

        tool = FakeTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"msg": "hello"})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        policy = AllowAllToolSelectionPolicy()
        run = Run.create(agent, session, model, tool_selection_policy=policy)
        events = await run.execute_to_completion("Test")

        # Tool should have been executed
        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 1
        assert tool_events[0].tool_name == "echo"

    @pytest.mark.asyncio
    async def test_run_with_denylist_policy(self) -> None:
        """Test DenylistToolSelectionPolicy blocks denied tools."""
        from quenda.runtime.tool_policy import DenylistToolSelectionPolicy

        tool = FakeTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"msg": "hello"})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        policy = DenylistToolSelectionPolicy(denied={"echo"})
        run = Run.create(agent, session, model, tool_selection_policy=policy)
        events = await run.execute_to_completion("Test")

        # Tool should NOT have been executed
        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 1
        assert tool_events[0].tool_name == "echo"
        assert "denylist" in tool_events[0].result
        assert tool_events[0].is_error

    @pytest.mark.asyncio
    async def test_run_with_partial_approval(self) -> None:
        """Test partial approval: some approved, some rejected."""
        from quenda.runtime.tool_policy import DenylistToolSelectionPolicy

        class NamedTool:
            """A tool with a configurable name."""
            def __init__(self, name: str) -> None:
                self._name = name

            @property
            def name(self) -> str:
                return self._name

            @property
            def description(self) -> str:
                return f"Tool {self._name}"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object"}

            def execute(self, **kwargs: object) -> ToolResult:
                return ToolResult(call_id="", name=self._name, content=f"{self._name} executed")

        tool1 = NamedTool("tool1")
        tool2 = NamedTool("tool2")
        agent = AgentConfig(name="test", tools=[tool1, tool2])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[
                    ToolCall(id="c1", name="tool1", arguments={}),
                    ToolCall(id="c2", name="tool2", arguments={}),
                ],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        policy = DenylistToolSelectionPolicy(denied={"tool2"})
        run = Run.create(agent, session, model, tool_selection_policy=policy)
        events = await run.execute_to_completion("Test")

        # Should have 2 tool events
        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 2

        # tool1 should have succeeded
        tool1_event = next(e for e in tool_events if e.tool_name == "tool1")
        assert not tool1_event.is_error
        assert "executed" in tool1_event.result

        # tool2 should have been rejected
        tool2_event = next(e for e in tool_events if e.tool_name == "tool2")
        assert tool2_event.is_error
        assert "denylist" in tool2_event.result

    @pytest.mark.asyncio
    async def test_run_preserves_tool_order(self) -> None:
        """Test tool results are in original request order."""
        from quenda.runtime.tool_policy import DenylistToolSelectionPolicy

        class NamedTool:
            """A tool with a configurable name."""
            def __init__(self, name: str) -> None:
                self._name = name

            @property
            def name(self) -> str:
                return self._name

            @property
            def description(self) -> str:
                return f"Tool {self._name}"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object"}

            def execute(self, **kwargs: object) -> ToolResult:
                return ToolResult(call_id="", name=self._name, content=f"{self._name} result")

        tool1 = NamedTool("tool1")
        tool2 = NamedTool("tool2")
        tool3 = NamedTool("tool3")
        agent = AgentConfig(name="test", tools=[tool1, tool2, tool3])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[
                    ToolCall(id="c1", name="tool1", arguments={}),
                    ToolCall(id="c2", name="tool2", arguments={}),
                    ToolCall(id="c3", name="tool3", arguments={}),
                ],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        # Reject tool2, approve tool1 and tool3
        policy = DenylistToolSelectionPolicy(denied={"tool2"})
        run = Run.create(agent, session, model, tool_selection_policy=policy)
        events = await run.execute_to_completion("Test")

        # Events should be in order: tool1, tool2 (rejected), tool3
        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 3
        assert tool_events[0].tool_name == "tool1"
        assert tool_events[1].tool_name == "tool2"
        assert tool_events[2].tool_name == "tool3"

    @pytest.mark.asyncio
    async def test_run_without_tool_selection_policy(self) -> None:
        """Test Run works without tool_selection_policy (default behavior)."""
        tool = FakeTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"msg": "hello"})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        run = Run.create(agent, session, model)
        assert run.tool_selection_policy is None

        events = await run.execute_to_completion("Test")

        # Tool should have been executed (default allow-all behavior)
        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 1


class TestToolResultProcessingPolicy:
    """Tests for ToolResultProcessingPolicy integration."""

    @pytest.mark.asyncio
    async def test_run_with_passthrough_policy(self) -> None:
        """Test PassthroughToolResultProcessingPolicy leaves result unchanged."""
        from quenda.runtime.tool_policy import PassthroughToolResultProcessingPolicy

        class VerboseTool:
            """A tool that returns a long result."""
            @property
            def name(self) -> str:
                return "verbose"

            @property
            def description(self) -> str:
                return "Verbose tool"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object"}

            def execute(self, **kwargs: object) -> ToolResult:
                return ToolResult(call_id="", name="verbose", content="This is a long result that should not be truncated")

        tool = VerboseTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="verbose", arguments={})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        policy = PassthroughToolResultProcessingPolicy()
        run = Run.create(agent, session, model, tool_result_processing_policy=policy)
        events = await run.execute_to_completion("Test")

        # Tool should have been executed with unchanged result
        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 1
        assert tool_events[0].result == "This is a long result that should not be truncated"
        assert tool_events[0].raw_result == "This is a long result that should not be truncated"

    @pytest.mark.asyncio
    async def test_run_with_truncating_policy(self) -> None:
        """Test TruncatingToolResultProcessingPolicy truncates long results."""
        from quenda.runtime.tool_policy import TruncatingToolResultProcessingPolicy

        class VerboseTool:
            """A tool that returns a very long result."""
            @property
            def name(self) -> str:
                return "verbose"

            @property
            def description(self) -> str:
                return "Verbose tool"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object"}

            def execute(self, **kwargs: object) -> ToolResult:
                # Create a 10000 character result
                return ToolResult(call_id="", name="verbose", content="X" * 10000)

        tool = VerboseTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="verbose", arguments={})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        policy = TruncatingToolResultProcessingPolicy(max_chars=100, suffix="...[truncated]")
        run = Run.create(agent, session, model, tool_result_processing_policy=policy)
        events = await run.execute_to_completion("Test")

        # Tool result should be truncated
        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 1
        assert len(tool_events[0].result) < 200  # Truncated
        assert "...[truncated]" in tool_events[0].result
        # Raw result should be unchanged
        assert len(tool_events[0].raw_result) == 10000

    def test_context_safe_policy_preserves_head_errors_and_tail(self) -> None:
        """Bounded tool views retain the regions most useful for diagnosis."""
        from quenda.runtime.tool_policy import (
            ContextSafeToolResultProcessingPolicy,
            ToolResultEnvelope,
        )

        raw = (
            "HEAD: command metadata\n"
            + ("ordinary output\n" * 1_000)
            + "ERROR: important failure detail\n"
            + ("more ordinary output\n" * 1_000)
            + "TAIL: final exit information"
        )
        policy = ContextSafeToolResultProcessingPolicy(max_chars=4_000)
        processed = policy.process_result(ToolResultEnvelope(
            call_id="c1",
            tool_name="shell",
            raw_content=raw,
            is_error=True,
            duration_ms=1,
        ))

        assert len(processed.content) <= 4_000
        assert "HEAD: command metadata" in processed.content
        assert "ERROR: important failure detail" in processed.content
        assert "TAIL: final exit information" in processed.content
        assert "raw output is preserved" in processed.content

    @pytest.mark.asyncio
    async def test_run_with_line_limited_policy(self) -> None:
        """Test LineLimitedToolResultProcessingPolicy limits lines."""
        from quenda.runtime.tool_policy import LineLimitedToolResultProcessingPolicy

        class MultiLineTool:
            """A tool that returns many lines."""
            @property
            def name(self) -> str:
                return "multiline"

            @property
            def description(self) -> str:
                return "Multi-line tool"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object"}

            def execute(self, **kwargs: object) -> ToolResult:
                return ToolResult(call_id="", name="multiline", content="\n".join(f"Line {i}" for i in range(100)))

        tool = MultiLineTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="multiline", arguments={})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        policy = LineLimitedToolResultProcessingPolicy(max_lines=10, suffix="...[more]")
        run = Run.create(agent, session, model, tool_result_processing_policy=policy)
        events = await run.execute_to_completion("Test")

        # Tool result should be line-limited
        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 1
        lines = tool_events[0].result.split("\n")
        assert len(lines) <= 11  # 10 lines + suffix
        assert "...[more]" in tool_events[0].result
        # Raw result should have 100 lines
        raw_lines = tool_events[0].raw_result.split("\n")
        assert len(raw_lines) == 100

    @pytest.mark.asyncio
    async def test_run_without_tool_result_processing_policy(self) -> None:
        """Test Run works without tool_result_processing_policy (default passthrough)."""
        tool = FakeTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"msg": "hello"})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        run = Run.create(agent, session, model)
        assert run.tool_result_processing_policy is None

        events = await run.execute_to_completion("Test")

        # Tool should have been executed with unchanged result
        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 1
        assert tool_events[0].result == tool_events[0].raw_result

    @pytest.mark.asyncio
    async def test_raw_result_preserved_for_trace(self) -> None:
        """Test raw_result is available even when result is processed."""
        from quenda.runtime.tool_policy import TruncatingToolResultProcessingPolicy

        class SecretTool:
            """A tool that might return sensitive data."""
            @property
            def name(self) -> str:
                return "secret"

            @property
            def description(self) -> str:
                return "Secret tool"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object"}

            def execute(self, **kwargs: object) -> ToolResult:
                return ToolResult(
                    call_id="",
                    name="secret",
                    content="API_KEY=secret123\nPASSWORD=hidden\nDATA=public",
                )

        tool = SecretTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="secret", arguments={})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        # Truncate to hide "secrets"
        policy = TruncatingToolResultProcessingPolicy(max_chars=10, suffix="...")
        run = Run.create(agent, session, model, tool_result_processing_policy=policy)
        events = await run.execute_to_completion("Test")

        # Result is truncated, but raw_result has full content
        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 1
        assert len(tool_events[0].result) <= 15  # 10 chars + suffix
        assert "API_KEY=secret123" in tool_events[0].raw_result

    @pytest.mark.asyncio
    async def test_image_content_preserved_for_tool_results(self) -> None:
        """Test that image tool results keep their image payload through runtime writeback."""

        class ImageTool:
            @property
            def name(self) -> str:
                return "read_file"

            @property
            def description(self) -> str:
                return "Read file"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object"}

            def execute(self, **kwargs: object) -> ToolResult:
                return ToolResult(
                    call_id="",
                    name="read_file",
                    content="Image: sample.png",
                    image_content=ImageContent(media_type="image/png", data="AAAA"),
                )

        tool = ImageTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = CapturingModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="read_file", arguments={"path": "sample.png"})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        run = Run.create(agent, session, model)
        await run.execute_to_completion("Read the image")

        assert len(model.invocations) >= 2
        tool_result_message = model.invocations[1][-1]
        assert tool_result_message.role == "user"
        assert isinstance(tool_result_message.content, list)
        tool_result = tool_result_message.content[0]
        assert isinstance(tool_result, ToolResult)
        assert tool_result.image_content is not None
        assert tool_result.image_content.media_type == "image/png"

    @pytest.mark.asyncio
    async def test_historical_images_do_not_keep_session_routed_to_vision(self) -> None:
        """Historical image payloads are lazy in later turns."""
        from quenda.runtime.events import ModelRouted

        agent = AgentConfig(name="test")
        session = SessionState.create("test")
        default_model = RoutingCaptureModel(vision=False)
        vision_model = RoutingCaptureModel(vision=True)

        first_run = Run.create(
            agent,
            session,
            default_model,
            vision_model=vision_model,
        )
        first_events = await first_run.execute_to_completion([
            TextContent(text="Describe this image"),
            ImageContent(media_type="image/png", data="AAAA"),
        ])

        assert any(isinstance(event, ModelRouted) for event in first_events)
        assert len(vision_model.invocations) == 1
        first_content = vision_model.invocations[0][0].content
        assert isinstance(first_content, list)
        assert any(isinstance(block, ImageContent) for block in first_content)

        second_run = Run.create(
            agent,
            session,
            default_model,
            vision_model=vision_model,
        )
        second_events = await second_run.execute_to_completion("Continue with text only")

        assert not any(isinstance(event, ModelRouted) for event in second_events)
        assert len(default_model.invocations) == 1
        second_messages = default_model.invocations[0]
        assert not any(
            isinstance(block, ImageContent)
            for message in second_messages
            if isinstance(message.content, list)
            for block in message.content
        )
        assert "[Image resource: image/png" in str(second_messages[0].content[1].text)
        assert isinstance(session.messages[0].content, list)
        assert any(isinstance(block, ImageContent) for block in session.messages[0].content)

    @pytest.mark.asyncio
    async def test_activate_resource_tool_attaches_historical_image_and_routes_to_vision(self) -> None:
        """Model can request a historical image through structured resource activation."""
        from quenda.runtime.events import ModelRouted
        from quenda.tools.resource_activation import ActivateResourceTool

        agent = AgentConfig(name="test", tools=[ActivateResourceTool()])
        session = SessionState.create("test")
        session.add_image_ref(ImageRef(
            id="img0",
            source=ImageSource(
                scheme="data",
                uri="data:image/png;base64,AAAA",
                media_type="image/png",
                filename="sample.png",
            ),
        ))
        session.add_user_message("Here is an image [img0: sample.png]")
        session.add_message(Message(role="assistant", content="It is an orange cat."))

        default_model = RoutingCaptureModel(
            vision=False,
            responses=[
                ModelResponse(
                    tool_calls=[
                        ToolCall(
                            id="c1",
                            name="activate_resource",
                            arguments={
                                "resource_id": "img0",
                                "purpose": "Inspect the image again",
                            },
                        )
                    ],
                    stop_reason="tool_use",
                ),
            ],
        )
        vision_model = RoutingCaptureModel(
            vision=True,
            responses=[ModelResponse(content="Vision answer", stop_reason="end_turn")],
        )

        run = Run.create(
            agent,
            session,
            default_model,
            vision_model=vision_model,
        )
        events = await run.execute_to_completion("Look at that image again")

        routed_events = [event for event in events if isinstance(event, ModelRouted)]
        assert len(routed_events) == 1
        assert routed_events[0].resolved_role == "vision"
        assert len(default_model.invocations) == 1
        assert len(vision_model.invocations) == 1

        vision_messages = vision_model.invocations[0]
        assert any(
            isinstance(block, ImageContent)
            for message in vision_messages
            if isinstance(message.content, list)
            for block in message.content
        )
        resource_context = [message.content for message in default_model.invocations[0] if message.role == "system"]
        assert any("[Resource img0]" in str(content) for content in resource_context)

    def test_resource_context_includes_original_file_path(self) -> None:
        """Session resource placeholders expose source metadata without raw image payload."""
        agent = AgentConfig(name="test")
        session = SessionState.create("test")
        session.add_image_ref(ImageRef(
            id="img0",
            source=ImageSource(
                scheme="file",
                uri="file:///Users/example/Downloads/test.jpg",
                media_type="image/jpeg",
                filename="test.jpg",
            ),
        ))
        run = Run.create(agent, session, RoutingCaptureModel(vision=False))

        messages = run._build_messages()
        context = "\n".join(str(message.content) for message in messages if message.role == "system")

        assert "[Resource img0]" in context
        assert "filename=test.jpg" in context
        assert "source=file" in context
        assert "path=/Users/example/Downloads/test.jpg" in context
        assert "raw=not_attached" in context


class TestToolPhaseEvents:
    """Tests for ToolPhaseStarted event and denial semantics (Phase 5)."""

    @pytest.mark.asyncio
    async def test_tool_phase_started_event_emitted(self) -> None:
        """Test ToolPhaseStarted event is emitted with correct data."""
        from quenda.runtime.events import ToolPhaseStarted
        from quenda.runtime.tool_policy import DenylistToolSelectionPolicy

        class NamedTool:
            def __init__(self, name: str) -> None:
                self._name = name

            @property
            def name(self) -> str:
                return self._name

            @property
            def description(self) -> str:
                return f"Tool {self._name}"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object"}

            def execute(self, **kwargs: object) -> ToolResult:
                return ToolResult(call_id="", name=self._name, content=f"{self._name} result")

        tool1 = NamedTool("tool1")
        tool2 = NamedTool("tool2")
        agent = AgentConfig(name="test", tools=[tool1, tool2])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[
                    ToolCall(id="c1", name="tool1", arguments={}),
                    ToolCall(id="c2", name="tool2", arguments={}),
                ],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        policy = DenylistToolSelectionPolicy(denied={"tool2"})
        run = Run.create(agent, session, model, tool_selection_policy=policy)
        events = await run.execute_to_completion("Test")

        # Should have ToolPhaseStarted event
        phase_events = [e for e in events if isinstance(e, ToolPhaseStarted)]
        assert len(phase_events) == 1

        phase_event = phase_events[0]
        # Should have 2 requested calls
        assert len(phase_event.requested_calls) == 2
        # Should have 1 approved (tool1)
        assert len(phase_event.approved_calls) == 1
        assert "c1" in phase_event.approved_calls
        # Should have 1 rejected (tool2)
        assert len(phase_event.rejected_calls) == 1
        assert phase_event.rejected_calls[0]["id"] == "c2"
        assert "denylist" in phase_event.rejected_calls[0]["reason"]
        # Policy name should be correct
        assert phase_event.policy_name == "DenylistToolSelectionPolicy"

    @pytest.mark.asyncio
    async def test_tool_phase_started_with_no_policy(self) -> None:
        """Test ToolPhaseStarted event shows default policy when none configured."""
        from quenda.runtime.events import ToolPhaseStarted

        tool = FakeTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        run = Run.create(agent, session, model)
        events = await run.execute_to_completion("Test")

        phase_events = [e for e in events if isinstance(e, ToolPhaseStarted)]
        assert len(phase_events) == 1

        phase_event = phase_events[0]
        # All calls should be approved
        assert len(phase_event.approved_calls) == 1
        assert len(phase_event.rejected_calls) == 0
        # Default policy name
        assert phase_event.policy_name == "AllowAllToolSelectionPolicy"

    @pytest.mark.asyncio
    async def test_tool_executed_has_denial_fields(self) -> None:
        """Test ToolExecuted event has is_denied and denial_reason fields."""
        from quenda.runtime.tool_policy import DenylistToolSelectionPolicy

        tool = FakeTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"msg": "hello"})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        policy = DenylistToolSelectionPolicy(denied={"echo"})
        run = Run.create(agent, session, model, tool_selection_policy=policy)
        events = await run.execute_to_completion("Test")

        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 1

        # Should be marked as denied
        assert tool_events[0].is_denied is True
        assert "denylist" in tool_events[0].denial_reason
        assert tool_events[0].is_error is True

    @pytest.mark.asyncio
    async def test_tool_executed_approved_not_denied(self) -> None:
        """Test approved tool execution is not marked as denied."""
        tool = FakeTool()
        agent = AgentConfig(name="test", tools=[tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"msg": "hello"})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        run = Run.create(agent, session, model)
        events = await run.execute_to_completion("Test")

        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 1

        # Should not be marked as denied
        assert tool_events[0].is_denied is False
        assert tool_events[0].denial_reason == ""

    @pytest.mark.asyncio
    async def test_trace_distinguishes_denial_from_failure(self) -> None:
        """Test trace can distinguish tool denial from execution failure."""
        from quenda.runtime.tool_policy import DenylistToolSelectionPolicy

        class FailingTool:
            @property
            def name(self) -> str:
                return "failing"

            @property
            def description(self) -> str:
                return "Failing tool"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object"}

            def execute(self, **kwargs: object) -> ToolResult:
                raise RuntimeError("Tool crashed!")

        class DeniedTool:
            @property
            def name(self) -> str:
                return "denied"

            @property
            def description(self) -> str:
                return "Denied tool"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object"}

            def execute(self, **kwargs: object) -> ToolResult:
                return ToolResult(call_id="", name="denied", content="ok")

        failing_tool = FailingTool()
        denied_tool = DeniedTool()
        agent = AgentConfig(name="test", tools=[failing_tool, denied_tool])
        session = SessionState.create("test")
        model = FakeModel([
            ModelResponse(
                tool_calls=[
                    ToolCall(id="c1", name="failing", arguments={}),
                    ToolCall(id="c2", name="denied", arguments={}),
                ],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done!", stop_reason="end_turn"),
        ])

        policy = DenylistToolSelectionPolicy(denied={"denied"})
        run = Run.create(agent, session, model, tool_selection_policy=policy)
        events = await run.execute_to_completion("Test")

        tool_events = [e for e in events if isinstance(e, ToolExecuted)]
        assert len(tool_events) == 2

        # failing tool: error but not denied
        failing_event = next(e for e in tool_events if e.tool_name == "failing")
        assert failing_event.is_error is True
        assert failing_event.is_denied is False

        # denied tool: error AND denied
        denied_event = next(e for e in tool_events if e.tool_name == "denied")
        assert denied_event.is_error is True
        assert denied_event.is_denied is True
        assert "denylist" in denied_event.denial_reason


class TestAgentPolicyBinding:
    """Tests for Agent-level policy binding (Phase 6)."""

    @pytest.mark.asyncio
    async def test_agent_tool_selection_policy_binding(self) -> None:
        """Test Agent accepts and propagates tool_selection_policy."""
        from quenda.runtime.agent import Agent
        from quenda.runtime.tool_policy import DenylistToolSelectionPolicy

        class EchoTool:
            @property
            def name(self) -> str:
                return "echo"

            @property
            def description(self) -> str:
                return "Echo tool"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object"}

            def execute(self, **kwargs: object) -> ToolResult:
                return ToolResult(call_id="", name="echo", content="echoed")

        tool = EchoTool()
        policy = DenylistToolSelectionPolicy(denied={"echo"})

        agent = Agent(
            name="test",
            tools=[tool],
            tool_selection_policy=policy,
        )

        assert agent.tool_selection_policy is policy

    @pytest.mark.asyncio
    async def test_agent_tool_result_processing_policy_binding(self) -> None:
        """Test Agent accepts and propagates tool_result_processing_policy."""
        from quenda.runtime.agent import Agent
        from quenda.runtime.tool_policy import TruncatingToolResultProcessingPolicy

        policy = TruncatingToolResultProcessingPolicy(max_chars=100)

        agent = Agent(
            name="test",
            tools=[],
            tool_result_processing_policy=policy,
        )

        assert agent.tool_result_processing_policy is policy

    @pytest.mark.asyncio
    async def test_agent_termination_policy_binding(self) -> None:
        """Test Agent accepts and propagates termination_policy."""
        from quenda.runtime.agent import Agent
        from quenda.runtime.termination import MaxStepsPolicy

        policy = MaxStepsPolicy(max_steps=10)

        agent = Agent(
            name="test",
            tools=[],
            termination_policy=policy,
        )

        assert agent.termination_policy is policy


class TestSessionPolicyBinding:
    """Tests for Session-level policy binding (Phase 6)."""

    @pytest.mark.asyncio
    async def test_session_inherits_agent_policies(self) -> None:
        """Test Session inherits policies from Agent."""
        from quenda.runtime.agent import Agent
        from quenda.runtime.tool_policy import DenylistToolSelectionPolicy, TruncatingToolResultProcessingPolicy
        from quenda.runtime.termination import MaxStepsPolicy

        selection_policy = DenylistToolSelectionPolicy(denied={"dangerous"})
        result_policy = TruncatingToolResultProcessingPolicy(max_chars=100)
        termination_policy = MaxStepsPolicy(max_steps=10)

        agent = Agent(
            name="test",
            tools=[],
            tool_selection_policy=selection_policy,
            tool_result_processing_policy=result_policy,
            termination_policy=termination_policy,
        )

        session = agent.open_session()

        assert session.tool_selection_policy is selection_policy
        assert session.tool_result_processing_policy is result_policy
        assert session.termination_policy is termination_policy

    @pytest.mark.asyncio
    async def test_session_policies_flow_to_run(self) -> None:
        """Test Session policies are passed to Run during send()."""
        from quenda.runtime.agent import Agent
        from quenda.runtime.tool_policy import DenylistToolSelectionPolicy

        class EchoTool:
            @property
            def name(self) -> str:
                return "echo"

            @property
            def description(self) -> str:
                return "Echo tool"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object"}

            def execute(self, **kwargs: object) -> ToolResult:
                return ToolResult(call_id="", name="echo", content="echoed")

        tool = EchoTool()
        policy = DenylistToolSelectionPolicy(denied={"echo"})

        # Create fake model
        class FakeModelForSession:
            def invoke(self, messages, *, tools):
                from quenda.kernel.types import ModelResponse
                return ModelResponse(content="Done", stop_reason="end_turn")

        agent = Agent(
            name="test",
            tools=[tool],
            model=FakeModelForSession(),
            tool_selection_policy=policy,
        )

        session = agent.open_session()

        # The session should have the policy
        assert session.tool_selection_policy is policy
