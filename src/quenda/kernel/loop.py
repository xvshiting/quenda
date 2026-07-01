"""
Kernel - The core model-tool loop executor.

The Kernel is the heart of Kora's execution. It runs a synchronous
model-tool loop, calling the model and executing tools until completion.
"""

import time
from collections.abc import Iterator
from dataclasses import dataclass

from quenda.kernel.model import Model
from quenda.kernel.tool import Tool, ToolRegistry
from quenda.kernel.types import Message, ModelResponse, ToolCall, ToolResult


@dataclass
class KernelStep:
    """
    A single step in the kernel execution.

    Each step represents either:
    - A model response (content or tool calls)
    - A tool execution result
    """

    type: str  # "model" or "tool"
    content: ModelResponse | ToolResult
    # For tool steps, store the original call with arguments
    tool_call: ToolCall | None = None
    # Timing
    duration_ms: int = 0


class Kernel:
    """
    The core model-tool loop executor.

    The Kernel runs a synchronous loop:
    1. Call model with messages
    2. If model returns content, yield and check stop
    3. If model returns tool calls, execute them
    4. Add results to messages
    5. Repeat until stop

    The Kernel is pure and testable - it has no knowledge of:
    - Agents or Agent files
    - Sessions or persistence
    - Users or tenants
    - Model configuration or API keys
    """

    def __init__(
        self,
        model: Model,
        tools: list[Tool],
        *,
        max_iterations: int = 100,
    ) -> None:
        """
        Initialize the Kernel.

        Args:
            model: The model provider to use.
            tools: The tools available for execution.
            max_iterations: Maximum number of model calls before stopping.
        """
        self.model = model
        self.registry = ToolRegistry()
        self.max_iterations = max_iterations

        for tool in tools:
            self.registry.register(tool)

    def invoke_model(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
    ) -> ModelResponse:
        """
        Invoke the model once with messages and optional tools.

        This is a primitive operation for Runtime to use when it owns
        the execution loop. Unlike run(), this method:
        - does not loop
        - does not check stop_reason
        - does not append to messages
        - does not execute any tools

        Args:
            messages: The conversation history.
            tools: Optional tool list (uses registered tools if None).

        Returns:
            The model's response (content or tool calls).

        Note:
            This method is pure execution. Runtime decides what to do
            with the response.
        """
        if tools is None:
            tools = self.registry.all_tools()
        return self.model.invoke(messages, tools=tools)

    def execute_tool(self, call: ToolCall) -> ToolResult:
        """
        Execute a single tool call.

        This is a primitive operation for Runtime to use when it owns
        the tool phase. Unlike _execute_tools_streaming(), this method:
        - executes exactly one tool
        - does not append to messages
        - returns the result directly

        Args:
            call: The tool call to execute.

        Returns:
            The tool execution result.

        Note:
            This method handles:
            - tool lookup (returns error if not found)
            - argument filtering (removes _ prefixed args)
            - execution timing
            - error handling

            Runtime decides whether to write the result to messages.
        """
        tool = self.registry.get(call.name)

        if tool is None:
            return ToolResult(
                call_id=call.id,
                name=call.name,
                content=f"Tool not found: {call.name}",
                is_error=True,
            )

        try:
            start_time = time.perf_counter()

            # Filter out framework-reserved parameters before execution
            filtered_args = {
                k: v for k, v in call.arguments.items()
                if not k.startswith("_")
            }
            result = tool.execute(**filtered_args)

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Kernel ensures all fields are properly set
            return ToolResult(
                call_id=result.call_id or call.id,
                name=result.name,
                content=result.content,
                is_error=result.is_error,
                duration_ms=duration_ms,
                display_hint=result.display_hint,
                change_preview=result.change_preview,
                result_summary=result.result_summary,
            )
        except Exception as e:
            return ToolResult(
                call_id=call.id,
                name=call.name,
                content=f"Tool execution failed: {e}",
                is_error=True,
            )

    def run(self, messages: list[Message]) -> Iterator[KernelStep]:
        """
        Run the model-tool loop.

        Args:
            messages: The initial conversation history.

        Yields:
            KernelStep objects representing each step of execution.

        Note:
            This is a generator that yields steps as they occur.
            The caller can observe progress in real-time.
        """
        tools = self.registry.all_tools()
        iteration = 0

        while iteration < self.max_iterations:
            # Call the model
            response = self.model.invoke(messages, tools=tools)
            iteration += 1

            # Yield the model response
            yield KernelStep(type="model", content=response)

            # Check if we should stop
            if response.stop_reason in ("end_turn", "max_tokens", "stop_sequence"):
                # Add assistant message if has content (final response)
                if response.content:
                    messages.append(Message(role="assistant", content=response.content))
                break

            # If there are tool calls, execute them
            if response.tool_calls:
                # Execute tools and yield results as they complete
                call_results: list[tuple[ToolCall, ToolResult]] = []

                for call, result in self._execute_tools_streaming(response.tool_calls):
                    call_results.append((call, result))
                    yield KernelStep(
                        type="tool",
                        content=result,
                        tool_call=call,
                        duration_ms=result.duration_ms,
                    )

                # Add assistant message with tool calls and user message with results
                tool_results = [result for _, result in call_results]
                messages.append(Message(role="assistant", content=response.tool_calls))
                messages.append(Message(role="user", content=tool_results))

    def _execute_tools_streaming(
        self, calls: list[ToolCall]
    ) -> Iterator[tuple[ToolCall, ToolResult]]:
        """
        Execute tool calls one by one, yielding (call, result) pairs immediately.

        This ensures KernelStep events reflect real execution order,
        enabling Interface layer to show accurate progress.

        Args:
            calls: The tool calls to execute.

        Yields:
            (ToolCall, ToolResult) tuples as each tool completes.
        """
        for call in calls:
            tool = self.registry.get(call.name)

            if tool is None:
                # Tool not found - yield an error
                yield (
                    call,
                    ToolResult(
                        call_id=call.id,
                        name=call.name,
                        content=f"Tool not found: {call.name}",
                        is_error=True,
                    ),
                )
                continue

            try:
                start_time = time.perf_counter()

                # Filter out framework-reserved parameters before execution
                filtered_args = {
                    k: v for k, v in call.arguments.items()
                    if not k.startswith("_")
                }
                result = tool.execute(**filtered_args)

                duration_ms = int((time.perf_counter() - start_time) * 1000)

                # Kernel ensures all fields are properly set
                # ToolResult is frozen, so we create a new one with all fields
                yield (
                    call,
                    ToolResult(
                        call_id=result.call_id or call.id,
                        name=result.name,
                        content=result.content,
                        is_error=result.is_error,
                        duration_ms=duration_ms,
                        display_hint=result.display_hint,
                        change_preview=result.change_preview,
                        result_summary=result.result_summary,
                    ),
                )
            except Exception as e:
                # Tool execution failed
                yield (
                    call,
                    ToolResult(
                        call_id=call.id,
                        name=call.name,
                        content=f"Tool execution failed: {e}",
                        is_error=True,
                    ),
                )

    def _execute_tools_with_calls(
        self, calls: list[ToolCall]
    ) -> list[tuple[ToolCall, ToolResult]]:
        """
        Execute a list of tool calls, returning (call, result) pairs.

        Deprecated: Use _execute_tools_streaming for real-time event emission.

        Args:
            calls: The tool calls to execute.

        Returns:
            A list of (ToolCall, ToolResult) tuples.
        """
        return list(self._execute_tools_streaming(calls))

    def _execute_tools(self, calls: list[ToolCall]) -> list[ToolResult]:
        """
        Execute a list of tool calls.

        Args:
            calls: The tool calls to execute.

        Returns:
            A list of ToolResult objects.
        """
        return [result for _, result in self._execute_tools_with_calls(calls)]

    def run_to_completion(self, messages: list[Message]) -> list[KernelStep]:
        """
        Run the loop to completion and return all steps.

        This is a convenience method that collects all steps into a list.

        Args:
            messages: The initial conversation history.

        Returns:
            A list of all KernelStep objects from the execution.
        """
        return list(self.run(messages))
