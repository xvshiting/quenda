"""Side-effect-free Agent package validation.

This module owns the validation workflow used by CLI and model-facing tools.
It parses declarations and compiles extension source, but deliberately does not
import extensions, resolve credentials, contact providers, or create sessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]

from quenda.host.loader import AgentConfigYaml, AgentPackage, load_agent_package
from quenda.host.skill import SkillDiscovery
from quenda.providers import (
    ProviderRegistry,
    build_default_api_registry,
    build_default_provider_registry,
    register_configured_providers,
)

VALIDATION_SCHEMA_VERSION = "quenda.agent-validation/v1"
_BUILTIN_TOOL_BUNDLES = frozenset({"core", "network"})
_BUILTIN_TOOL_NAMES = frozenset(
    {
        "activate_resource",
        "apply_agent_config_patch",
        "apply_patch",
        "execute_python",
        "execute_skill_asset",
        "explain_agent_config",
        "get_current_datetime",
        "http_request",
        "list_files",
        "list_skill_resources",
        "read_file",
        "read_skill_resource",
        "request_interaction",
        "request_skill_activation",
        "run_shell",
        "search_text",
        "validate_agent_package",
        "web_fetch",
        "write_file",
    }
)
_EXTENSION_DIRECTORIES = (
    "commands",
    "interactions",
    "tools",
    "context",
    "setup",
    "policies",
    "providers",
)


@dataclass(frozen=True)
class ValidationDiagnostic:
    """One stable, machine-readable validation finding."""

    code: str
    severity: Literal["error", "warning"]
    message: str
    path: str | None = None

    def to_dict(self) -> dict[str, str]:
        payload = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.path is not None:
            payload["path"] = self.path
        return payload


@dataclass(frozen=True)
class ValidationReport:
    """Complete result returned through the validation interface."""

    path: Path
    agent_name: str | None = None
    diagnostics: tuple[ValidationDiagnostic, ...] = field(default_factory=tuple)

    @property
    def error_count(self) -> int:
        return sum(item.severity == "error" for item in self.diagnostics)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "warning" for item in self.diagnostics)

    @property
    def valid(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "valid": self.valid,
            "agent": {
                "name": self.agent_name,
                "path": str(self.path),
            },
            "counts": {
                "errors": self.error_count,
                "warnings": self.warning_count,
            },
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


def validate_agent_package(
    path: Path | str,
    *,
    workspace_path: Path | str | None = None,
) -> ValidationReport:
    """Validate one Agent package without executing it or its extensions."""
    agent_dir = _resolve_agent_directory(path)
    diagnostics: list[ValidationDiagnostic] = []

    try:
        package = load_agent_package(agent_dir)
    except (FileNotFoundError, OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        diagnostics.append(
            ValidationDiagnostic(
                code="agent.invalid",
                severity="error",
                message=_safe_load_error(exc),
                path=str(agent_dir),
            )
        )
        return ValidationReport(agent_dir, diagnostics=tuple(diagnostics))

    return _validate_loaded_package(
        package,
        workspace_path=workspace_path,
        diagnostics=diagnostics,
    )


def validate_agent_configuration(
    path: Path | str,
    config_data: dict[str, Any],
    *,
    workspace_path: Path | str | None = None,
) -> ValidationReport:
    """Validate candidate config data against an existing Agent package."""
    agent_dir = _resolve_agent_directory(path)
    diagnostics: list[ValidationDiagnostic] = []
    try:
        package = load_agent_package(agent_dir)
        package = replace(package, config=AgentConfigYaml.from_dict(config_data))
    except (FileNotFoundError, OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        diagnostics.append(
            ValidationDiagnostic(
                code="agent.invalid",
                severity="error",
                message=_safe_load_error(exc),
                path=str(agent_dir / "config.yaml"),
            )
        )
        return ValidationReport(agent_dir, diagnostics=tuple(diagnostics))

    return _validate_loaded_package(
        package,
        workspace_path=workspace_path,
        diagnostics=diagnostics,
    )


def _validate_loaded_package(
    package: AgentPackage,
    *,
    workspace_path: Path | str | None,
    diagnostics: list[ValidationDiagnostic],
) -> ValidationReport:
    """Run the canonical validators for one already parsed package."""
    _validate_instructions(package, diagnostics)
    registry = _validate_providers(package, diagnostics)
    _validate_models(package, registry, diagnostics)
    _validate_skills(
        package,
        Path(workspace_path).expanduser().resolve()
        if workspace_path is not None
        else package.path,
        diagnostics,
    )
    _validate_execution(package, diagnostics)
    _validate_evolution(package, diagnostics)
    _validate_tool_declarations(package, diagnostics)
    _validate_extension_syntax(package, diagnostics)

    return ValidationReport(
        path=package.path,
        agent_name=package.name,
        diagnostics=tuple(diagnostics),
    )


def _resolve_agent_directory(path: Path | str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if resolved.is_file() and resolved.name == "AGENT.md":
        return resolved.parent
    return resolved


def _validate_instructions(
    package: AgentPackage,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    config = package.config
    if config is None:
        return
    for relative in config.instructions_include:
        instruction = package.path / relative
        if not instruction.is_file():
            diagnostics.append(
                ValidationDiagnostic(
                    code="instruction.missing",
                    severity="error",
                    message=f"Configured instruction does not exist: {relative}",
                    path=str(instruction),
                )
            )


def _validate_providers(
    package: AgentPackage,
    diagnostics: list[ValidationDiagnostic],
) -> ProviderRegistry:
    api_registry = build_default_api_registry()
    registry = build_default_provider_registry(api_registry=api_registry)
    config = package.config
    configured_ids = {provider.id for provider in config.providers} if config else set()

    if config and config.providers:
        try:
            register_configured_providers(config.providers, registry)
        except ValueError as exc:
            diagnostics.append(
                ValidationDiagnostic(
                    code="provider.invalid",
                    severity="error",
                    message=str(exc),
                    path=str(package.path / "config.yaml"),
                )
            )

    for provider_id in sorted(configured_ids):
        spec = registry.get_spec(provider_id)
        if spec is None:
            continue
        protocols = {spec.api, *(model.api for model in spec.models if model.api)}
        for protocol in sorted(protocols):
            if not api_registry.has(protocol):
                diagnostics.append(
                    ValidationDiagnostic(
                        code="provider_api.unknown",
                        severity="error",
                        message=(
                            f"Provider {provider_id!r} selects unknown API protocol "
                            f"{protocol!r}"
                        ),
                        path=str(package.path / "config.yaml"),
                    )
                )
    return registry


def _validate_models(
    package: AgentPackage,
    registry: ProviderRegistry,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    config = package.config
    roles = config.models if config else None
    provider_extensions = list((package.path / "extensions" / "providers").glob("*.py"))

    role_values = {
        "default": roles.default if roles else None,
        "vision": roles.vision if roles else None,
    }
    if role_values["default"] is None:
        diagnostics.append(
            ValidationDiagnostic(
                code="model.default_implicit",
                severity="warning",
                message="No default model is declared; runtime compatibility defaults apply",
                path=str(package.path / "config.yaml"),
            )
        )

    for role_name, role in role_values.items():
        if role is None:
            continue
        try:
            model = registry.get_model(role.provider, role.model)
        except KeyError:
            if provider_extensions:
                diagnostics.append(
                    ValidationDiagnostic(
                        code="model.deferred_extension",
                        severity="warning",
                        message=(
                            f"Model role {role_name!r} references "
                            f"{role.provider}/{role.model}; provider extensions are not "
                            "executed by static validation"
                        ),
                        path=str(package.path / "config.yaml"),
                    )
                )
            else:
                diagnostics.append(
                    ValidationDiagnostic(
                        code="model.not_found",
                        severity="error",
                        message=(
                            f"Model role {role_name!r} references unknown model "
                            f"{role.provider}/{role.model}"
                        ),
                        path=str(package.path / "config.yaml"),
                    )
                )
            continue
        if role_name == "vision" and not model.spec.vision:
            diagnostics.append(
                ValidationDiagnostic(
                    code="vision.unsupported",
                    severity="error",
                    message=(
                        f"Vision role references {role.provider}/{role.model}, "
                        "which is not declared vision-capable"
                    ),
                    path=str(package.path / "config.yaml"),
                )
            )


def _validate_skills(
    package: AgentPackage,
    workspace_path: Path,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    config = package.config
    if config is None or not config.skills:
        return
    discovery = SkillDiscovery(
        workspace_path=workspace_path,
        agent_package_path=package.path,
    )
    available = {skill.name for skill in discovery.discover_skills()}
    for skill_name in config.skills:
        if skill_name not in available:
            diagnostics.append(
                ValidationDiagnostic(
                    code="skill.not_found",
                    severity="error",
                    message=f"Configured Skill is not discoverable: {skill_name}",
                    path=str(package.path / "config.yaml"),
                )
            )


def _validate_tool_declarations(
    package: AgentPackage,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    config = package.config
    if config is None:
        return
    for bundle in sorted(set(config.tools.bundles) - _BUILTIN_TOOL_BUNDLES):
        diagnostics.append(
            ValidationDiagnostic(
                code="tool_bundle.unknown",
                severity="error",
                message=f"Unknown framework tool bundle: {bundle}",
                path=str(package.path / "config.yaml"),
            )
        )
    extension_sources = list((package.path / "extensions" / "tools").glob("*.py"))
    for tool_name in sorted(set(config.tools.include) - _BUILTIN_TOOL_NAMES):
        if extension_sources:
            diagnostics.append(
                ValidationDiagnostic(
                    code="tool.deferred_extension",
                    severity="warning",
                    message=(
                        f"Tool {tool_name!r} is not built in; static validation does "
                        "not execute tool extensions"
                    ),
                    path=str(package.path / "config.yaml"),
                )
            )
        else:
            diagnostics.append(
                ValidationDiagnostic(
                    code="tool.not_found",
                    severity="error",
                    message=f"Configured Tool is not available: {tool_name}",
                    path=str(package.path / "config.yaml"),
                )
            )


def _validate_execution(
    package: AgentPackage,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    config = package.config
    if config is None:
        return
    backend = config.execution.backend.strip() or "local-trusted"
    config_path = str(package.path / "config.yaml")
    if backend != "local-trusted":
        diagnostics.append(
            ValidationDiagnostic(
                code="execution.backend_unavailable",
                severity="error",
                message=(
                    f"Execution backend {backend!r} is unavailable; this Host "
                    "currently provides only 'local-trusted'"
                ),
                path=config_path,
            )
        )
        return
    if config.execution.requires_isolation:
        diagnostics.append(
            ValidationDiagnostic(
                code="execution.isolation_unavailable",
                severity="error",
                message=(
                    "Execution backend 'local-trusted' does not provide strong "
                    "filesystem or network isolation"
                ),
                path=config_path,
            )
        )


def _validate_evolution(
    package: AgentPackage,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    config = package.config
    if config is None:
        return
    evolution = config.evolution
    path = str(package.path / "config.yaml")
    if evolution.write_mode not in {"automatic", "review", "disabled"}:
        diagnostics.append(
            ValidationDiagnostic(
                code="evolution.write_mode_invalid",
                severity="error",
                message=(
                    "evolution.write_mode must be automatic, review, or disabled"
                ),
                path=path,
            )
        )
    for field_name, value in (
        ("every_n_user_turns", evolution.every_n_user_turns),
        ("max_proposals", evolution.max_proposals),
    ):
        if value <= 0:
            diagnostics.append(
                ValidationDiagnostic(
                    code=f"evolution.{field_name}_invalid",
                    severity="error",
                    message=f"evolution.{field_name} must be positive",
                    path=path,
                )
            )
    if not 0 <= evolution.min_confidence <= 1:
        diagnostics.append(
            ValidationDiagnostic(
                code="evolution.min_confidence_invalid",
                severity="error",
                message="evolution.min_confidence must be between 0 and 1",
                path=path,
            )
        )


def _validate_extension_syntax(
    package: AgentPackage,
    diagnostics: list[ValidationDiagnostic],
) -> None:
    extensions = package.path / "extensions"
    for directory in _EXTENSION_DIRECTORIES:
        for source in sorted((extensions / directory).glob("*.py")):
            if source.name.startswith("_"):
                continue
            try:
                content = source.read_text(encoding="utf-8")
                compile(content, str(source), "exec")
            except (OSError, UnicodeError, SyntaxError) as exc:
                diagnostics.append(
                    ValidationDiagnostic(
                        code="extension.syntax",
                        severity="error",
                        message=_safe_compile_error(exc),
                        path=str(source),
                    )
                )


def _safe_load_error(error: Exception) -> str:
    """Describe a load failure without echoing source lines or credentials."""
    problem = getattr(error, "problem", None)
    mark = getattr(error, "problem_mark", None)
    if isinstance(problem, str):
        location = ""
        if mark is not None:
            location = f" at line {mark.line + 1}, column {mark.column + 1}"
        return f"config.yaml is invalid: {problem}{location}"
    return str(error)


def _safe_compile_error(error: Exception) -> str:
    """Describe extension compilation without including the offending source."""
    if isinstance(error, SyntaxError):
        location = ""
        if error.lineno is not None:
            location = f" at line {error.lineno}"
            if error.offset is not None:
                location += f", column {error.offset}"
        return f"Extension cannot be compiled: {error.msg}{location}"
    return f"Extension cannot be compiled: {type(error).__name__}"


__all__ = [
    "VALIDATION_SCHEMA_VERSION",
    "ValidationDiagnostic",
    "ValidationReport",
    "validate_agent_configuration",
    "validate_agent_package",
]
