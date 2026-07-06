"""Tests for interface event handlers."""

from dataclasses import dataclass, field
from io import StringIO

from quenda.interface import ActivityEventHandler, InterfaceTheme, ProgressEventHandler, StreamingEventHandler
from quenda.interface.console import ConsoleRenderer
from quenda.interface.status import StatusBarManager
from quenda.runtime.events import ModelResponded, ModelRouted, RunCompleted, RunStarted, ToolExecuted


@dataclass
class FakeIndicator:
    """Simple indicator spy for event handler tests."""

    running: bool = False
    messages: list[str] = field(default_factory=list)

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def update(self, message: str) -> None:
        self.messages.append(message)

    @property
    def is_running(self) -> bool:
        return self.running


def test_activity_event_handler_drives_indicator_without_rendering() -> None:
    indicator = FakeIndicator()
    status_bar = StatusBarManager()
    handler = ActivityEventHandler(
        indicator=indicator,
        theme=InterfaceTheme(),
        renderer=ConsoleRenderer(),
        status_bar=status_bar,
    )

    handler.on_event(RunStarted(user_message="hello"))
    handler.on_event(ModelResponded(
        content="",
        tool_call_details=[{
            "id": "call_1",
            "name": "web_search",
            "arguments": {"_summary": "Searching latest filings"},
        }],
    ))
    handler.on_event(ToolExecuted(tool_name="web_search"))
    handler.on_event(ModelResponded(content="final answer"))
    handler.on_event(RunCompleted(final_content="final answer"))

    assert indicator.is_running is False
    assert indicator.messages[0] == "Thinking..."
    assert "Searching latest filings" in indicator.messages
    assert indicator.messages[-1] == "Thinking..."
    assert any("Searching latest filings" in line for line in status_bar.get_activity_log())


def test_progress_event_handler_renders_tool_progress_without_run_headers() -> None:
    """Progress handler shows tool execution but NOT run phase headers."""
    indicator = FakeIndicator()
    output = StringIO()
    handler = ProgressEventHandler(
        renderer=ConsoleRenderer(),
        indicator=indicator,
        output=output,
    )

    # First run
    handler.on_event(RunStarted(user_message="hello"))
    handler.on_event(ToolExecuted(
        tool_name="web_search",
        arguments={"_summary": "Searching latest filings"},
        result_summary="3 matches",
    ))

    # Second run (e.g., after skill activation)
    handler.on_event(RunStarted(user_message="Activated skills: code-review. Original request: hello"))
    handler.on_event(ToolExecuted(
        tool_name="read_file",
        arguments={"_summary": "Reading file"},
        result_summary="100 lines",
    ))

    text = output.getvalue()

    # Should show tool execution progress
    assert "Searching latest filings" in text
    assert "Reading file" in text

    # Should NOT show any run phase headers
    assert "[Run 1]" not in text
    assert "[Run 2]" not in text
    assert "🔄" not in text
    assert "Activating skills" not in text


def test_console_renderer_clears_routed_model_between_runs() -> None:
    renderer = ConsoleRenderer()

    renderer.render(RunStarted(user_message="image"))
    renderer.render(ModelRouted(
        resolved_role="vision",
        provider="jdcloud",
        model_id="Kimi-K2.5",
        required_capabilities={"text", "vision"},
    ))
    first_completion = renderer.render(RunCompleted(total_steps=1))

    renderer.render(RunStarted(user_message="text"))
    second_completion = renderer.render(RunCompleted(total_steps=1))

    assert first_completion is not None
    assert "model: jdcloud/Kimi-K2.5" in first_completion
    assert second_completion is not None
    assert "model:" not in second_completion


def test_streaming_handler_clears_routed_model_between_non_verbose_runs() -> None:
    indicator = FakeIndicator()
    output = StringIO()
    handler = StreamingEventHandler(
        renderer=ConsoleRenderer(),
        indicator=indicator,
        theme=InterfaceTheme(),
        output=output,
        verbose_start=False,
    )

    handler.on_event(RunStarted(user_message="image"))
    handler.on_event(ModelRouted(
        resolved_role="vision",
        provider="jdcloud",
        model_id="Kimi-K2.5",
        required_capabilities={"text", "vision"},
    ))
    handler.on_event(RunCompleted(total_steps=1))

    handler.on_event(RunStarted(user_message="text"))
    handler.on_event(RunCompleted(total_steps=1))

    completions = [line for line in output.getvalue().splitlines() if "Done in" in line]
    assert len(completions) == 2
    assert "model: jdcloud/Kimi-K2.5" in completions[0]
    assert "model:" not in completions[1]
