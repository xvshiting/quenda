"""
Skill activation - Managing active skills and composing instructions.

SkillActivator handles:
- Activating/deactivating skills
- Composing instructions from active skills
- Tracking active skill state

ADR-025 Compliance:
- Activation state is stored as skill names (not SkillPackage objects)
- SkillPackage objects are resolved on-demand, not stored durably
- This supports turn-boundary reload semantics
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from quenda.host.skill.discovery import SkillDiscovery
    from quenda.host.skill.package import SkillPackage

logger = logging.getLogger(__name__)


@dataclass
class SkillActivator:
    """
    Manages skill activation and instruction composition.

    The activator tracks which skills are currently active and
    provides methods to compose their instructions into a unified
    instruction block.

    ADR-025 Compliance:
    - Durable state is active_skill_names (list of names, not objects)
    - SkillPackage objects are resolved on-demand from names
    - This allows fresh skill content to be picked up at turn boundaries

    Attributes:
        discovery: The skill discovery instance
        active_skill_names: List of persistently active skill names (durable state)
        transient_active_skill_names: List of transiently active skill names
    """

    discovery: SkillDiscovery
    active_skill_names: list[str] = field(default_factory=list)
    transient_active_skill_names: list[str] = field(default_factory=list)

    @property
    def active_skills(self) -> list[SkillPackage]:
        """
        Resolve active skills from names (on-demand resolution).

        This property re-resolves skills each time, ensuring fresh
        skill content is picked up at turn boundaries.

        Returns:
            List of resolved SkillPackage objects for active skills.
        """
        skills: list[SkillPackage] = []
        for name in self.list_active():
            skill = self.discovery.get_skill(name)
            if skill is not None:
                skill.active = True
                skills.append(skill)
            else:
                logger.warning(f"Active skill '{name}' not found during resolution")
        return skills

    def activate_skill(self, name: str, *, transient: bool = False) -> SkillPackage | None:
        """
        Activate a skill by name.

        Args:
            name: The skill name to activate.

        Returns:
            The activated SkillPackage, or None if not found.
        """
        skill = self.discovery.get_skill(name)
        if skill is None:
            logger.warning(f"Skill '{name}' not found")
            return None

        if self.is_active(name):
            logger.debug(f"Skill '{name}' already active")
            # Set active flag for the returned skill (ADR-025: on-demand resolution)
            skill.active = True
            return skill

        target = self.transient_active_skill_names if transient else self.active_skill_names
        target.append(name)
        # Set active flag for the returned skill
        skill.active = True
        kind = "transient" if transient else "persistent"
        logger.info(f"Activated {kind} skill: {name}")

        return skill

    def deactivate_skill(self, name: str) -> bool:
        """
        Deactivate a skill by name.

        Args:
            name: The skill name to deactivate.

        Returns:
            True if deactivated, False if not found.
        """
        if name in self.transient_active_skill_names:
            self.transient_active_skill_names.remove(name)
            logger.info(f"Deactivated transient skill: {name}")
            return True

        if name in self.active_skill_names:
            self.active_skill_names.remove(name)
            logger.info(f"Deactivated skill: {name}")
            return True

        logger.warning(f"Skill '{name}' not active")
        return False

    def get_active_instructions(self) -> str:
        """
        Compose instructions from all active skills.

        Instructions are composed in activation order, with later
        skills potentially overriding earlier ones. Each skill's
        instructions are wrapped in a clear section marker.

        Returns:
            Composed instruction string from all active skills.
        """
        sections: list[str] = []

        for skill in self.active_skills:  # Uses property for on-demand resolution
            # Build resource path info for assets (scripts, templates, etc.)
            resource_info = self._build_resource_info(skill)

            # Each skill's instructions are wrapped in a section
            section = f"<Skill:{skill.name}>\n{skill.instructions}"
            if resource_info:
                section += f"\n\n{resource_info}"
            section += f"\n</Skill:{skill.name}>"
            sections.append(section)

        return "\n\n".join(sections)

    def _build_resource_info(self, skill: SkillPackage) -> str:
        """
        Build resource information for a skill using skill:// URIs.

        Returns a formatted string with URIs for each resource,
        allowing the model to use skill resource tools.
        """
        if not skill.resources:
            return ""

        lines = ["## Skill Resources", ""]
        lines.append("Access resources using skill:// URIs:")
        lines.append("")

        for resource in skill.resources:
            # Compute relative path within skill
            try:
                relative_path = str(resource.path.relative_to(skill.path))
            except ValueError:
                relative_path = resource.path.name

            uri = f"skill://{skill.name}/{relative_path}"
            resource_type = resource.type
            exec_marker = " [executable]" if resource.executable else ""
            lines.append(f"- `{uri}` ({resource_type}){exec_marker}")

        lines.append("")
        lines.append("Use tools to access resources:")
        lines.append("- `read_skill_resource(uri)` - Read resource content")
        lines.append("- `execute_skill_asset(uri, args)` - Execute executable scripts")
        lines.append("- `list_skill_resources()` - List all available resources")

        return "\n".join(lines)

    def is_active(self, name: str) -> bool:
        """Check if a skill is currently active."""
        return (
            name in self.active_skill_names
            or name in self.transient_active_skill_names
        )

    def list_active(self) -> list[str]:
        """List names of all active skills."""
        return list(self.active_skill_names) + [
            name for name in self.transient_active_skill_names
            if name not in self.active_skill_names
        ]

    def list_persistent(self) -> list[str]:
        """List persistently active skill names."""
        return list(self.active_skill_names)

    def list_transient(self) -> list[str]:
        """List transiently active skill names."""
        return list(self.transient_active_skill_names)

    def clear_transient(self) -> None:
        """Deactivate all transient skills."""
        self.transient_active_skill_names.clear()
        logger.info("All transient skills deactivated")

    def clear(self) -> None:
        """Deactivate all skills."""
        self.active_skill_names.clear()
        self.transient_active_skill_names.clear()
        logger.info("All skills deactivated")


__all__ = ["SkillActivator"]
