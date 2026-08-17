"""Behavioral tests for the canonical prompt assembly seam."""

from __future__ import annotations

from pathlib import Path

from quenda.host import (
    ContextRebuilder,
    InstructionScope,
    InstructionSource,
    PromptAssembler,
    PromptChangeReason,
    PromptResidency,
    TemplateContext,
    User,
)
from quenda.host.instructions import FRAMEWORK_CONTRACT


def _template_context() -> TemplateContext:
    return TemplateContext(
        agent_name="test-agent",
        agent_version="1.0.0",
        workspace_id="ws_test",
        workspace_path="/tmp/workspace",
        user_id="user-test",
        model_provider="test-provider",
        model_name="test-model",
        date="2026-08-14",
        session_id="session-test",
        mode="chat",
    )


def test_assembly_preserves_segment_identity_when_content_changes(
    tmp_path: Path,
) -> None:
    """A content revision invalidates only that segment's digest and assembly."""
    first_path = tmp_path / "AGENT.md"
    second_path = tmp_path / "instructions" / "style.md"
    first = InstructionSource(
        scope=InstructionScope.AGENT_PACKAGE,
        content="Agent: {{agent.name}}",
        path=first_path,
    )
    second = InstructionSource(
        scope=InstructionScope.AGENT_INSTRUCTIONS,
        content="Prefer concise output.",
        path=second_path,
    )

    assembler = PromptAssembler()
    original = assembler.assemble([first, second], _template_context())
    revised = assembler.assemble(
        [
            first,
            InstructionSource(
                scope=second.scope,
                content="Prefer detailed output.",
                path=second.path,
            ),
        ],
        _template_context(),
    )

    assert [segment.source_id for segment in original.segments] == [
        segment.source_id for segment in revised.segments
    ]
    assert original.segments[0].digest == revised.segments[0].digest
    assert original.segments[1].digest != revised.segments[1].digest
    assert original.digest != revised.digest
    assert original.composed_prompt == "Agent: test-agent\n\nPrefer concise output."

    invalidation = revised.diff(original)
    assert invalidation is not None
    assert invalidation.reason is PromptChangeReason.CONTENT_CHANGED
    assert invalidation.source_id == original.segments[1].source_id
    assert invalidation.first_changed_index == 1
    assert invalidation.reused_prefix_segment_count == 1


def test_assembly_moves_run_dynamic_segments_behind_stable_prefix() -> None:
    """Volatile time context cannot invalidate later Agent instructions."""
    sources = [
        InstructionSource(
            scope=InstructionScope.FRAMEWORK,
            content=FRAMEWORK_CONTRACT,
        ),
        InstructionSource(
            scope=InstructionScope.FRAMEWORK,
            content="## Current Temporal Context\nCurrent local date: 2026-08-14",
        ),
        InstructionSource(
            scope=InstructionScope.AGENT_PACKAGE,
            content="Agent instructions.",
            path=Path("/tmp/agent/AGENT.md"),
        ),
    ]

    assembly = PromptAssembler().assemble(sources, _template_context())

    assert [segment.residency for segment in assembly.segments] == [
        PromptResidency.BINDING,
        PromptResidency.BINDING,
        PromptResidency.RUN,
    ]
    assert assembly.stable_prefix_segment_count == 2
    assert assembly.segments[0].source_id == "framework:contract"
    assert assembly.segments[1].source_id.endswith("/tmp/agent/AGENT.md")
    assert assembly.segments[2].source_id == "runtime:temporal"


def test_context_rebuilder_returns_the_same_canonical_assembly() -> None:
    """The compatibility string API is a view over the assembly API."""
    rebuilder = ContextRebuilder(
        agent_name="test-agent",
        agent_version="1.0.0",
        agent_md_content="Agent {{agent.name}} on {{model.name}}.",
        agent_instructions=[],
        agent_package_path=Path("/tmp/test-agent"),
        workspace_path=Path("/tmp/workspace"),
        workspace_id="ws_test",
        user=User(id="test-user"),
    )

    assembly = rebuilder.rebuild_assembly(
        provider="test-provider",
        model="test-model",
        session_id="session-test",
    )
    prompt = rebuilder.rebuild(
        provider="test-provider",
        model="test-model",
        session_id="session-test",
    )

    assert prompt == assembly.composed_prompt
    assert assembly.segments


def test_cache_observation_reports_reused_prefix_without_prompt_content() -> None:
    sources = [
        InstructionSource(
            scope=InstructionScope.FRAMEWORK,
            content=FRAMEWORK_CONTRACT,
        ),
        InstructionSource(
            scope=InstructionScope.AGENT_PACKAGE,
            content="Private agent instructions.",
            path=Path("/tmp/agent/AGENT.md"),
        ),
    ]
    assembler = PromptAssembler()
    original = assembler.assemble(sources, _template_context())
    unchanged = assembler.assemble(sources, _template_context())

    observation = unchanged.observe(original)

    assert observation.reused_prefix_segment_count == len(unchanged.segments)
    assert observation.first_changed_source_id is None
    assert observation.change_reason is None
    assert observation.estimated_reused_prefix_tokens > 0
    assert "Private agent instructions" not in repr(observation)


def test_cache_observation_identifies_first_changed_segment() -> None:
    stable = InstructionSource(
        scope=InstructionScope.FRAMEWORK,
        content=FRAMEWORK_CONTRACT,
    )
    agent_path = Path("/tmp/agent/AGENT.md")
    assembler = PromptAssembler()
    original = assembler.assemble(
        [
            stable,
            InstructionSource(
                scope=InstructionScope.AGENT_PACKAGE,
                content="Original.",
                path=agent_path,
            ),
        ],
        _template_context(),
    )
    revised = assembler.assemble(
        [
            stable,
            InstructionSource(
                scope=InstructionScope.AGENT_PACKAGE,
                content="Revised.",
                path=agent_path,
            ),
        ],
        _template_context(),
    )

    observation = revised.observe(original)

    assert observation.reused_prefix_segment_count == 1
    assert observation.first_changed_source_id == original.segments[1].source_id
    assert observation.change_reason is PromptChangeReason.CONTENT_CHANGED
