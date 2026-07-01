# 会话管理

理解 Kora 的会话（Session）系统——从创建到持久化。

---

## 架构概览

```
Agent
├── open_session() → Session (执行上下文 + SessionState)
│   ├── send(message) → 执行一次对话
│   ├── save() → 持久化到存储
│   └── state → SessionState (可序列化的纯数据)
│
├── load_session(id) → 从存储恢复会话
└── list_sessions() → 查看所有会话

SessionState (纯数据，可持久化)
├── id: str
├── agent_name: str
├── messages: list[Message]
├── metadata: dict
├── usage: SessionUsage (token 统计)
├── summary_blocks: list[SummaryBlock] (压缩摘要)
└── archive_refs: list[str] (归档引用)
```

---

## 会话生命周期

```
  Agent.open_session()
        │
        ▼
  Session (id, messages=[], state)
        │
  ┌─────┴─────┐
  │           │
  ▼           ▼
send()     save()
  │           │
  │           ▼
  │        FileStorage
  │           │
  ▼           ▼
更多消息    持久化完成
  │
  ▼
save() → 下次可 load_session()
```

---

## 创建会话

```python
from kora import Agent

agent = Agent(
    name="my-agent",
    system_prompt="...",
    tools=[...],
    model=model,
)

# 创建新会话
session = agent.open_session()

# 指定自定义 ID（便于后续恢复）
session = agent.open_session(session_id="my-session-001")
```

---

## 发送消息

```python
# 异步
response = await session.send("你好")

# 同步
response = session.send_sync("你好")

# 带事件监控
async def on_event(event):
    print(f"事件: {event}")

response = await session.send("分析代码", on_event=on_event)
```

### 上下文保持

```python
session.send_sync("我的名字是小明")
session.send_sync("我叫什么名字？")  # 记得上下文：小明
```

---

## 持久化存储

### 配置 Storage

```python
from kora import Agent
from kora.host.storage import FileStorage, FileStorageConfig

from pathlib import Path

storage = FileStorage(
    config=FileStorageConfig(base_dir=Path("/path/to/storage"))
)

agent = Agent(
    name="my-agent",
    tools=[...],
    model=model,
    storage=storage,  # 配置存储
)
```

### 保存会话

```python
session = agent.open_session()
session.send_sync("你好")
session.save()  # 持久化到磁盘
```

### 恢复会话

```python
# 列出所有会话
sessions = agent.list_sessions()
for s in sessions:
    print(f"{s.id}: {len(s)} messages")

# 恢复会话
session = agent.load_session("my-session-001")
if session:
    result = session.send_sync("继续刚才的话题")
```

### 自动保存

在 CLI 模式中（如 `kora code`），每次 `send()` 后会自动 `save()`。

---

## 会话状态操作

```python
# 消息历史
session.messages  # list[Message]

# 消息数量
len(session)  # 等价于 len(session.messages)

# 清除历史
session.clear()

# 模式切换
session.mode = "code"       # 设置
current_mode = session.mode  # 读取

# 元数据
session.state.metadata["custom_key"] = "value"
```

---

## 会话状态 (SessionState)

`SessionState` 是纯数据类，可序列化，不包含执行逻辑：

```python
from kora.runtime import SessionState

# 手动创建
state = SessionState.create(
    agent_name="my-agent",
    session_id="custom-id",  # 可选
)

# 添加消息
state.add_user_message("你好")
state.add_message(Message(role="assistant", content="嗨！"))

# 属性
state.id          # 会话 ID
state.agent_name  # Agent 名称
state.messages    # 消息历史
state.metadata    # 自定义元数据
state.created_at  # 创建时间
```

---

## Token 用量统计

```python
# 查看用量
usage = session.state.usage
usage.total_input_tokens      # 总输入 token
usage.total_output_tokens     # 总输出 token
usage.total_tokens            # 总 token
usage.total_cached_input_tokens  # 缓存命中
usage.total_reasoning_tokens     # 推理 token（如 deepseek-r1）
usage.compression_count       # 压缩次数
usage.last_compressed_at      # 最后压缩时间
```

---

## 消息格式

```python
from kora.kernel.types import Message

# 系统消息
Message(role="system", content="你是一个助手")

# 用户消息
Message(role="user", content="你好")

# 助手消息（纯文本）
Message(role="assistant", content="你好！有什么可以帮助你的？")

# 助手消息（带工具调用）
tool_calls = [ToolCall(id="call_1", name="search", arguments={"q": "weather"})]
Message(role="assistant", content=tool_calls)

# 工具结果
results = [ToolResult(call_id="call_1", name="search", content="晴天")]
Message(role="user", content=results)
```

---

## 上下文压缩 (ADR-015)

长会话的上下文管理：

```python
from kora.host.compression_policy import DefaultCompressionPolicy
from kora.runtime.compressor import SummarizerCompressor

agent = Agent(
    name="my-agent",
    tools=[...],
    model=model,
    # 自动压缩
    compression_policy=DefaultCompressionPolicy(
        threshold_ratio=0.8,      # 达到 80% 上下文窗口时触发
        keep_last_n_messages=10,   # 保留最近 10 条消息
        archive_raw_messages=True, # 归档原始消息
    ),
    compressor=SummarizerCompressor(
        model=summary_model,
        storage=storage,
    ),
)
```

在工作原理层面：

1. **检测**: 每次执行前检查上下文是否接近窗口上限
2. **决策**: Policy 决定是否需要压缩
3. **执行**: Compressor 总结历史消息，生成摘要
4. **应用**: 摘要代替原始消息加入上下文，原始消息归档

---

## 最佳实践

1. **总是 save()**: 重要会话完成后及时持久化
2. **使用有意义的 session_id**: 便于后续查找和恢复
3. **定期 clear()**: 对不需要的上下文及时清理
4. **配置压缩策略**: 长对话场景开启自动压缩
5. **监控 token 用量**: 避免超长上下文导致费用飙升

---

## 下一步

- [事件系统](./06-events.md) — 监控 Agent 的运行过程
- [进阶用法](./07-advanced.md) — 指令系统、扩展机制

---

<div align="right">
  <a href="./04-providers.md">← 上一页</a> ·
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a> ·
  <a href="./06-events.md">下一页 →</a>
</div>
