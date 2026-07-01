# Agent 基础

理解 Quenda Agent 的核心概念和配置方式。

---

## Agent 的构成

一个 Agent 由三个核心部分组成：

```
Agent(name, system_prompt, tools, model)
├── name          — 唯一标识符
├── system_prompt — 行为指令（人格、规则、方法论）
├── tools         — 可调用的能力（函数/工具）
└── model         — 底层 AI 模型（决定了智能水平）
```

## 创建 Agent

### 基础方式

```python
from quenda import Agent

agent = Agent(
    name="my-assistant",
    system_prompt="你是一个有用的助手。",
    tools=[...],
    model=model,
)
```

### 完整配置

```python
from quenda import Agent
from quenda.host.storage import FileStorage, FileStorageConfig
from quenda.host.compression_policy import DefaultCompressionPolicy
from quenda.runtime.compressor import SummarizerCompressor

agent = Agent(
    name="advanced-agent",
    system_prompt="...",
    tools=my_tools,
    model=model,
    from pathlib import Path

    # 持久化存储
    storage=FileStorage(
        config=FileStorageConfig(base_dir=Path("/path/to/storage"))
    ),
    # 自动上下文压缩（ADR-015）
    compression_policy=DefaultCompressionPolicy(
        threshold_ratio=0.8,
        keep_last_n_messages=10,
    ),
    compressor=SummarizerCompressor(
        model=summary_model,
        storage=storage,
    ),
)
```

## 系统提示词 (System Prompt)

系统提示词是 Agent 行为的核心——它定义了 Agent 的身份、规则和工作方式。

### 何时使用

- **定义角色**: "你是一个 Python 专家"
- **设定规则**: "永远不要修改文件系统之外的文件"
- **指导方法**: "先读代码，再改代码"
- **约束行为**: "不确定时要问用户"

### 动态更新

可以在运行时更新系统提示词：

```python
agent.set_system_prompt("新的系统提示词...")

# 或者在 Session 中更新
session.set_system_prompt("新的提示词")
```

## Agent 属性

```python
agent = Agent(name="my-agent", system_prompt="...", tools=[...], model=model)

agent.name            # "my-agent"
agent.config          # AgentConfig 实例（不可变）
agent.model           # Model 实例（可能为 None）
agent.system_prompt   # str 或 None
agent.tools           # list[Tool]
agent.storage         # Storage 或 None
```

## 两种执行模式

Quenda Agent 提供两种执行方式：

### 1. 一次性执行 `run()`

适用于问答、单次任务。每次调用创建临时会话：

```python
# 异步
result = await agent.run("你好！")

# 同步
result = agent.run_sync("你好！")

# 带事件回调
result = await agent.run(
    "帮我分析这段代码",
    on_event=lambda event: print(event)
)
```

### 2. 持久会话 `open_session()`

适用于多轮对话、需要保持上下文的场景：

```python
# 开启会话
session = agent.open_session()

# 多轮对话
r1 = await session.send("第一轮")
r2 = await session.send("第二轮（记得上下文）")

# 会话信息
session.id       # 唯一 ID
session.messages # 消息历史
session.model   # 当前模型
```

### Session 属性

```python
session.id            # str: 会话 ID
session.state         # SessionState: 底层状态
session.messages      # list[Message]: 消息历史
session.system_prompt # str | None: 系统提示词
session.tools         # list[Tool]: 可用工具
session.mode          # str: 当前模式（chat/code/architect）
session.model         # Model | None: 当前模型

len(session)          # 消息数量
```

---

## Agent 配置不可变性

`AgentConfig` 是不可变的（frozen dataclass）：

```python
from quenda.runtime import AgentConfig

config = AgentConfig(
    name="my-agent",
    system_prompt="...",
    tools=[...],
)

# config.name = "new-name"  # ❌ 不可变，会报错
```

## 使用 AGENT.md 文件

Quenda 支持从 `AGENT.md` 文件加载 Agent 配置：

```markdown
---
name: my-agent
version: 1.0.0
---

你是一个 Python 专家助手...
```

代码中加载：

```python
from quenda.host import load_agent_from_markdown

config = load_agent_from_markdown("path/to/AGENT.md")
# 返回 AgentConfig 实例（不含工具和模型）
```

---

## 下一步

- [工具系统](./03-tools.md) — 掌握所有工具用法
- [模型提供者](./04-providers.md) — 切换不同的 AI 模型
- [会话管理](./05-sessions.md) — 深入会话生命周期

---

<div align="right">
  <a href="./01-quickstart.md">← 上一页</a> ·
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a> ·
  <a href="./03-tools.md">下一页 →</a>
</div>
