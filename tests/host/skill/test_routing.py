"""Tests for host-side skill routing helpers."""

from quenda.host.skill.routing import (
    build_skill_activation_followup,
    extract_skill_activation_requests,
    resolve_skill_activation_requests,
)
from quenda.runtime.events import ModelResponded


class TestExtractSkillActivationRequests:
    """Tests for extracting skill activation requests from events."""

    def test_extracts_matching_tool_calls(self) -> None:
        events = [
            ModelResponded(
                content="",
                tool_calls=["call_1", "call_2"],
                tool_call_details=[
                    {
                        "id": "call_1",
                        "name": "request_skill_activation",
                        "arguments": {"skill_name": "code-review"},
                    },
                    {
                        "id": "call_2",
                        "name": "read_file",
                        "arguments": {"path": "notes.md"},
                    },
                ],
                tool_arguments=[{"skill_name": "code-review"}, {"path": "notes.md"}],
            )
        ]

        requests = extract_skill_activation_requests(events)

        assert requests == [{"skill_name": "code-review"}]


class TestBuildSkillActivationFollowup:
    """Tests for continuation text generation."""

    def test_includes_context_and_guardrails(self) -> None:
        followup = build_skill_activation_followup(
            requested=["code-review"],
            activated=["code-review"],
            unavailable=[],
            already_active=[],
            original_user_message="Review this patch.",
        )

        assert "Activated skills: code-review." in followup
        assert "do not acknowledge this note" in followup
        assert "Original user request: Review this patch." in followup


class TestResolveSkillActivationRequests:
    """Tests for structured skill activation resolution."""

    def test_resolves_available_skill(self) -> None:
        activated_names: list[str] = []

        def activate(skill_names: list[str]) -> list[str]:
            activated_names.extend(skill_names)
            return skill_names

        resolution = resolve_skill_activation_requests(
            [{"skill_name": "code-review"}],
            available_skill_names={"code-review"},
            active_skill_names=set(),
            activate=activate,
            original_user_message="Please review this code.",
        )

        assert resolution.requested == ["code-review"]
        assert resolution.activated == ["code-review"]
        assert resolution.unavailable == []
        assert resolution.already_active == []
        assert resolution.followup_message is not None
        assert activated_names == ["code-review"]

    def test_ignores_empty_requests(self) -> None:
        resolution = resolve_skill_activation_requests(
            [{"skill_name": "   "}],
            available_skill_names={"code-review"},
            active_skill_names=set(),
            activate=lambda names: names,
            original_user_message="Hello",
        )

        assert resolution.requested == []
        assert resolution.followup_message is None
