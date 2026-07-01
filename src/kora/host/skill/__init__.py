"""
Skills - Host-level capability packages.

Skills are composable instruction packages that can be activated
to modify agent behavior. They differ from tools in that they
provide instructions, references, and resources rather than
executable functions.

Skill = instructions + resource catalog + optional tools + optional policy metadata

This module provides:
- SkillFrontmatter: Pydantic model for SKILL.md parsing
- SkillPackage: Dataclass for loaded skill
- SkillDiscovery: Finding and loading skills from configured paths
- SkillActivator: Managing active skills and composing instructions
- ResourceResolver: Loading and resolving skill resources

Usage:
    from kora.host.skill import SkillDiscovery, SkillActivator, ResourceResolver

    discovery = SkillDiscovery(workspace_path)
    activator = SkillActivator(discovery)

    # Discover available skills
    skills = discovery.discover_skills()

    # Activate a skill
    activator.activate_skill("code-review")

    # Get composed instructions from active skills
    instructions = activator.get_active_instructions()

    # Access resources
    resolver = ResourceResolver(activator.active_skills)
    content = resolver.load_resource("code-review", "checklist.md")
"""

from kora.host.skill.models import (
    ActivationTrigger,
    AssetReference,
    ResourceCatalog,
    ResourceReference,
    SkillFrontmatter,
    SkillKoraMetadata,
    ToolRequirements,
    TrustMetadata,
)
from kora.host.skill.package import SkillPackage, SkillResource
from kora.host.skill.discovery import SkillDiscovery
from kora.host.skill.activation import SkillActivator
from kora.host.skill.routing import (
    SkillActivationResolution,
    build_skill_activation_followup,
    extract_skill_activation_requests,
    resolve_skill_activation_requests,
)
from kora.host.skill.resources import (
    ResourceInfo,
    LoadedResource,
    ResourceResolver,
)

__all__ = [
    # Models
    "ActivationTrigger",
    "AssetReference",
    "ResourceCatalog",
    "ResourceReference",
    "SkillFrontmatter",
    "SkillKoraMetadata",
    "ToolRequirements",
    "TrustMetadata",
    # Package
    "SkillPackage",
    "SkillResource",
    # Discovery
    "SkillDiscovery",
    # Activation
    "SkillActivator",
    "SkillActivationResolution",
    "extract_skill_activation_requests",
    "build_skill_activation_followup",
    "resolve_skill_activation_requests",
    # Resources
    "ResourceInfo",
    "LoadedResource",
    "ResourceResolver",
]
