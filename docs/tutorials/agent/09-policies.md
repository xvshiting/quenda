# Policy 系统

策略钩子 (Policy Hooks) 是 Quenda 的扩展机制，让你可以在不修改核心代码的情况下控制 Agent 的行为。

---

## 概述

Quenda 的 Policy 系统遵循 **"简单默认，可扩展设计"** 原则：

- **Core 定义执行机制和默认行为**
- **Policy 定义策略逻辑**

```
┌─────────────────────────────────────────────────────────────┐
│                       Host Layer                             │
│  (配置、存储、身份、权限)                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Runtime Layer                           │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ TraceSink   │  │ Termination  │  │ Tool Policies    │    │
│  │ (Observer)  │  │   Policy     │  │ (Target Contract)│    │
│  └─────────────┘  └──────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Kernel Layer                           │
│  (纯执行引擎，不包含策略逻辑)                                   │
└─────────────────────────────────────────────────────────────┘
```

### 可用的 Policy Seams

| Seam | 角色 | 当前状态 | 用途 |
|------|------|----------|------|
| `TraceSink` | Observer | ✅ 可用 | 记录运行事件，调试分析 |
| `TerminationPolicy` | Policy | ✅ 可用 | 控制何时停止执行 |
| `ToolSelectionPolicy` | Policy | ⚠️ Target Contract | 工具执行审批 |
| `ToolResultProcessingPolicy` | Policy | ⚠️ Target Contract | 工具结果处理 |

---

## TraceSink：事件观察器

`TraceSink` 是一个纯观察接口，用于记录 Agent 运行过程中的所有事件。

### 基础用法

```python
from quenda.runtime import Run, JsonlTraceSink

# 创建 TraceSink
sink = JsonlTraceSink("traces/run.jsonl")

# 注入到 Run
run = Run.create(
    agent=agent,
    session=session,
    model=model,
    trace_sink=sink,
)

# 运行时自动记录事件
events = await run.execute_to_completion("你好")
```

### 事件类型

所有事件都继承自 `Event` 基类：

```python
from quenda.runtime import (
    RunStarted,      # Run 开始
    RunCompleted,    # Run 正常完成
    RunTerminated,   # Run 被策略终止
    RunInterrupted,  # Run 被用户中断
    ModelResponded,  # 模型响应
    ToolExecuted,    # 工具执行完成
    ErrorOccurred,   # 发生错误
)
```

### 自定义 TraceSink

```python
from quenda.runtime import TraceSink, AnyEvent

class MyTraceSink:
    """自定义 TraceSink 实现。"""
    
    def record(self, event: AnyEvent) -> None:
        """记录事件（不能抛出异常）。"""
        # 根据 event.type 分发处理
        if event.type == "model_responded":
            print(f"[Model] {event.content[:50]}...")
        elif event.type == "tool_executed":
            print(f"[Tool] {event.tool_name} ({event.duration_ms}ms)")
        elif event.type == "run_completed":
            print(f"[Done] {event.total_steps} steps, {event.duration_ms}ms")

# 使用自定义 sink
run = Run.create(agent, session, model, trace_sink=MyTraceSink())
```

### 内置实现

| 实现 | 说明 |
|------|------|
| `NullTraceSink` | 空实现，默认值 |
| `JsonlTraceSink` | 写入 JSONL 文件，便于后续分析 |

---

## TerminationPolicy：终止策略

`TerminationPolicy` 让你可以控制 Agent 何时停止执行，而不是让它无限运行。

### 基础用法

```python
from quenda.runtime import Run, MaxStepsPolicy

# 限制最多 20 步
policy = MaxStepsPolicy(max_steps=20)

run = Run.create(
    agent=agent,
    session=session,
    model=model,
    termination_policy=policy,
)

# 超过 20 步后自动停止
events = await run.execute_to_completion("帮我分析这个项目")

# 检查是否被终止
from quenda.runtime import RunTerminated
terminated = [e for e in events if isinstance(e, RunTerminated)]
if terminated:
    print(f"被终止: {terminated[0].reason}")
```

### 内置策略

#### MaxStepsPolicy

限制最大步骤数：

```python
from quenda.runtime import MaxStepsPolicy

policy = MaxStepsPolicy(max_steps=50)
```

#### TimeBudgetPolicy

限制执行时间（毫秒）：

```python
from quenda.runtime import TimeBudgetPolicy

# 最多运行 5 分钟
policy = TimeBudgetPolicy(max_time_ms=5 * 60 * 1000)
```

#### TokenBudgetPolicy

限制 Token 使用量：

```python
from quenda.runtime import TokenBudgetPolicy

# 最多使用 100k tokens
policy = TokenBudgetPolicy(max_total_tokens=100_000)
```

#### ConsecutiveErrorPolicy

连续错误时停止：

```python
from quenda.runtime import ConsecutiveErrorPolicy

# 连续 3 次错误后停止
policy = ConsecutiveErrorPolicy(max_consecutive_errors=3)
```

### 组合策略

使用 `CompositeTerminationPolicy` 组合多个策略：

```python
from quenda.runtime import (
    CompositeTerminationPolicy,
    MaxStepsPolicy,
    TokenBudgetPolicy,
    ConsecutiveErrorPolicy,
)

# 任一条件满足即停止
policy = CompositeTerminationPolicy([
    MaxStepsPolicy(max_steps=50),
    TokenBudgetPolicy(max_total_tokens=100_000),
    ConsecutiveErrorPolicy(max_consecutive_errors=5),
])

run = Run.create(
    agent=agent,
    session=session,
    model=model,
    termination_policy=policy,
)
```

### 自定义 TerminationPolicy

```python
from quenda.runtime import (
    TerminationPolicy,
    TerminationState,
    TerminationDecision,
)

class NoProgressPolicy:
    """检测无进展并停止。"""
    
    def __init__(self, max_same_tool_calls: int = 3):
        self.max_same_tool_calls = max_same_tool_calls
        self._call_history: list[str] = []
    
    def should_terminate(self, state: TerminationState) -> TerminationDecision:
        # 自定义逻辑：检测重复工具调用
        # 注意：这是一个示例，实际需要更多信息
        
        if state.step_count > 10 and state.tool_round_count < 2:
            # 执行了多步但几乎没有工具调用
            return TerminationDecision(
                should_stop=True,
                reason="no_progress_detected",
            )
        
        return TerminationDecision(should_stop=False)

# 使用自定义策略
run = Run.create(
    agent=agent,
    session=session,
    model=model,
    termination_policy=NoProgressPolicy(),
)
```

### TerminationState 字段

```python
@dataclass(frozen=True)
class TerminationState:
    # 执行进度
    step_count: int           # 已执行步数
    tool_round_count: int     # 工具轮次
    elapsed_time_ms: int      # 已用时间（毫秒）
    
    # Token 使用（累计）
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    
    # 错误追踪
    error_count: int
    consecutive_error_count: int
    
    # 上下文
    run_id: str
    session_id: str
    agent_name: str
    last_step_type: str | None    # "model" 或 "tool"
    last_stop_reason: str | None  # 模型停止原因
```

---

## 组合使用

可以将 `TraceSink` 和 `TerminationPolicy` 组合使用：

```python
from quenda.runtime import (
    Run,
    JsonlTraceSink,
    CompositeTerminationPolicy,
    MaxStepsPolicy,
    TokenBudgetPolicy,
)

# 创建 Run 时注入所有策略
run = Run.create(
    agent=agent,
    session=session,
    model=model,
    
    # 观察器
    trace_sink=JsonlTraceSink("traces/session.jsonl"),
    
    # 终止策略
    termination_policy=CompositeTerminationPolicy([
        MaxStepsPolicy(max_steps=30),
        TokenBudgetPolicy(max_total_tokens=50_000),
    ]),
)

# 执行
events = await run.execute_to_completion("帮我重构这个模块")

# 分析结果
from quenda.runtime import RunCompleted, RunTerminated

completed = [e for e in events if isinstance(e, RunCompleted)]
terminated = [e for e in events if isinstance(e, RunTerminated)]

if completed:
    print(f"✅ 完成: {completed[0].total_steps} 步")
elif terminated:
    print(f"⏹️ 终止: {terminated[0].reason}")
```

---

## Tool Policies（Target Contract）

`ToolSelectionPolicy` 和 `ToolResultProcessingPolicy` 是 **Target Contract**，表示接口已定义，但需要 Runtime/Kernel 重构后才能完整集成。

### ToolSelectionPolicy

用于审批工具执行请求：

```python
from quenda.runtime import (
    ToolSelectionPolicy,
    ToolSelectionRequest,
    ToolSelectionDecision,
    RejectedToolCall,
    DenylistToolSelectionPolicy,
    AllowlistToolSelectionPolicy,
)

# 拒绝危险工具
policy = DenylistToolSelectionPolicy(
    denied={"run_shell", "python_execution"}
)

# 或只允许特定工具
policy = AllowlistToolSelectionPolicy(
    allowed={"read_file", "search_text", "list_files"}
)
```

**注意**：当前版本需要 Runtime ownership of tool-call gating 才能完整集成。

### ToolResultProcessingPolicy

用于处理工具输出：

```python
from quenda.runtime import (
    ToolResultProcessingPolicy,
    ToolResultEnvelope,
    ProcessedToolResult,
    TruncatingToolResultProcessingPolicy,
    LineLimitedToolResultProcessingPolicy,
)

# 截断长输出
policy = TruncatingToolResultProcessingPolicy(max_chars=4000)

# 或限制行数
policy = LineLimitedToolResultProcessingPolicy(max_lines=100)
```

**注意**：当前版本需要 Runtime ownership of tool-result writeback 才能完整集成。

---

## 设计原则

### 1. Observer vs Policy

| 类型 | 影响 | 示例 |
|------|------|------|
| Observer | 只观察，不影响控制流 | `TraceSink` |
| Policy | 做决策，影响执行 | `TerminationPolicy` |

### 2. Kernel Guard vs Runtime Policy

```python
# Kernel Guard: 硬编码安全限制，不可配置
kernel = Kernel(model, tools, max_iterations=100)

# Runtime Policy: 可配置的策略，用户可控
run.termination_policy = MaxStepsPolicy(max_steps=20)
```

两者共存：
- **Kernel Guard** 是最后一道防线
- **Runtime Policy** 是用户策略层

### 3. 默认行为

所有 Policy 都有默认实现，保持向后兼容：

```python
# 不配置时使用默认值
run = Run.create(agent, session, model)
# trace_sink = None → NullTraceSink
# termination_policy = None → NeverTerminatePolicy
```

---

## 完整示例

```python
import asyncio
from quenda import Agent
from quenda.runtime import (
    JsonlTraceSink,
    CompositeTerminationPolicy,
    MaxStepsPolicy,
    TokenBudgetPolicy,
    ConsecutiveErrorPolicy,
    RunTerminated,
)

async def main():
    # 创建 Agent
    agent = Agent(
        name="code-assistant",
        system_prompt="你是一个代码助手...",
        tools=get_core_tools("/workspace"),
    )
    
    # 打开会话
    session = agent.open_session()
    
    # 创建带策略的 Run
    run = Run.create(
        agent=agent.config,
        session=session.state,
        model=agent.model,
        
        # 记录事件
        trace_sink=JsonlTraceSink(f"traces/{session.id}.jsonl"),
        
        # 终止策略
        termination_policy=CompositeTerminationPolicy([
            MaxStepsPolicy(max_steps=50),
            TokenBudgetPolicy(max_total_tokens=100_000),
            ConsecutiveErrorPolicy(max_consecutive_errors=3),
        ]),
    )
    
    # 执行
    events = await run.execute_to_completion("帮我优化这个函数")
    
    # 检查结果
    terminated = [e for e in events if isinstance(e, RunTerminated)]
    if terminated:
        print(f"执行被终止: {terminated[0].reason}")
        print(f"已完成步骤: {terminated[0].steps_completed}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 下一步

- [API 参考](./08-references.md) — 完整 API 速查表
- [事件系统](./06-events.md) — 事件驱动开发
- [架构决策记录](../../architecture/) — 了解设计背景

---

<div align="right">
  <a href="./07-advanced.md">← 上一页</a> ·
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a> ·
  <a href="./08-references.md">API 参考 →</a>
</div>
