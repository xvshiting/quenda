"""Canonical, side-effect-free prompt assembly for the Host layer.

The assembler deliberately does not resolve files or discover skills. It keeps
relative order within each residency class, then moves more volatile classes to
the tail so changing Run context cannot invalidate stable Agent instructions.
Instruction authority remains explicit metadata rather than relying on textual
position.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path

from quenda.host.instructions import (
    FRAMEWORK_CONTRACT,
    InstructionComposer,
    InstructionScope,
    InstructionSource,
    TemplateContext,
)
from quenda.runtime.events import PromptCacheObserved
from quenda.runtime.token_estimator import TokenEstimator


class PromptResidency(StrEnum):
    """How long a prompt segment is expected to remain applicable."""

    BINDING = "binding"
    SESSION = "session"
    ACTIVATION = "activation"
    RUN = "run"


class PromptTrust(StrEnum):
    """The authority family that supplied a prompt segment."""

    FRAMEWORK = "framework"
    AGENT = "agent"
    USER = "user"
    RETRIEVED = "retrieved"


class PromptChangeReason(StrEnum):
    """Why an assembly stopped sharing a prefix with its predecessor."""

    CONTENT_CHANGED = "content_changed"
    SOURCE_ADDED = "source_added"
    SOURCE_REMOVED = "source_removed"
    ORDER_CHANGED = "order_changed"


@dataclass(frozen=True)
class PromptSegment:
    """One rendered prompt segment with cache-safe identity metadata."""

    source_id: str
    scope: InstructionScope
    residency: PromptResidency
    trust: PromptTrust
    content: str
    digest: str
    path: Path | None = None


@dataclass(frozen=True)
class PromptAssembly:
    """Rendered prompt and its ordered, inspectable segment manifest."""

    segments: tuple[PromptSegment, ...]
    composed_prompt: str
    digest: str
    stable_prefix_segment_count: int
    stable_prefix_digest: str

    def diff(self, previous: PromptAssembly) -> PromptInvalidation | None:
        """Return the first cache-relevant change from ``previous`` to self."""
        if self.digest == previous.digest:
            return None

        current_ids = {segment.source_id for segment in self.segments}
        previous_ids = {segment.source_id for segment in previous.segments}
        shared_length = min(len(self.segments), len(previous.segments))

        for index in range(shared_length):
            current = self.segments[index]
            old = previous.segments[index]
            if current.source_id == old.source_id:
                if current.digest != old.digest:
                    return PromptInvalidation(
                        source_id=current.source_id,
                        first_changed_index=index,
                        reused_prefix_segment_count=index,
                        reason=PromptChangeReason.CONTENT_CHANGED,
                    )
                continue

            if current.source_id not in previous_ids:
                reason = PromptChangeReason.SOURCE_ADDED
                source_id = current.source_id
            elif old.source_id not in current_ids:
                reason = PromptChangeReason.SOURCE_REMOVED
                source_id = old.source_id
            else:
                reason = PromptChangeReason.ORDER_CHANGED
                source_id = current.source_id
            return PromptInvalidation(
                source_id=source_id,
                first_changed_index=index,
                reused_prefix_segment_count=index,
                reason=reason,
            )

        index = shared_length
        if len(self.segments) > len(previous.segments):
            return PromptInvalidation(
                source_id=self.segments[index].source_id,
                first_changed_index=index,
                reused_prefix_segment_count=index,
                reason=PromptChangeReason.SOURCE_ADDED,
            )
        return PromptInvalidation(
            source_id=previous.segments[index].source_id,
            first_changed_index=index,
            reused_prefix_segment_count=index,
            reason=PromptChangeReason.SOURCE_REMOVED,
        )

    def observe(
        self,
        previous: PromptAssembly | None = None,
    ) -> PromptCacheObservation:
        """Build content-free cache telemetry for this prompt snapshot."""
        invalidation = self.diff(previous) if previous is not None else None
        if previous is None:
            reused_count = 0
        elif invalidation is None:
            reused_count = len(self.segments)
        else:
            reused_count = invalidation.reused_prefix_segment_count

        estimator = TokenEstimator()
        stable_content = "\n\n".join(
            segment.content
            for segment in self.segments[: self.stable_prefix_segment_count]
        )
        reused_content = "\n\n".join(
            segment.content for segment in self.segments[:reused_count]
        )
        return PromptCacheObservation(
            assembly_digest=self.digest,
            stable_prefix_digest=self.stable_prefix_digest,
            segment_count=len(self.segments),
            stable_prefix_segment_count=self.stable_prefix_segment_count,
            reused_prefix_segment_count=reused_count,
            estimated_prompt_tokens=estimator.estimate_text(self.composed_prompt),
            estimated_stable_prefix_tokens=estimator.estimate_text(stable_content),
            estimated_reused_prefix_tokens=estimator.estimate_text(reused_content),
            first_changed_source_id=(
                invalidation.source_id if invalidation is not None else None
            ),
            change_reason=(
                invalidation.reason if invalidation is not None else None
            ),
        )


@dataclass(frozen=True)
class PromptInvalidation:
    """The first segment that invalidates reuse of an earlier prompt prefix."""

    source_id: str
    first_changed_index: int
    reused_prefix_segment_count: int
    reason: PromptChangeReason


@dataclass(frozen=True)
class PromptCacheObservation:
    """Content-free estimate of prompt-prefix reuse between two snapshots."""

    assembly_digest: str
    stable_prefix_digest: str
    segment_count: int
    stable_prefix_segment_count: int
    reused_prefix_segment_count: int
    estimated_prompt_tokens: int
    estimated_stable_prefix_tokens: int
    estimated_reused_prefix_tokens: int
    first_changed_source_id: str | None = None
    change_reason: PromptChangeReason | None = None


def build_prompt_cache_event(
    observation: PromptCacheObservation,
    *,
    run_id: str = "",
) -> PromptCacheObserved:
    """Convert cache telemetry to the shared content-free event contract."""
    return PromptCacheObserved(
        run_id=run_id,
        assembly_digest=observation.assembly_digest,
        stable_prefix_digest=observation.stable_prefix_digest,
        segment_count=observation.segment_count,
        stable_prefix_segment_count=observation.stable_prefix_segment_count,
        reused_prefix_segment_count=observation.reused_prefix_segment_count,
        estimated_prompt_tokens=observation.estimated_prompt_tokens,
        estimated_stable_prefix_tokens=observation.estimated_stable_prefix_tokens,
        estimated_reused_prefix_tokens=observation.estimated_reused_prefix_tokens,
        first_changed_source_id=observation.first_changed_source_id,
        change_reason=(
            observation.change_reason.value
            if observation.change_reason is not None
            else None
        ),
    )


class PromptAssembler:
    """Render ordered instruction sources into a canonical prompt assembly."""

    def assemble(
        self,
        sources: Sequence[InstructionSource],
        context: TemplateContext,
    ) -> PromptAssembly:
        composer = InstructionComposer(context)
        anonymous_counts: dict[InstructionScope, int] = {}
        segments: list[PromptSegment] = []

        for source in sources:
            rendered = composer.render_template(source.content)
            if not rendered.strip():
                continue

            source_id = _source_id(source, anonymous_counts)
            segments.append(
                PromptSegment(
                    source_id=source_id,
                    scope=source.scope,
                    residency=_residency(source),
                    trust=_trust(source.scope),
                    content=rendered,
                    digest=_text_digest(rendered),
                    path=source.path,
                )
            )

        residency_order = {
            PromptResidency.BINDING: 0,
            PromptResidency.SESSION: 1,
            PromptResidency.ACTIVATION: 2,
            PromptResidency.RUN: 3,
        }
        segments.sort(key=lambda segment: residency_order[segment.residency])

        stable_prefix_count = next(
            (
                index
                for index, segment in enumerate(segments)
                if segment.residency is PromptResidency.RUN
            ),
            len(segments),
        )
        segment_tuple = tuple(segments)
        return PromptAssembly(
            segments=segment_tuple,
            composed_prompt="\n\n".join(segment.content for segment in segments),
            digest=_manifest_digest(segment_tuple),
            stable_prefix_segment_count=stable_prefix_count,
            stable_prefix_digest=_manifest_digest(
                segment_tuple[:stable_prefix_count]
            ),
        )


def _source_id(
    source: InstructionSource,
    anonymous_counts: dict[InstructionScope, int],
) -> str:
    stripped = source.content.lstrip()
    if source.scope is InstructionScope.FRAMEWORK:
        if source.content.strip() == FRAMEWORK_CONTRACT.strip():
            return "framework:contract"
        if stripped.startswith(("## Current Environment", "## Current Temporal Context")):
            return "runtime:temporal"
        if stripped.startswith("## Current Agent Identity"):
            return "framework:agent-identity"

    if source.path is not None:
        return f"{source.scope.name.lower()}:{source.path.expanduser().resolve()}"

    count = anonymous_counts.get(source.scope, 0)
    anonymous_counts[source.scope] = count + 1
    return f"{source.scope.name.lower()}:anonymous:{count}"


def _residency(source: InstructionSource) -> PromptResidency:
    stripped = source.content.lstrip()
    if stripped.startswith(("## Current Environment", "## Current Temporal Context")):
        return PromptResidency.RUN
    if stripped.startswith("## Current Agent Identity"):
        return PromptResidency.SESSION
    if source.scope is InstructionScope.SKILL:
        return PromptResidency.ACTIVATION
    if source.scope in {
        InstructionScope.USER_GLOBAL,
        InstructionScope.USER_AGENT,
        InstructionScope.WORKSPACE,
        InstructionScope.WORKSPACE_AGENT,
        InstructionScope.USER_WORKSPACE,
    }:
        return PromptResidency.SESSION
    if source.path is not None and source.path.name.startswith("mode-"):
        return PromptResidency.SESSION
    return PromptResidency.BINDING


def _trust(scope: InstructionScope) -> PromptTrust:
    if scope is InstructionScope.FRAMEWORK:
        return PromptTrust.FRAMEWORK
    if scope in {
        InstructionScope.AGENT_PACKAGE,
        InstructionScope.AGENT_INSTRUCTIONS,
        InstructionScope.SKILL,
    }:
        return PromptTrust.AGENT
    return PromptTrust.USER


def _text_digest(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def _manifest_digest(segments: Sequence[PromptSegment]) -> str:
    digest = sha256(b"quenda-prompt-assembly-v1\0")
    for segment in segments:
        digest.update(segment.source_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(segment.digest.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


__all__ = [
    "PromptAssembler",
    "PromptAssembly",
    "PromptCacheObservation",
    "PromptChangeReason",
    "PromptInvalidation",
    "PromptResidency",
    "PromptSegment",
    "PromptTrust",
    "build_prompt_cache_event",
]
