"""
Console renderer for Quenda Runtime events.

Renders events to human-readable console output with:
- Tool calls with summaries (from LLM-generated _summary)
- Result summaries
- Error details
- Progress tracking
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quenda.interface.markdown import render_markdown_lite

if TYPE_CHECKING:
    from quenda.interface.theme import InterfaceTheme
    from quenda.runtime.events import AnyEvent


class ConsoleRenderer:
    """
    Renders Runtime events to console output.

    Responsibilities:
    - Format tool calls with LLM-generated summaries
    - Summarize results
    - Show errors with context
    - Track and display progress

    Usage:
        renderer = ConsoleRenderer()
        for event in run.execute(message):
            output = renderer.render(event)
            if output:
                print(output)
    """

    def __init__(
        self,
        theme: InterfaceTheme | None = None,
        *,
        verbose: bool = False,
    ) -> None:
        """
        Initialize the renderer.

        Args:
            theme: Theme configuration. Uses default if not provided.
            verbose: Show detailed output (for one-shot mode).
        """
        from quenda.interface.theme import InterfaceTheme
        self.theme = theme or InterfaceTheme()
        self.verbose = verbose
        self._step_count = 0

    def render(self, event: AnyEvent) -> str | None:
        """
        Render an event to a string.

        Args:
            event: The event to render.

        Returns:
            Rendered string, or None if the event should be skipped.
        """
        if event.type == "run_started":
            return self._render_run_started(event)
        if event.type == "model_responded":
            return self._render_model_responded(event)
        if event.type == "tool_executed":
            return self._render_tool_executed(event)
        if event.type == "run_completed":
            return self._render_run_completed(event)
        if event.type == "error_occurred":
            return self._render_error(event)
        if event.type == "compression_started":
            return self._render_compression_started(event)
        if event.type == "compression_completed":
            return self._render_compression_completed(event)
        return None

    def _render_run_started(self, event: AnyEvent) -> str | None:
        """Render run started event."""
        if not self.verbose:
            return None

        msg = event.user_message
        if len(msg) > 60:
            msg = msg[:60] + "..."

        return f"\n🚀 Starting: {msg}"

    def _render_model_responded(self, event: AnyEvent) -> str | None:
        """Render model response event."""
        lines = []

        # Show content if present (with markdown-lite rendering)
        if event.content:
            lines.append(f"\n{render_markdown_lite(event.content)}")

        # Show tool calls in verbose mode (use tool_call_details for names)
        if self.verbose and event.tool_call_details:
            tool_names = [d.get("name", "unknown") for d in event.tool_call_details]
            tools_str = ", ".join(tool_names)
            lines.append(f"\n🔧 Using tools: {tools_str}")

        return "\n".join(lines) if lines else None

    def _render_tool_executed(self, event: AnyEvent) -> str:
        """
        Render tool execution event.

        Display format (ADR-006):
        - summary (display_hint) - LLM summary with tool-provided hint in parentheses
        - result_summary shown after summary for result context
        - change_preview shown as diff for file modification tools
        """
        self._step_count += 1

        # Use theme icons
        icon = self.theme.error_icon if event.is_error else self.theme.success_icon

        # Build main text: summary + display_hint
        summary = event.arguments.get("_summary", "")
        if summary:
            main_text = summary
        else:
            # Fall back to phase-based label
            phase = self.theme.tool_phases.get(event.tool_name, "executing")
            phase_label = self.theme.phase_labels.get(phase, "⚡ Running")
            main_text = f"{phase_label}..."

        # Add display_hint in parentheses if available
        if event.display_hint:
            main_text = f"{main_text} ({event.display_hint})"

        # Add result_summary if available (e.g., "47 lines", "23 matches")
        if event.result_summary and not event.is_error:
            main_text = f"{main_text} → {event.result_summary}"

        # Duration (only in verbose mode)
        duration_str = ""
        if self.verbose and self.theme.show_duration and event.duration_ms > 0:
            if event.duration_ms < 1000:
                duration_str = f" ({event.duration_ms}ms)"
            else:
                duration_str = f" ({event.duration_ms / 1000:.1f}s)"

        line = f"  {icon} {main_text}{duration_str}"

        # For errors, show details
        if event.is_error and event.result:
            error_lines = self._format_error_result(event.result)
            if error_lines:
                line += "\n" + error_lines

        # For file modifications, show diff preview if available
        if event.change_preview and not event.is_error:
            diff_lines = self._format_change_preview(event.change_preview)
            if diff_lines:
                line += "\n" + diff_lines

        return line

    def _format_change_preview(self, preview: str) -> str:
        """
        Format diff preview for file modification tools with full-line backgrounds.

        Claude Code style:
        - Context lines: "num content" (no background)
        - Removed lines: "num -content" (red background, full width)
        - Added lines: "num +content" (green background, full width)
        - Background extends to terminal width using \033[K
        """
        # ANSI codes
        RED_BG = "\033[48;5;224m"    # Light red background
        GREEN_BG = "\033[48;5;194m"  # Light green background
        CLEAR_EOL = "\033[K"        # Clear to end of line
        RESET = "\033[0m"

        lines = preview.strip().split("\n")
        formatted_lines = []

        # Calculate max line number width for alignment
        max_num_width = 3
        for line in lines:
            # Format: "num -content", "num +content", or "num content"
            parts = line.split(" ", 1)
            if parts and parts[0].isdigit():
                max_num_width = max(max_num_width, len(parts[0]))

        for line in lines:
            parts = line.split(" ", 1)
            if len(parts) != 2:
                formatted_lines.append(f"     {line}")
                continue

            line_num, content = parts
            if not line_num.isdigit():
                formatted_lines.append(f"     {line}")
                continue

            line_num_padded = line_num.rjust(max_num_width)

            if content.startswith("-"):
                # Removed line - red background
                formatted_lines.append(
                    f"     {RED_BG}{line_num_padded} -{content[1:]}{CLEAR_EOL}{RESET}"
                )
            elif content.startswith("+"):
                # Added line - green background
                formatted_lines.append(
                    f"     {GREEN_BG}{line_num_padded} +{content[1:]}{CLEAR_EOL}{RESET}"
                )
            else:
                # Context line - no background
                formatted_lines.append(f"     {line_num_padded} {content}")

        return "\n".join(formatted_lines)

    def _render_run_completed(self, event: AnyEvent) -> str:
        """Render run completed event using theme template."""
        duration_str = ""
        if self.theme.show_duration and event.duration_ms > 0:
            if event.duration_ms < 1000:
                duration_str = self.theme.complete_duration_ms_template.format(
                    duration_ms=event.duration_ms,
                )
            else:
                duration_str = self.theme.complete_duration_s_template.format(
                    duration_s=event.duration_ms / 1000,
                )

        return self.theme.complete_template.format(
            complete_icon=self.theme.complete_icon,
            steps=event.total_steps,
            duration=duration_str,
        )

    def _render_error(self, event: AnyEvent) -> str:
        """Render error event."""
        return f"\n{self.theme.error_icon} Error ({event.error_type}): {event.error_message}"

    def _format_error_result(self, result: str) -> str:
        """Format error result for display."""
        lines = result.strip().split("\n")

        max_lines = self.theme.max_error_lines
        if len(lines) <= max_lines:
            formatted = "\n".join(f"     {line}" for line in lines)
        else:
            # Show first few lines
            shown = lines[:max_lines]
            formatted = "\n".join(f"     {line}" for line in shown)
            remaining = len(lines) - max_lines
            formatted += f"\n     ... ({remaining} more lines)"

        return formatted

    def _render_compression_started(self, event: AnyEvent) -> str | None:
        """
        Render compression started event (ADR-015).

        Shows a brief indicator that compression is underway.
        """
        decision = event.decision
        reason = decision.reason if hasattr(decision, 'reason') and decision.reason else "token threshold"
        return f"\n📦 Compressing context ({reason})..."

    def _render_compression_completed(self, event: AnyEvent) -> str | None:
        """
        Render compression completed event (ADR-015).

        Shows a summary of what was compressed.
        """
        result = event.result
        archived = result.archived_message_count if hasattr(result, 'archived_message_count') else 0
        summary_tokens = result.summary_token_count if hasattr(result, 'summary_token_count') else 0

        parts = []
        if archived > 0:
            parts.append(f"{archived} messages archived")
        if summary_tokens > 0:
            parts.append(f"summary ~{summary_tokens} tokens")

        if parts:
            detail = ", ".join(parts)
            return f"✅ Compression done ({detail})"
        else:
            return "✅ Compression done"


__all__ = ["ConsoleRenderer"]
