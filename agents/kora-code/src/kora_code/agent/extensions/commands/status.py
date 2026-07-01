"""
Sample command extension for kora-code agent.

This demonstrates ADR-010: Agent command extensions.
"""

from kora.host.commands import Command, CommandResult, CommandContext


class StatusCommand:
    """Show agent status."""

    @property
    def name(self) -> str:
        return "status"

    @property
    def description(self) -> str:
        return "Show agent and session status"

    @property
    def usage(self) -> str:
        return "/status"

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        mode = context.get_mode()
        msg_count = len(context.session)

        return CommandResult(
            status="ok",
            message=(
                f"**Status:**\n"
                f"  Mode: `{mode}`\n"
                f"  Messages: {msg_count}\n"
                f"  Session: `{context.session.id[:12]}...`"
            ),
        )


# Export commands list (ADR-010 contract)
commands = [StatusCommand()]