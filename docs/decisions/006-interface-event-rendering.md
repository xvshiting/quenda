# ADR-006: Interface Event Rendering

## Status

Accepted

## Context

Quenda Runtime 发出结构化事件（`RunStarted`, `ToolExecuted`, `ModelResponded`, `RunCompleted` 等），但当前 CLI 对这些事件的渲染过于简陋：

```text
✓ list_files
✓ read_file
❌ run_shell
```

**问题**：

1. **不可解释**：用户不知道工具为什么被调用、参数是什么、失败原因是什么
2. **太吵**：每个工具单独刷一行，长任务变成瀑布流
3. **缺少参数摘要**：`read_file` 不带 path，`run_shell` 不带 command
4. **缺少阶段性状态**：没有把行为组织成阶段
5. **失败信息不足**：`❌ run_shell` 没有足够诊断信息

**本质**：我们缺的不是漂亮 TUI，而是 Interface 层对 Runtime events 的可解释渲染。

补充观察：

- 当前 Kernel 支持模型一次返回多个 `tool_calls`
- 这些工具调用当前按顺序同步执行
- 但 `KernelStep(type="tool")` 不是每执行完一个就立即产出
- 而是等整批工具全部执行完成后，再批量 yield 工具结果

这会让 Interface 层失去真实的中间状态，导致：

1. indicator 无法知道当前正在执行哪一个工具
2. 多工具调用只能显示第一条 summary 或粗糙总数
3. 时间线会误导用户，以为多个工具几乎同时完成
4. Web / TUI / 调试视图以后都会遇到同样的问题

因此，这不只是渲染器问题，也涉及 Kernel step 的产出时机。

## Decision

### 0. Kernel step 应贴近真实执行顺序

Interface 要想正确展示执行过程，Kernel 输出的 step 必须尽量
贴近真实执行顺序。

对于一批 `tool_calls`，正确的语义应该是：

1. 模型返回工具调用列表
2. Kernel 顺序执行第一个工具
3. 第一个工具完成后立即 yield 一个 `KernelStep(type="tool")`
4. Kernel 顺序执行第二个工具
5. 第二个工具完成后立即 yield 一个 `KernelStep(type="tool")`
6. 直到整批工具执行完成

而不是：

1. 先把整批工具全部执行完
2. 再一次性批量吐出所有工具事件

推荐原则：

- 工具仍然可以保持同步串行执行
- 但结果事件必须实时逐个产出
- 事件流应反映真实执行顺序，而不是事后回放

这项调整属于 Kernel / Runtime 事件模型的修正，不是单纯的
UI 补丁。

### 1. 事件增强

首先确保事件包含足够信息：

```python
@dataclass(frozen=True)
class ToolExecuted(Event):
    type: Literal["tool_executed"] = "tool_executed"
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)  # NEW
    result: str = ""
    is_error: bool = False
    duration_ms: int = 0  # NEW
    call_id: str = ""  # NEW
```

`arguments` 字段应包含工具的关键参数（不是全部参数）：

| 工具 | 关键参数 |
|------|---------|
| `read_file` | `path` |
| `write_file` | `path` |
| `list_files` | `path`, `pattern` |
| `search_text` | `pattern`, `path` |
| `apply_patch` | `path` |
| `run_shell` | `command` |
| `execute_python` | (first line of code) |

但 `arguments` 只是结构化底层数据，不应该强制等价于最终展示文本。

推荐补充两类展示扩展能力：

- `display_hint`: summary 后面的人类可读补充信息
- `change_preview`: 修改类工具的变更预览

推荐原则：

- `arguments` 负责结构化事实
- `display_hint` 负责可读展示
- `change_preview` 负责修改类工具的可视化差异

默认情况下，`display_hint` 可以从关键参数自动生成；
但工具应允许提供比 `key=value` 更自然的展示内容。

### 2. ConsoleRenderer

创建 `ConsoleRenderer` 类负责将事件渲染成人能理解的输出：

```python
# src/quenda/interface/console.py

class ConsoleRenderer:
    """
    Renders Runtime events to console output.

    Responsibilities:
    - Format tool calls with arguments
    - Render tool-defined display hints
    - Render diff previews for file modifications
    - Summarize results
    - Show errors with context
    - Track and display progress
    """

    def __init__(
        self,
        *,
        verbose: bool = False,
        show_arguments: bool = True,
        show_duration: bool = True,
        max_result_lines: int = 3,
    ):
        pass

    def render(self, event: AnyEvent) -> str | None:
        """
        Render an event to a string.

        Returns None if the event should be skipped.
        """
        pass

    def render_tool_call(self, event: ToolExecuted) -> str:
        """Render a tool execution with arguments and result."""
        pass

    def render_error(self, event: ToolExecuted) -> str:
        """Render a failed tool execution with error details."""
        pass
```

### 3. 渲染规则

#### Summary + Display Hint

默认展示应采用：

```text
summary (display_hint)
```

示例：

```text
Reading config file (pyproject.toml)
Searching for SessionState (src/)
Running tests (pytest -q tests/test_runtime.py)
Updating runtime loop (src/quenda/kernel/loop.py)
```

`display_hint` 的来源规则：

1. 优先使用 tool 自定义展示提示
2. 否则从关键参数生成默认提示
3. 超长内容截断

不建议直接把原始参数对象或 JSON dump 直接渲染给用户。

#### Tool Call（成功）

```text
✓ read_file src/quenda/cli.py
✓ list_files .
✓ search_text "def main" src/quenda/
✓ run_shell pytest -q tests/
```

#### Tool Call（失败）

```text
❌ run_shell pytest -q
   exit 2: ModuleNotFoundError: No module named 'quenda'

❌ read_file nonexistent.txt
   FileNotFoundError: No such file or directory
```

#### 工具结果摘要

```text
✓ read_file README.md (47 lines)
✓ search_text "import" src/ (23 matches)
✓ run_shell pytest -q (12 passed, 2 failed)
```

#### 修改类工具的 Diff Preview

对于会修改文件的工具，成功时应支持额外显示短 diff 预览。

规则：

- 仅当存在实际变更时展示
- 无变更时不展示 diff
- 只展示变更 hunks 及周围少量上下文
- 风格接近 unified diff / Git diff
- 长 diff 截断，避免刷屏

示例：

```diff
@@
- call_results = list(self._execute_tools_with_calls(response.tool_calls))
- for call, result in call_results:
+ for call, result in self._execute_tools_with_calls(response.tool_calls):
    yield KernelStep(...)
```

这类 diff preview 应优先用于：

- `apply_patch`
- `write_file`
- 未来的其它文件编辑类工具

#### 长输出截断

```text
✓ run_shell cat large_file.txt
   --- output truncated (234 lines) ---
   last 3 lines shown
```

#### Model 思考（如果有）

```text
💭 Looking for the main entry point...
```

#### 阶段性状态

```text
📁 Inspecting project structure
   ✓ list_files .
   ✓ read_file pyproject.toml

🔍 Finding entry point
   ✓ search_text "def main" src/
   ✓ read_file src/quenda/cli.py
```

#### Run 完成

```text
✅ Completed in 8 steps (3.2s)
```

### 4. 输出模式

ConsoleRenderer 支持两种模式：

**Compact（默认）**：适合 REPL，单行工具摘要

```text
✓ read_file src/quenda/cli.py
✓ run_shell pytest -q
```

**当前实现约束**：REPL 进一步收敛为只展示 `summary`，不显示工具名，也不做阶段折叠。这样可以把展示层保持在最小稳定形态，等需要更强信息密度时再引入聚合逻辑。

**Verbose**：适合 one-shot，显示详细信息

```text
🚀 Starting: Find the main entry point

🔧 Using tools: search_text, read_file

✓ search_text "def main" src/quenda/
   Found 3 matches in 2 files

✓ read_file src/quenda/cli.py
   251 lines, main entry at line 156

✅ Completed in 4 steps
```

### 5. 事件折叠策略（未来）

对于重复调用或长时间运行，实现折叠：

```text
✓ run_shell pytest (x3)  # 3 次相同命令折叠
✓ read_file (x5 files)  # 5 次读取折叠
```

这个留到后续实现，MVP 先做单行渲染。

### 6. 多工具调用的展示语义

对于模型一次返回多个工具调用，Interface 层不应该假设它们是
并行执行的。

当前和近期推荐语义：

- 多个工具调用是一个 tool batch
- batch 内部按顺序执行
- 每个工具完成后应立即发出对应事件
- indicator 应该能随着 batch 执行推进而更新

短期展示规则：

- 单工具：显示该工具的 summary
- 多工具：显示批次状态，例如 `Executing 2 tools...`
- 如果后续 step 已能逐个实时产出，允许展示当前工具 summary

长期展示规则：

- 可以进一步引入 `ToolExecutionStarted` 或 `ToolBatchStarted`
- 但在引入新事件前，至少应保证 `ToolExecuted` 逐个实时到达

### 7. 工具自定义展示协议

展示层不应该完全依赖一套硬编码的参数格式化规则去猜测每个
工具该如何展示。

推荐为工具提供可选的展示扩展能力：

- 自定义 `display_hint`
- 自定义 `change_preview`

原则上：

- 默认展示逻辑由框架提供
- 工具可以覆盖默认展示逻辑以提高可读性
- Interface 负责样式，不负责业务语义猜测

推荐职责分工：

| 能力 | 默认来源 | 可否由工具定制 |
|---|---|---|
| `summary` | LLM `_summary` 或框架默认摘要 | 否，保持框架主导 |
| `display_hint` | 从关键参数自动生成 | 是 |
| `change_preview` | 默认无 | 是 |

推荐实现方向：

- Runtime 事件保留结构化 `arguments`
- Tool 或 ToolResult 可额外提供展示提示
- Interface 将其渲染为括号中的浅色辅助信息
- 修改类工具可提供结构化变更信息，由 Interface 渲染为 diff

不推荐把所有显示逻辑都塞进 ConsoleRenderer 的工具名判断分支，
因为这会让展示层越来越像业务层。

## Implementation Plan

### Phase 1: 事件增强 ✅

1. ✅ 更新 `ToolExecuted` 添加 `arguments`、`duration_ms`、`call_id`
2. ✅ 更新 `Run` 传递工具参数和执行时间
3. ✅ 确保 `ToolResult` 包含足够信息

### Phase 1.5: 修正 Kernel 工具事件产出时机 ✅

1. ✅ 移除”先执行完整批工具、再统一回放结果”的行为
2. ✅ 调整 `Kernel.run()`，在每个工具执行完成后立即 yield 对应 step
3. ✅ 保持工具执行顺序不变，先不引入并行工具语义
4. ✅ 保证 Runtime 和 Interface 接收到的事件顺序更接近真实执行过程

### Phase 1.8: 展示提示与 Diff Preview ✅

1. ✅ 为事件层补充 `display_hint`、`result_summary` 和 `change_preview` 概念
2. ✅ 为常见工具提供默认参数到展示提示的兜底格式化
3. ✅ 为文件修改类工具提供 diff preview 能力
4. ✅ ConsoleRenderer 渲染 summary、display hint 和短 diff

### Phase 2: ConsoleRenderer ✅

1. ✅ 创建 `src/quenda/interface/console.py`
2. ✅ 实现 `ConsoleRenderer` 类
3. ✅ 更新 `cli.py` 使用 `ConsoleRenderer`

### Phase 3: Code Agent Policy (待实现)

1. 更新 `AGENT.md` 添加工具使用纪律
2. 定义工具调用节奏约束
3. 添加失败处理策略

## Non-Goals

- 完整 TUI（Rich/Textual 组件）
- 流式 token 输出
- Markdown 渲染
- Diff 高亮
- 进度条动画

这些属于更高层级的 Interface 增强，不在本次范围。

## Consequences

### Positive

- 用户能理解 Agent 在做什么
- 失败时有足够诊断信息
- 输出有组织，不再混乱
- 为未来 TUI 打下基础

### Negative

- 需要修改 Runtime 事件结构
- 可能影响现有代码
- 输出变多，需要控制长度

## Recommendation

按 Phase 1-3 顺序实现，先做事件增强，再做渲染器，最后约束 Agent 行为。
