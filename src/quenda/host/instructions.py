"""
Instruction layer for Quenda Host.

Implements ADR-007: Instruction Layer and Scope Overlay.

Provides instruction composition from multiple scopes:
1. Framework contract (skills path conventions, workspace structure)
2. Agent package AGENT.md
3. Agent package config.yaml included instructions
4. User-level configured instruction files
5. User-agent INSTRUCTIONS.md
6. Project-level configured instruction files and INSTRUCTIONS.md
7. Workspace-agent INSTRUCTIONS.md
8. User-project configured instruction files
9. Activated skills
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quenda.host.identity import User
    from quenda.host.skill.package import SkillPackage
    from quenda.runtime.temporal import TemporalContext


# Framework contract - always included as the base context
FRAMEWORK_CONTRACT = """
## Quenda Framework Conventions

Treat the project directory as the shared physical workspace. Quenda's
`.quenda/workspace.yaml` binds it to per-user session state under
`~/.quenda/users/<user>/`; do not confuse that private state with project files.

Skills are progressively disclosed instruction packages. Resolution priority is:

1. user-workspace skills (highest priority, isolated to this user and workspace)
2. agent-bundled skills
3. user skills (lowest priority)

Each skill is rooted at a `skills/<skill-name>/SKILL.md` package.

The available-skill catalog contains routing metadata only. When a task matches a
skill, request its activation by exact name. Do not assume it is active until the
Host confirms activation. Activated instructions are added to context; references,
templates, scripts, and other resources are loaded on demand with the skill resource
tools. Do not invent resource contents or paths.

Skill discovery is refreshed at turn boundaries. Use `/skill` commands only when
the user explicitly asks to inspect or control activation state.
"""


SKILL_CATALOG_DESCRIPTION_LIMIT = 180


def _compact_skill_description(description: str) -> str:
    """Return a one-line routing hint rather than full trigger documentation."""
    normalized = " ".join(description.split())
    if len(normalized) <= SKILL_CATALOG_DESCRIPTION_LIMIT:
        return normalized

    sentence_end = normalized.find(". ")
    if 0 < sentence_end < SKILL_CATALOG_DESCRIPTION_LIMIT:
        return normalized[: sentence_end + 1]

    return normalized[: SKILL_CATALOG_DESCRIPTION_LIMIT - 1].rstrip() + "…"


class InstructionScope(IntEnum):
    """
    Scope for instruction sources.

    Lower numbers = higher priority (loaded first).
    Higher numbers = more specific (loaded later, can override).
    """

    FRAMEWORK = 0       # Quenda framework contract
    AGENT_PACKAGE = 1   # Agent package AGENT.md
    AGENT_INSTRUCTIONS = 2  # Agent package instructions/*.md
    USER_GLOBAL = 3     # ~/.quenda/users/<user>/INSTRUCTIONS.md
    USER_AGENT = 4      # ~/.quenda/users/<user>/agents/<agent>/INSTRUCTIONS.md
    WORKSPACE = 5       # <workspace>/.quenda/INSTRUCTIONS.md
    WORKSPACE_AGENT = 6 # <workspace>/.quenda/agents/<agent>/INSTRUCTIONS.md
    USER_WORKSPACE = 7  # ~/.quenda/users/<user>/workspaces/<ws_id>/<filename>
    SKILL = 8           # Activated skills


@dataclass(frozen=True)
class InstructionSource:
    """
    A single source of instructions.

    Attributes:
        scope: The scope this instruction belongs to.
        content: The raw instruction text (may contain {{variables}}).
        path: Optional path to the source file (for debugging/display).
    """

    scope: InstructionScope
    content: str
    path: Path | None = None


@dataclass(frozen=True)
class TemplateContext:
    """
    Context for template variable substitution.

    All variables are whitelisted - only these can be used in templates.
    """

    agent_name: str
    agent_version: str
    workspace_id: str
    workspace_path: str
    user_id: str
    model_provider: str
    model_name: str
    date: str
    session_id: str
    mode: str = "chat"


class InstructionComposer:
    """
    Composes instruction text from multiple sources.

    Usage:
        composer = InstructionComposer(context)
        text = composer.compose(sources)
    """

    # Pattern to match {{variable}} templates
    TEMPLATE_PATTERN = re.compile(r"\{\{(\w+(?:\.\w+)*)\}\}")

    def __init__(self, context: TemplateContext) -> None:
        """
        Initialize composer with template context.

        Args:
            context: The context for variable substitution.
        """
        self.context = context

    def compose(self, sources: list[InstructionSource]) -> str:
        """
        Compose instruction text from sources in order.

        Args:
            sources: List of instruction sources in priority order.

        Returns:
            Composed instruction text with all sources appended.
        """
        parts = []
        for source in sources:
            rendered = self.render_template(source.content)
            if rendered.strip():
                parts.append(rendered)
        return "\n\n".join(parts)

    def render_template(self, content: str) -> str:
        """
        Replace {{variable}} with context values.

        Only whitelisted variables are supported.
        Nested access like {{agent.name}} is supported.

        Args:
            content: Content containing {{variable}} templates.

        Returns:
            Content with variables replaced.
        """
        def replace_var(match: re.Match[str]) -> str:
            var_path = match.group(1)
            return self._resolve_variable(var_path)

        return self.TEMPLATE_PATTERN.sub(replace_var, content)

    def _resolve_variable(self, var_path: str) -> str:
        """
        Resolve a variable path to its value.

        Args:
            var_path: Variable path like "agent.name" or "workspace_id".

        Returns:
            The resolved value as string, or empty string if not found.
        """
        # Map of top-level variable names to context attributes
        var_map: dict[str, str] = {
            "agent.name": self.context.agent_name,
            "agent.version": self.context.agent_version,
            "workspace.id": self.context.workspace_id,
            "workspace.path": self.context.workspace_path,
            "user.id": self.context.user_id,
            "model.provider": self.context.model_provider,
            "model.name": self.context.model_name,
            "date": self.context.date,
            "session.id": self.context.session_id,
            "mode": self.context.mode,
        }

        return var_map.get(var_path, "")


def resolve_instruction_sources(
    agent_package_path: Path,
    agent_name: str,
    agent_md_content: str,
    agent_instructions: list[InstructionSource],
    workspace_path: Path,
    user: User,
    workspace_id: str | None = None,
    instruction_files: list[str] | None = None,
    discovered_skills: list[SkillPackage] | None = None,
    active_skills: list[SkillPackage] | None = None,
    include_skill_catalog: bool = False,
    temporal_context: TemporalContext | None = None,
) -> list[InstructionSource]:
    """
    Resolve all instruction sources in priority order.

    MVP scope:
    - Agent package AGENT.md + included instructions
    - Configured user, project, and user-project instruction files
    - Legacy user-agent and workspace INSTRUCTIONS.md files
    - Workspace-agent INSTRUCTIONS.md
    - Activated skills (full instructions - for skills in use)
    - Optional discovered skill catalog for debugging or explicit routing flows

    Args:
        agent_package_path: Path to agent package directory.
        agent_name: Agent name.
        agent_md_content: Content of AGENT.md (base prompt).
        agent_instructions: Included instructions from agent package.
        workspace_path: Workspace directory.
        user: Current user.
        workspace_id: Stable logical workspace identifier. Required to resolve
            the user-project instruction scope.
        instruction_files: Agent-configured filenames. Defaults to QUENDA.md.
        discovered_skills: All discovered skills.
        active_skills: Activated skills (full instructions injected).
        include_skill_catalog: Whether to inject the discovered skill catalog into
            the prompt. Default is False so skills stay host-managed unless
            explicitly surfaced.

    Returns:
        List of instruction sources in priority order.
    """
    sources: list[InstructionSource] = []
    configured_files = ["QUENDA.md"] if instruction_files is None else instruction_files

    # 1. Framework contract (skills conventions, workspace structure)
    sources.append(InstructionSource(
        scope=InstructionScope.FRAMEWORK,
        content=FRAMEWORK_CONTRACT,
        path=None,
    ))

    if temporal_context is not None:
        sources.append(InstructionSource(
            scope=InstructionScope.FRAMEWORK,
            content=temporal_context.render_prompt(),
            path=None,
        ))

    # 2. Agent package AGENT.md (base prompt)
    sources.append(InstructionSource(
        scope=InstructionScope.AGENT_PACKAGE,
        content=agent_md_content,
        path=agent_package_path / "AGENT.md",
    ))

    # 3. Agent package included instructions
    sources.extend(agent_instructions)

    # Local Agent Homes keep their editable identity, user profile, and durable
    # memory beside AGENT.md. Package agents without agent.yaml retain the
    # existing user-scoped overlay behavior.
    if (agent_package_path / "agent.yaml").is_file():
        for filename in ("SOUL.md", "USER.md", "MEMORY.md"):
            home_instruction = agent_package_path / filename
            if home_instruction.is_file():
                content = home_instruction.read_text(encoding="utf-8").strip()
                if content:
                    sources.append(
                        InstructionSource(
                            scope=InstructionScope.AGENT_INSTRUCTIONS,
                            content=content,
                            path=home_instruction,
                        )
                    )

    # 4. User-level configured instruction files
    user_root = Path.home() / ".quenda" / "users" / user.id
    for filename in configured_files:
        user_instruction = user_root / filename
        if user_instruction.is_file():
            sources.append(InstructionSource(
                scope=InstructionScope.USER_GLOBAL,
                content=user_instruction.read_text(encoding="utf-8"),
                path=user_instruction,
            ))

    # 5. User-agent INSTRUCTIONS.md (legacy agent-specific preferences)
    user_agent = Path.home() / ".quenda" / "users" / user.id / "agents" / agent_name / "INSTRUCTIONS.md"
    if user_agent.exists():
        sources.append(InstructionSource(
            scope=InstructionScope.USER_AGENT,
            content=user_agent.read_text(encoding="utf-8"),
            path=user_agent,
        ))

    # 6. Project-level configured instruction files. For each configured name,
    # the visible project-root file precedes its .quenda counterpart.
    for filename in configured_files:
        for project_instruction in (
            workspace_path / filename,
            workspace_path / ".quenda" / filename,
        ):
            if project_instruction.is_file():
                sources.append(InstructionSource(
                    scope=InstructionScope.WORKSPACE,
                    content=project_instruction.read_text(encoding="utf-8"),
                    path=project_instruction,
                ))

    # Legacy project-level INSTRUCTIONS.md
    workspace_instructions = workspace_path / ".quenda" / "INSTRUCTIONS.md"
    if workspace_instructions.is_file() and workspace_instructions.name not in configured_files:
        sources.append(InstructionSource(
            scope=InstructionScope.WORKSPACE,
            content=workspace_instructions.read_text(encoding="utf-8"),
            path=workspace_instructions,
        ))

    # 7. Workspace-agent INSTRUCTIONS.md
    workspace_agent = workspace_path / ".quenda" / "agents" / agent_name / "INSTRUCTIONS.md"
    if workspace_agent.exists():
        sources.append(InstructionSource(
            scope=InstructionScope.WORKSPACE_AGENT,
            content=workspace_agent.read_text(encoding="utf-8"),
            path=workspace_agent,
        ))

    # 8. User-project configured instruction files (most specific file scope)
    if workspace_id:
        user_workspace_root = user_root / "workspaces" / workspace_id
        for filename in configured_files:
            user_workspace_instruction = user_workspace_root / filename
            if user_workspace_instruction.is_file():
                sources.append(InstructionSource(
                    scope=InstructionScope.USER_WORKSPACE,
                    content=user_workspace_instruction.read_text(encoding="utf-8"),
                    path=user_workspace_instruction,
                ))

    # 9. Optional discovered skills catalog (description only)
    if include_skill_catalog and discovered_skills:
        skill_catalog_lines = [
            "## Available Skills\n",
            "The Host discovered these optional skills for this workspace.\n",
            "If you need one of them, call `request_skill_activation` with the exact `skill_name`.\n",
            "Do not assume a skill is active until Host confirms activation in a follow-up phase.\n",
        ]
        for skill in discovered_skills:
            is_active = active_skills and any(s.name == skill.name for s in active_skills)
            status = "✓ active" if is_active else "available"
            description = _compact_skill_description(skill.description)
            skill_catalog_lines.append(f"- **{skill.name}** ({status}): {description}")
        sources.append(InstructionSource(
            scope=InstructionScope.SKILL,
            content="\n".join(skill_catalog_lines),
            path=None,
        ))

    # 10. Activated skills (full instructions with structured wrapping per Agent Skills spec)
    # Uses <skill_content> tags for:
    # - Clear identification during context compaction
    # - Distinguishing skill instructions from other content
    # - Surfacing bundled resources without eager loading
    if active_skills:
        for skill in active_skills:
            # Build resource listing (not loaded, just enumerated)
            resource_listing = ""
            if skill.resources:
                resource_lines = ["\n\n<skill_resources>"]
                for r in skill.resources:
                    try:
                        relative = str(r.path.relative_to(skill.path))
                    except ValueError:
                        relative = r.path.name
                    resource_lines.append(f"  <file>{relative}</file>")
                resource_lines.append("</skill_resources>")
                resource_listing = "\n".join(resource_lines)

            # Structured wrapping per Agent Skills specification
            skill_content = f"""<skill_content name="{skill.name}">
{skill.instructions}

Skill directory: {skill.path}
Relative paths in this skill are relative to the skill directory.{resource_listing}
</skill_content>"""
            sources.append(InstructionSource(
                scope=InstructionScope.SKILL,
                content=skill_content,
                path=skill.path / "SKILL.md",
            ))

    return sources


def resolve_mode_instruction_source(
    agent_package_path: Path,
    mode: str,
) -> list[InstructionSource]:
    """Load the instruction overlay for the current interaction mode."""
    if re.fullmatch(r"[a-z][a-z0-9-]*", mode) is None:
        return []

    mode_file = agent_package_path / "instructions" / f"mode-{mode}.md"
    if not mode_file.exists():
        return []

    return [
        InstructionSource(
            scope=InstructionScope.AGENT_INSTRUCTIONS,
            content=mode_file.read_text(encoding="utf-8"),
            path=mode_file,
        )
    ]


__all__ = [
    "InstructionScope",
    "InstructionSource",
    "TemplateContext",
    "InstructionComposer",
    "resolve_instruction_sources",
    "resolve_mode_instruction_source",
    "FRAMEWORK_CONTRACT",
]
