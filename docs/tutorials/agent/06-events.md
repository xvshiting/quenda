# 事件系统

Quenda 的运行时事件系统让你可以实时监控 Agent 的执行过程。

---

## 事件架构

```
Run.execute(message)
  │
  ├── RunStarted          ── 执行开始
  │
  ├── ModelResponded      ── 模型返回结果
  │   └── content / tool_calls
  │
  ├── ToolExecuted        ── 工具执行完成
  │   └── tool_name / result / is_error
  │
  ├── ... (循环：模型→工具→模型→工具→...) ── 多轮交互
  │
  ├── CompressionStarted  ── 上下文压缩开始
  ├── CompressionCompleted── 压缩完成
  │
  ├── RunCompleted        ── 正常完成
  ├── RunInterrupted      ── 用户中断
  └── ErrorOccurred       ── 执行出错
```

---

## 事件类型

### 基础事件

所有事件继承 `Event`：

```python
@dataclass(frozen=True)
class Event:
    id: str        # 唯一 ID
    timestamp: datetime  # 时间戳
    run_id: str    # 所属 Run
```

### RunStarted

```python
@dataclass(frozen=True)
class RunStarted(Event):
    agent_name: str       # Agent 名称
    session_id: str       # 会话 ID
    user_message: str     # 用户消息
```

### ModelResponded

模型返回响应的关键事件：

```python
@dataclass(frozen=True)
class ModelResponded(Event):
    content: str | None          # 文本回复（可能为 None）
    tool_calls: list[str]        # 调用的工具名列表
    tool_arguments: list[dict]   # 每个工具调用的参数
    stop_reason: str             # 停止原因
```

### ToolExecuted

```python
@dataclass(frozen=True)
class ToolExecuted(Event):
    tool_name: str               # 工具名
    arguments: dict              # 关键参数（含 _summary）
    result: str                  # 执行结果
    is_error: bool               # 是否错误
    duration_ms: int             # 执行耗时（毫秒）
    result_lines: int            # 结果行数
    result_truncated: bool       # 是否被截断
```

### 其他事件

```python
@dataclass(frozen=True)
class RunCompleted(Event):
    agent_name: str
    session_id: str
    total_steps: int             # 总步数
    final_content: str | None    # 最终回复
    duration_ms: int             # 总耗时

@dataclass(frozen=True)
class ErrorOccurred(Event):
    error_message: str
    error_type: str

@dataclass(frozen=True)
class RunInterrupted(Event):
    reason: str                  # 中断原因
    steps_completed: int         # 已完成步数

@dataclass(frozen=True)
class CompressionStarted(Event):
    session_id: str
    decision: CompressionDecision

@dataclass(frozen=True)
class CompressionCompleted(Event):
    session_id: str
    result: CompressionResult
```

---

## 使用事件

### 事件回调

```python
def on_event(event):
    if hasattr(event, 'type'):
        print(f"[{event.type}] {event}")

# Agent 一次性执行
result = asyncio.run(
    agent.run("你好", on_event=on_event)
)

# Session 对话
result = await session.send(
    "分析代码",
    on_event=on_event
)
```

### 收集事件

```python
from quenda.runtime.events import (
    ModelResponded, ToolExecuted, RunCompleted
)

events = []

def collector(event):
    events.append(event)

result = agent.run_sync("你好", on_event=collector)

# 分析事件
for event in events:
    if isinstance(event, ModelResponded):
        print(f"模型回复: {event.content[:100]}...")
        print(f"工具调用: {event.tool_calls}")
    elif isinstance(event, ToolExecuted):
        print(f"执行工具 {event.tool_name}: {event.duration_ms}ms")
    elif isinstance(event, RunCompleted):
        print(f"完成: {event.total_steps} 步, {event.duration_ms}ms")
```

### 流式处理

```python
import asyncio
from quenda.runtime import Run
from quenda.runtime.session import SessionState

# 底层 Run 对象可以直接异步迭代
state = SessionState.create("my-agent")
run = Run.create(agent_config, state, model)

async for event in run.execute("你好"):
    if event.type == "model_responded" and event.content:
        print(event.content, end="", flush=True)
    elif event.type == "tool_executed":
        print(f"\n[工具] {event.tool_name} ({event.duration_ms}ms)")
```

---

## 构建监控面板

利用事件系统可以构建实时监控：

```python
from collections import Counter
from datetime import datetime

class RunMonitor:
    def __init__(self):
        self.steps = 0
        self.tool_calls = Counter()
        self.total_duration = 0
        self.start_time = None

    def on_event(self, event):
        if event.type == "run_started":
            self.start_time = datetime.now()
            print(f"▶ 开始执行: {event.user_message[:50]}...")

        elif event.type == "model_responded":
            self.steps += 1
            if event.tool_calls:
                print(f"  ├ 模型请求工具: {event.tool_calls}")

        elif event.type == "tool_executed":
            self.tool_calls[event.tool_name] += 1
            self.total_duration += event.duration_ms
            icon = "✓" if not event.is_error else "✗"
            print(f"  ├ {icon} {event.tool_name} ({event.duration_ms}ms)")

        elif event.type == "run_completed":
            elapsed = (datetime.now() - self.start_time).total_seconds()
            print(f"▶ 完成: {event.total_steps} 步, {elapsed:.1f}s")
            print(f"  工具调用: {dict(self.tool_calls)}")
```

---

## 事件驱动开发

你可以基于事件构建高级功能：

- **调试工具**: 记录所有事件到日志文件
- **进度条**: 可视化工具执行进度
- **费用追踪**: 统计每次执行的 token 消耗
- **断点续传**: 在中断点保存状态，稍后恢复
- **审计日志**: 记录 Agent 的所有操作

---

## 下一步

- [进阶用法](./07-advanced.md) — 指令系统、扩展机制
- [API 参考](./08-references.md) — 完整 API 速查表

---

<div align="right">
  <a href="./05-sessions.md">← 上一页</a> ·
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a> ·
  <a href="./07-advanced.md">下一页 →</a>
</div>
