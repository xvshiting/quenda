"""
Theme configuration for Quenda Interface layer.

Provides configurable visual elements and behavior for terminal output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TextIO


@dataclass
class InterfaceTheme:
    """
    Theme configuration for Interface layer.

    Contains all customizable visual elements and behavior parameters.
    Use factory methods for preset themes or customize individual fields.

    Example:
        # Default theme
        theme = InterfaceTheme()

        # Minimal theme for CI/CD
        theme = InterfaceTheme.minimal()

        # Custom theme
        theme = InterfaceTheme(
            agent_icon="🔮",
            spinner_frames=("◐", "◑", "◒", "◓"),
            show_duration=False,
        )
    """

    # === Icons ===
    success_icon: str = "✓"
    error_icon: str = "❌"
    agent_icon: str = "🤖"
    thinking_icon: str = "💭"
    complete_icon: str = "✅"
    interrupt_icon: str = "⚠"
    permission_icon: str = "🔐"

    # === Activity messages ===
    thinking_message: str = "Thinking..."

    # === Separators ===
    status_separator: str = " │ "

    # === Status bar templates ===
    # Available variables: agent_icon, mode, sep, frame, interrupt_icon, error_icon, message, details_hint
    status_idle_template: str = " {agent_icon} mode: {mode}{sep}[/ for commands] "
    status_running_template: str = " {frame} {message}{details_hint} [Ctrl+C to interrupt] "
    status_interrupted_template: str = " {interrupt_icon} Interrupted "
    status_error_template: str = " {error_icon} Error │ {message} "

    # === Activity indicator ===
    spinner_frames: tuple[str, ...] = (
        "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"
    )
    spinner_interval: float = 0.08  # seconds

    # === Welcome message template ===
    # Available variables: agent_icon, agent_name, workspace_id, workspace_path,
    #                      session_id, provider, model, instructions
    welcome_template: str = """
{agent_icon} {agent_name}
   Workspace: {workspace_id}
   Session: {session_id}
   Model: {provider}/{model}
   Workspace path: {workspace_path}

{instructions}
"""

    # === Complete message template ===
    # Available variables: complete_icon, steps, duration
    complete_template: str = "\n\n{complete_icon} Done in {steps} steps{duration}"
    complete_duration_ms_template: str = " ({duration_ms}ms)"
    complete_duration_s_template: str = " ({duration_s:.1f}s)"

    # === Tool phase mapping ===
    tool_phases: dict[str, str] = field(default_factory=lambda: {
        "list_files": "reading",
        "read_file": "reading",
        "search_text": "searching",
        "write_file": "editing",
        "apply_patch": "editing",
        "run_shell": "executing",
        "python_execution": "executing",
        "http_request": "network",
        "web_fetch": "network",
        "web_search": "searching",
    })

    phase_labels: dict[str, str] = field(default_factory=lambda: {
        "reading": "📖 Reading",
        "searching": "🔍 Searching",
        "editing": "✏️ Editing",
        "executing": "⚡ Running",
        "network": "🌐 Fetching",
    })

    # === Error display ===
    max_error_lines: int = 5
    max_message_length: int = 40

    # === Behavior switches ===
    show_duration: bool = True
    show_esc_hint: bool = True  # Whether to show interrupt hint in spinner
    esc_hint_always: bool = True  # If True, always show; if False, show every N frames
    esc_hint_interval: int = 60  # Show hint every N frames (when esc_hint_always=False)
    esc_hint_text: str = "[Ctrl+C to interrupt]"  # Customizable hint text

    # === Output streams ===
    # None means use sys.stdout / sys.stderr
    output_stream: TextIO | None = None
    error_stream: TextIO | None = None

    @classmethod
    def minimal(cls) -> InterfaceTheme:
        """
        Minimal theme for CI/CD environments.

        Uses ASCII-safe characters and reduced output.
        """
        return cls(
            agent_icon="[Quenda]",
            success_icon="[OK]",
            error_icon="[ERR]",
            complete_icon="[DONE]",
            interrupt_icon="[INT]",
            thinking_icon="[...]",
            spinner_frames=("|", "/", "-", "\\"),
            status_separator=" | ",
            status_idle_template=" {agent_icon} {mode} ",
            status_running_template=" {frame} {message}{details_hint} ",
            welcome_template="{agent_name} | {workspace_id}\n",
            show_esc_hint=False,
            show_duration=True,
        )

    @classmethod
    def ascii(cls) -> InterfaceTheme:
        """
        ASCII-only theme for terminals without Unicode support.

        Uses only ASCII characters but maintains visual structure.
        """
        return cls(
            agent_icon="[Quenda]",
            success_icon="[+]",
            error_icon="[!]",
            complete_icon="[OK]",
            interrupt_icon="[!]",
            thinking_icon="[...]",
            spinner_frames=(".", "o", "O", "0", "O", "o"),
            status_separator=" | ",
            status_idle_template=" {agent_icon} mode: {mode} | [/ for commands] ",
            status_running_template=" {frame} {message}{details_hint} [Ctrl+C to interrupt] ",
            welcome_template="""
{agent_icon} {agent_name}
   Workspace: {workspace_id}
   Session: {session_id}
   Model: {provider}/{model}
   Path: {workspace_path}

{instructions}
""",
            phase_labels={
                "reading": "[Read]",
                "searching": "[Search]",
                "editing": "[Edit]",
                "executing": "[Run]",
                "network": "[Fetch]",
            },
        )

    @classmethod
    def silent(cls) -> InterfaceTheme:
        """
        Silent theme with minimal visual output.

        Disables most visual elements for quiet operation.
        """
        return cls(
            agent_icon="",
            success_icon="",
            error_icon="",
            complete_icon="",
            interrupt_icon="",
            thinking_icon="",
            spinner_frames=("",),
            status_idle_template="",
            status_running_template="",
            status_interrupted_template="",
            status_error_template="",
            welcome_template="",
            complete_template="Done.",
            show_esc_hint=False,
            show_duration=False,
        )


__all__ = ["InterfaceTheme"]
