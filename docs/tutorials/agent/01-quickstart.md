# 快速开始 — Quenda Agent

本章教你从零搭建第一个 Quenda Agent。

---

## 安装

```bash
pip install quenda
```

验证安装：

```python
import quenda
print(quenda.__version__)
# 输出: 0.1.0
```

> **依赖**: Python 3.12+

---

## 你的第一个 Agent

### 1. 获取模型

Quenda 内置了 20+ 个模型提供商的支持。通过 registry 获取模型实例：

```python
from quenda import get_provider_registry

registry = get_provider_registry()
model = registry.get_model("deepseek", "deepseek-v4-flash")
```

环境变量中设置 API Key：

```bash
export DEEPSEEK_API_KEY="sk-xxx"
```

### 2. 定义工具

使用 `@tool` 装饰器快速定义工具：

```python
from quenda import tool

@tool
def echo(msg: str) -> str:
    """返回输入的消息。"""
    return f"你说了: {msg}"

@tool
def add(a: int, b: int = 0) -> int:
    """两个数相加。"""
    return a + b
```

### 3. 创建 Agent

```python
from quenda import Agent

agent = Agent(
    name="my-agent",
    system_prompt="你是一个乐于助人的助手。",
    tools=[echo, add],
    model=model,
)
```

### 4. 运行

两种执行模式：

**一次性对话 (run):**

```python
import asyncio

result = asyncio.run(agent.run("你好！帮我计算 3 + 5。"))
print(result)
```

**持久会话 (open_session):**

```python
session = agent.open_session()

async def chat():
    r1 = await session.send("3 + 5 等于多少？")
    print(r1)

    # 上下文保持
    r2 = await session.send("加上 2 呢？")
    print(r2)

asyncio.run(chat())
```

---

## 使用内置工具

Quenda 提供了开箱即用的核心工具集：

```python
from quenda.tools import get_core_tools
from quenda import Agent, get_provider_registry

registry = get_provider_registry()
model = registry.get_model("deepseek", "deepseek-v4-flash")

# 8 个核心工具
tools = get_core_tools("/path/to/workspace")

agent = Agent(
    name="code-agent",
    system_prompt="你是一个编码助手。",
    tools=tools,
    model=model,
)
```

`get_core_tools()` 返回的工具：

| 工具 | 用途 |
|------|------|
| `ListFilesTool` | 列出文件/目录 |
| `SearchTextTool` | 全文搜索 |
| `ReadFileTool` | 读取文件内容 |
| `WriteFileTool` | 创建新文件 |
| `ApplyPatchTool` | 安全修改文件 |
| `PythonExecutionTool` | 沙箱执行 Python |
| `RunShellTool` | 执行 Shell 命令 |
| `RequestInteractionTool` | 向用户请求交互 |

---

## 完整示例

一个可运行的最小 Agent：

```python
import asyncio
from quenda import Agent, tool, get_provider_registry

# 1. 定义工具
@tool
def get_weather(city: str) -> str:
    """查询城市天气。"""
    # 这里只是模拟
    return f"{city} 今天晴天，25°C"

# 2. 获取模型
registry = get_provider_registry()
model = registry.get_model("deepseek", "deepseek-v4-flash")

# 3. 创建 Agent
agent = Agent(
    name="weather-agent",
    system_prompt="你是天气助手，使用工具查询天气。",
    tools=[get_weather],
    model=model,
)

# 4. 运行
result = asyncio.run(agent.run("北京今天天气怎么样？"))
print(result)
```

---

## 下一步

- [Agent 基础](./02-agent-basics.md) — 深入理解 Agent 配置
- [工具系统](./03-tools.md) — 掌握所有工具用法
- [模型提供者](./04-providers.md) — 切换不同的 AI 模型

---

<div align="right">
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a> ·
  <a href="./02-agent-basics.md">下一页 →</a>
</div>
