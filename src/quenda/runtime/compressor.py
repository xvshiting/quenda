"""
Compressor for Quenda Runtime.

This module provides the compression mechanism that Runtime uses
to compress session history when Host policy decides compression is needed.

Key principle: Runtime executes compression, Host decides when.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

from quenda.kernel.types import Message, ToolCall, ToolResult

if TYPE_CHECKING:
    from quenda.kernel.model import Model
    from quenda.host.storage import Storage
    from quenda.runtime.compression import CompressionDecision, CompressionResult
    from quenda.runtime.session import SessionState


# System prompt for summarization
SUMMARY_SYSTEM_PROMPT = """你是一个对话摘要助手。你的任务是将长对话压缩为简洁但信息丰富的摘要。

摘要要求：
- 保留所有关键信息，不遗漏重要决策
- 使用简洁的语言，避免冗余
- 保持时间顺序的逻辑性
- 标注重要的代码片段或文件名
- 记录错误和解决方案

摘要格式：
## 用户目标
...

## 已完成的工作
...

## 重要决策
...

## 待办事项
...

## 已知问题
..."""


class Compressor(Protocol):
    """
    Runtime-facing compression contract.

    Runtime calls this with the session state and Host decision,
    and the compressor returns the compression result.
    """

    def compress(
        self,
        session: SessionState,
        decision: CompressionDecision,
    ) -> CompressionResult:
        """
        Execute compression on the session.

        Args:
            session: The session state to compress.
            decision: The Host-provided compression decision.

        Returns:
            CompressionResult with summary and archive info.
        """
        ...


class SummarizerCompressor:
    """
    LLM-based summarization compressor.

    Uses a model to generate summaries of older conversation history.
    The summary preserves key information while reducing token count.
    """

    def __init__(
        self,
        model: Model,
        storage: Storage | None = None,
    ) -> None:
        """
        Initialize the summarizer compressor.

        Args:
            model: The model to use for summarization.
            storage: Optional storage for archiving raw messages.
        """
        self.model = model
        self.storage = storage

    def compress(
        self,
        session: SessionState,
        decision: CompressionDecision,
    ) -> CompressionResult:
        """
        Compress session history using LLM summarization.

        Args:
            session: The session state to compress.
            decision: The Host-provided compression decision.

        Returns:
            CompressionResult with summary message and archive refs.
        """
        from quenda.kernel import Kernel
        from quenda.kernel.types import Message
        from quenda.runtime.compression import CompressionResult
        from quenda.runtime.token_estimator import TokenEstimator

        # 1. Check if compression is needed
        if len(session.messages) <= decision.keep_last_n_messages:
            # Nothing to compress
            return CompressionResult(
                summary_messages=[],
                archived_message_count=0,
                archive_refs=[],
                summary_token_count=0,
            )

        # 2. Find valid split point
        # We need to ensure remaining messages form a valid sequence:
        # - Cannot start with tool results (must follow tool calls)
        # - Cannot have orphaned tool calls (calls without results)
        initial_split = len(session.messages) - decision.keep_last_n_messages
        split_index = self._find_valid_split_point(session.messages, initial_split)

        if split_index <= 0:
            # Cannot find a valid split point, don't compress
            return CompressionResult(
                summary_messages=[],
                archived_message_count=0,
                archive_refs=[],
                summary_token_count=0,
            )

        to_compress = session.messages[:split_index]
        remaining = session.messages[split_index:]

        if not to_compress:
            return CompressionResult(
                summary_messages=[],
                archived_message_count=0,
                archive_refs=[],
                summary_token_count=0,
            )

        # 3. Generate summary using LLM
        summary_content = self._summarize(to_compress)

        # 4. Archive raw messages if requested
        archive_refs = []
        if decision.archive_raw_messages and self.storage:
            archive_id = self._archive_messages(session.id, to_compress)
            archive_refs.append(archive_id)

        # 5. Update session messages
        session.messages = remaining

        # 6. Create summary message
        summary_message = Message(
            role="system",
            content=summary_content,
        )

        # 7. Estimate summary tokens
        estimator = TokenEstimator()
        summary_tokens = estimator.estimate_text(summary_content)

        return CompressionResult(
            summary_messages=[summary_message],
            archived_message_count=len(to_compress),
            archive_refs=archive_refs,
            summary_token_count=summary_tokens,
        )

    def _find_valid_split_point(
        self,
        messages: list[Message],
        initial_split: int,
    ) -> int:
        """
        Find a valid split point that ensures remaining messages are valid.

        A valid message sequence must:
        - Start with user or assistant text (not tool results)
        - Have matching tool calls and results

        Args:
            messages: All session messages.
            initial_split: Initial split index.

        Returns:
            Valid split index (may be adjusted from initial).
        """
        split = initial_split

        # Ensure we don't start with tool results
        while split < len(messages):
            remaining = messages[split:]
            if not remaining:
                break

            first_msg = remaining[0]

            # Check if first message is tool results
            if self._is_tool_result_message(first_msg):
                # Need to include the tool call that produced this result
                split = self._find_tool_call_for_result(messages, split)
                if split < 0:
                    # Couldn't find matching tool call, skip this result
                    split += 1
                continue

            # Check if first message is tool calls without following results
            if self._is_tool_call_message(first_msg):
                # Check if there are matching results
                if not self._has_matching_tool_results(remaining):
                    # Need to include the results or skip the calls
                    result_index = self._find_tool_results_for_calls(messages, split)
                    if result_index > 0:
                        # Found results, include them
                        split = result_index
                    else:
                        # No results, skip the tool calls
                        split += 1
                    continue

            # Valid starting message
            break

        return split

    def _is_tool_result_message(self, msg: Message) -> bool:
        """Check if message contains tool results."""
        if msg.role == "user" and not isinstance(msg.content, str):
            items = list(msg.content)
            return items and isinstance(items[0], ToolResult)
        return False

    def _is_tool_call_message(self, msg: Message) -> bool:
        """Check if message contains tool calls."""
        if msg.role == "assistant" and not isinstance(msg.content, str):
            items = list(msg.content)
            return items and isinstance(items[0], ToolCall)
        return False

    def _has_matching_tool_results(self, messages: list[Message]) -> bool:
        """Check if tool calls have matching results in following messages."""
        if not messages or not self._is_tool_call_message(messages[0]):
            return False

        # Get tool call IDs
        items = list(messages[0].content)
        call_ids = {tc.id for tc in items if isinstance(tc, ToolCall)}

        # Check if next message has matching results
        if len(messages) < 2:
            return False

        next_msg = messages[1]
        if self._is_tool_result_message(next_msg):
            items = list(next_msg.content)
            result_ids = {tr.call_id for tr in items if isinstance(tr, ToolResult)}
            return call_ids == result_ids

        return False

    def _find_tool_call_for_result(self, messages: list[Message], result_index: int) -> int:
        """Find the index of tool call message for the result at result_index."""
        result_msg = messages[result_index]
        if not self._is_tool_result_message(result_msg):
            return -1

        items = list(result_msg.content)
        result_ids = {tr.call_id for tr in items if isinstance(tr, ToolResult)}

        # Search backwards for matching tool calls
        for i in range(result_index - 1, -1, -1):
            msg = messages[i]
            if self._is_tool_call_message(msg):
                items = list(msg.content)
                call_ids = {tc.id for tc in items if isinstance(tc, ToolCall)}
                if call_ids == result_ids:
                    return i

        return -1

    def _find_tool_results_for_calls(self, messages: list[Message], call_index: int) -> int:
        """Find the index after tool results for calls at call_index."""
        call_msg = messages[call_index]
        if not self._is_tool_call_message(call_msg):
            return -1

        # Check if next message has results
        if call_index + 1 < len(messages):
            next_msg = messages[call_index + 1]
            if self._is_tool_result_message(next_msg):
                # Return index after results (include results)
                return call_index + 2 if call_index + 2 <= len(messages) else -1

        return -1

    def _summarize(self, messages: list[Message]) -> str:
        """
        Generate a summary of the messages using LLM.

        Args:
            messages: The messages to summarize.

        Returns:
            A summary string.
        """
        from quenda.kernel import Kernel
        from quenda.kernel.types import Message

        # Build summarization prompt
        prompt = self._build_summary_prompt(messages)

        # Create kernel with no tools for summarization
        kernel = Kernel(self.model, tools=[])

        # Run summarization
        summary_content = ""
        for step in kernel.run([
            Message(role="system", content=SUMMARY_SYSTEM_PROMPT),
            Message(role="user", content=prompt),
        ]):
            if step.type == "model":
                response = step.content
                if hasattr(response, 'content') and response.content:
                    summary_content = response.content
                    break

        return summary_content or "（摘要生成失败）"

    def _build_summary_prompt(self, messages: list[Message]) -> str:
        """
        Build the prompt for summarization.

        Args:
            messages: The messages to summarize.

        Returns:
            A prompt string for the summarization model.
        """
        # Format messages for summarization
        formatted = self._format_messages(messages)

        return f"""请将以下对话历史压缩为简洁的摘要，保留：
- 用户目标
- 已接受的约束
- 重要决策
- 影响计划的工具输出
- 已知错误和失败尝试
- 待办事项
- 当前工作流状态

对话历史：
{formatted}

摘要："""

    def _format_messages(self, messages: list[Message], max_length: int = 10000) -> str:
        """
        Format messages for the summarization prompt.

        Args:
            messages: The messages to format.
            max_length: Maximum character length for the formatted output.

        Returns:
            A formatted string representation of the messages.
        """
        lines = []
        total_length = 0

        for msg in messages:
            if isinstance(msg.content, str):
                line = f"[{msg.role}]: {msg.content}"
            else:
                # Tool calls or results
                items = list(msg.content)
                if items:
                    if hasattr(items[0], 'name'):
                        if hasattr(items[0], 'arguments'):
                            # Tool calls
                            line = f"[{msg.role}]: 调用工具: {', '.join(getattr(i, 'name', '?') for i in items)}"
                        else:
                            # Tool results
                            line = f"[{msg.role}]: 工具结果: {', '.join(getattr(i, 'name', '?') for i in items)}"
                    else:
                        line = f"[{msg.role}]: [复杂内容]"
                else:
                    line = f"[{msg.role}]: [空]"

            if total_length + len(line) > max_length:
                lines.append("... (内容已截断)")
                break

            lines.append(line)
            total_length += len(line)

        return "\n".join(lines)

    def _archive_messages(self, session_id: str, messages: list[Message]) -> str:
        """
        Archive raw messages to storage.

        Args:
            session_id: The session ID.
            messages: The messages to archive.

        Returns:
            The archive ID.
        """
        if not self.storage:
            return ""

        archive_id = str(uuid4())
        self.storage.save_archive(session_id, messages, archive_id)
        return archive_id


__all__ = [
    "Compressor",
    "SummarizerCompressor",
    "SUMMARY_SYSTEM_PROMPT",
]
