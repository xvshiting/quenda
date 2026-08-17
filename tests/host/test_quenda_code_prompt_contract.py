"""Contract tests for Quenda Code's layered coding instructions."""

from pathlib import Path

from quenda.host.loader import find_builtin_agent, load_agent_package


def _agent_path() -> Path:
    path = find_builtin_agent("quenda-code")
    assert path is not None
    return path


def test_quenda_code_keeps_general_and_mode_specific_rules_separate() -> None:
    package = load_agent_package(_agent_path())
    instructions = {source.path.name: source.content for source in package.instructions}

    coding = instructions["coding.md"]
    mode_code = (_agent_path() / "instructions" / "mode-code.md").read_text(
        encoding="utf-8"
    )

    assert "Before calling an internal function" in coding
    assert "Never invent an API" in coding
    assert "Read the smallest relevant line range first" in coding
    assert "After each meaningful increment" in coding
    assert "Definition of Done" not in coding

    assert "## Definition of Done" in mode_code
    assert "**API verification**" in mode_code
    assert "**Behavior verification**" in mode_code
    assert "**Project checks**" in mode_code
    assert "**Placeholder scan**" in mode_code
    assert "最小语义增量" in mode_code
    assert "不把所有验证推迟到最后" in mode_code


def test_quenda_code_requires_evidence_before_claiming_completion() -> None:
    agent_md = (_agent_path() / "AGENT.md").read_text(encoding="utf-8")
    mode_code = (_agent_path() / "instructions" / "mode-code.md").read_text(
        encoding="utf-8"
    )

    assert "Evidence over confidence" in agent_md
    assert "is incomplete and report the remaining evidence" in agent_md
    assert "不得使用“已完成”“完整实现”" in mode_code
    assert "异步任务、事件流、暂停恢复、取消或持久化" in mode_code


def test_quenda_code_base_prompt_omits_unrelated_data_collection_example() -> None:
    agent_md = (_agent_path() / "AGENT.md").read_text(encoding="utf-8")

    assert "Market is up" not in agent_md
    assert "indices, sectors, stocks" not in agent_md


def test_quenda_code_context_guidance_matches_host_behavior() -> None:
    package = load_agent_package(_agent_path())
    instructions = {source.path.name: source.content for source in package.instructions}

    context = instructions["context-injection.md"]
    runtime = instructions["runtime-info.md"]

    assert "default filename is `QUENDA.md`" in context
    assert "`IDENTITY.md`, `SOUL.md`, `USER.md`, and `MEMORY.md`" in context
    assert "20,000" not in context
    assert "60,000" not in context
    assert "host name" in runtime
    assert "do not infer unavailable details" in runtime


def test_quenda_code_tool_guidance_uses_current_filesystem_schema() -> None:
    package = load_agent_package(_agent_path())
    instructions = {source.path.name: source.content for source in package.instructions}
    guidance = instructions["tool-best-practices.md"]

    assert "list_files(path, depth, pattern)" in guidance
    assert "read_file(path, start, end)" in guidance
    assert "offset" not in guidance
    assert "recursive" not in guidance
    assert len(guidance) < 5_000
