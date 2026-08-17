"""Post-Run memory evolution orchestration."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Protocol

from quenda.evolution.memory import (
    MemoryEvolutionStore,
    MemoryProposal,
    MemoryTarget,
    MemoryWriteMode,
)
from quenda.kernel.model import Model
from quenda.kernel.types import Message
from quenda.runtime.events import AnyEvent, EvolutionCompleted
from quenda.runtime.ports.after_run import AfterRunContext


@dataclass(frozen=True)
class EvolutionTriggerConfig:
    """When the default policy should spend a separate model call."""

    every_n_user_turns: int = 5
    on_explicit_signal: bool = True

    def __post_init__(self) -> None:
        if self.every_n_user_turns <= 0:
            raise ValueError("every_n_user_turns must be positive")


class EvolutionTriggerPolicy(Protocol):
    """Choose whether one completed Run should enter evolution evaluation."""

    def should_trigger(self, context: AfterRunContext) -> bool:
        ...


class MemoryProposalGenerator(Protocol):
    """Generate zero or more complete-document proposals from Run evidence."""

    def generate(self, context: AfterRunContext) -> list[MemoryProposal]:
        ...


class DefaultEvolutionTriggerPolicy:
    """Periodic evaluation with an early path for explicit memory signals."""

    _SIGNAL = re.compile(
        r"(?i)(?:\bremember\b|\bforget\b|\bi prefer\b|\bmy preference\b|"
        r"记住|忘掉|忘记|我的偏好|我更喜欢|以后请|以后不要|纠正一下)"
    )

    def __init__(self, config: EvolutionTriggerConfig | None = None) -> None:
        self.config = config or EvolutionTriggerConfig()

    def should_trigger(self, context: AfterRunContext) -> bool:
        user_messages = [
            message
            for message in context.messages
            if message.role == "user"
        ]
        if not user_messages:
            return False
        latest = user_messages[-1]
        if (
            self.config.on_explicit_signal
            and isinstance(latest.content, str)
            and self._SIGNAL.search(latest.content)
        ):
            return True
        return len(user_messages) % self.config.every_n_user_turns == 0


class ModelMemoryProposalGenerator:
    """Use an isolated model call to propose conservative Markdown revisions."""

    def __init__(
        self,
        model: Model,
        store: MemoryEvolutionStore,
        *,
        max_proposals: int = 2,
    ) -> None:
        self.model = model
        self.store = store
        self.max_proposals = max(1, max_proposals)

    def generate(self, context: AfterRunContext) -> list[MemoryProposal]:
        current = {
            target.value: self._read_target(target)
            for target in MemoryTarget
        }
        recent = [
            {"role": message.role, "content": message.content}
            for message in context.messages[-4:]
            if isinstance(message.content, str)
            and message.role in {"user", "assistant"}
        ]
        response = self.model.invoke(
            [
                Message(
                    role="system",
                    content=(
                        "You are Quenda's conservative memory evolution evaluator. "
                        "Return JSON only. Propose a change only for stable, reusable "
                        "information supported by the conversation. Do not store secrets, "
                        "ephemeral task state, guesses, or assistant-created claims. "
                        "IDENTITY defines role/scope; SOUL defines personality/values; "
                        "USER records user preferences; CORE_MEMORY records durable facts. "
                        "Each proposal must contain the complete replacement Markdown while "
                        "preserving unrelated existing content. Schema: "
                        '{"proposals":[{"target":"core_memory|user_profile|identity|soul",'
                        '"proposed_content":"...","reason":"...","confidence":0.0}]}. '
                        f"Return at most {self.max_proposals} proposals."
                    ),
                ),
                Message(
                    role="user",
                    content=json.dumps(
                        {
                            "run_id": context.completed.run_id,
                            "current_documents": current,
                            "recent_conversation": recent,
                        },
                        ensure_ascii=False,
                    ),
                ),
            ],
            tools=[],
        )
        payload = _parse_json_object(response.content or "")
        raw_proposals = payload.get("proposals", [])
        if not isinstance(raw_proposals, list):
            raise ValueError("Evolution response proposals must be a list")

        proposals: list[MemoryProposal] = []
        for item in raw_proposals[: self.max_proposals]:
            if not isinstance(item, dict):
                continue
            target = MemoryTarget(str(item.get("target", "")))
            proposals.append(
                MemoryProposal(
                    target=target,
                    proposed_content=str(item.get("proposed_content", "")),
                    reason=str(item.get("reason", "")),
                    confidence=float(item.get("confidence", 0)),
                    expected_revision=self.store.current_revision(target),
                    source_run_id=context.completed.run_id,
                )
            )
        return proposals

    def _read_target(self, target: MemoryTarget) -> str:
        path = self.store.agent_home / target.filename
        return path.read_text(encoding="utf-8") if path.is_file() else ""


class MemoryEvolutionCoordinator:
    """Deep module joining trigger, generator, validation, policy, and storage."""

    def __init__(
        self,
        store: MemoryEvolutionStore,
        generator: MemoryProposalGenerator,
        *,
        trigger: EvolutionTriggerPolicy | None = None,
        min_confidence: float = 0.8,
    ) -> None:
        if not 0 <= min_confidence <= 1:
            raise ValueError("min_confidence must be between 0 and 1")
        self.store = store
        self.generator = generator
        self.trigger = trigger or DefaultEvolutionTriggerPolicy()
        self.min_confidence = min_confidence

    async def process(self, context: AfterRunContext) -> list[AnyEvent]:
        mode = self.store.policy.write_mode
        if mode is MemoryWriteMode.DISABLED or not self.trigger.should_trigger(context):
            return [EvolutionCompleted(triggered=False, write_mode=mode.value)]

        proposals = await asyncio.to_thread(self.generator.generate, context)
        committed = 0
        staged = 0
        rejected = 0
        for proposal in proposals:
            report = self.store.validate(proposal)
            if not report.valid or proposal.confidence < self.min_confidence:
                rejected += 1
                continue
            if mode is MemoryWriteMode.REVIEW:
                self.store.stage(proposal)
                staged += 1
                continue
            try:
                self.store.apply(proposal, actor="default-evolution-policy")
            except ValueError as exc:
                if "does not change" not in str(exc):
                    rejected += 1
                continue
            committed += 1

        return [
            EvolutionCompleted(
                triggered=True,
                write_mode=mode.value,
                proposal_count=len(proposals),
                committed_count=committed,
                staged_count=staged,
                rejected_count=rejected,
            )
        ]


def _parse_json_object(content: str) -> dict[str, object]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Evolution response did not contain a JSON object")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Evolution response must be a JSON object")
    return payload


__all__ = [
    "DefaultEvolutionTriggerPolicy",
    "EvolutionTriggerConfig",
    "EvolutionTriggerPolicy",
    "MemoryEvolutionCoordinator",
    "MemoryProposalGenerator",
    "ModelMemoryProposalGenerator",
]
