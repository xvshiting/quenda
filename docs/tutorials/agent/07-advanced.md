# 进阶用法

指令系统、Agent 包、扩展机制、安全策略。

---

## 指令系统 (Instruction System)

Quenda 的指令系统允许将 Agent 的提示词拆分为多个文件，按需组合。

### 指令来源

```
Agent 指令的优先级（从高到低）：
1. mode-<name>.md  — 模式文件（根据当前模式加载）
2. 用户 workspace 覆盖
3. instructions/*.md  — 分包指令
4. AGENT.md          — 核心身份定义
```

### 组装流程

```python
from quenda.host.instructions import (
    InstructionComposer,
    InstructionSource,
    resolve_instruction_sources,
)

# 解析所有指令源
sources = resolve_instruction_sources(
    agent_package_path="/path/to/agent",
    agent_name="my-agent",
    agent_md_content="...",
    agent_instructions=[...],
    workspace_path="/path/to/workspace",
    user=user,
)

# 模板上下文
from quenda.host.instructions import TemplateContext
context = TemplateContext(
    agent_name="my-agent",
    agent_version="1.0.0",
    workspace_id="ws_xxx",
    workspace_path="/path/to/workspace",
    user_id="user-1",
    model_provider="deepseek",
    model_name="deepseek-v4-flash",
    date="2025-06-24",
    session_id="session-xxx",
)

# 组装最终提示词
composer = InstructionComposer(context)
final_prompt = composer.compose(sources)
```

### 模式文件

模式文件 (`mode-<name>.md`) 根据当前交互模式动态加载：

```python
# 在 Session 中切换模式
session.mode = "code"       # 加载 mode-code.md
session.mode = "architect"  # 加载 mode-architect.md
session.mode = "chat"       # 不额外加载模式文件
```

---

## Agent 包 (Agent Package)

一个完整的 Agent 包目录结构：

```
my-agent/
├── AGENT.md                  # 核心身份定义（必需）
├── config.yaml               # 机器可读配置（可选）
├── instructions/             # 指令文件（可选）
│   ├── principles.md
│   ├── communication.md
│   ├── coding.md
│   ├── mode-code.md
│   └── mode-architect.md
└── extensions/               # 扩展目录（可选）
    └── commands/
        └── custom.py         # 自定义斜杠命令
```

### 加载 Agent 包

```python
from quenda.host import load_agent_package

pkg = load_agent_package("/path/to/my-agent")

pkg.name        # Agent 名称
pkg.version     # 版本号
pkg.description # 描述
pkg.agent_md    # AGENT.md 内容
pkg.config      # AgentConfigYaml
pkg.instructions # 指令文件列表
```

### AGENT.md 格式

```markdown
---
name: my-agent
version: 1.0.0
description: 我的自定义 Agent
---

你是一个专家助手...
```

### config.yaml 格式

```yaml
model:
  provider: deepseek
  name: deepseek-v4-flash

instructions:
  include:
    - instructions/coding.md
    - instructions/communication.md

theme:
  preset: default  # 或 minimal / ascii / silent
  # 或自定义覆盖
  agent_icon: "🤖"
  show_duration: true

compression:
  enabled: true
  threshold_ratio: 0.8
  keep_last_n_messages: 10
  archive_raw_messages: true
  compression_model: "deepseek-v4-flash"
```

---

## 扩展机制 (Extensions)

### 自定义命令 (ADR-010)

在 `extensions/commands/` 中添加 `.py` 文件：

```python
# extensions/commands/greet.py

from quenda.host.commands import Command, CommandResult, CommandContext
from quenda.runtime.commands import ReplAction

class GreetCommand:
    @property
    def name(self) -> str:
        return "greet"

    @property
    def description(self) -> str:
        return "自定义问候命令"

    @property
    def usage(self) -> str:
        return "/greet [name]"

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        name = args.strip() or "World"
        return CommandResult(
            status="ok",
            message=f"Hello, {name}! 👋",
        )

# 导出方式一：命令列表
commands = [GreetCommand()]

# 导出方式二：注册函数
# def register(registry):
#     registry.register(GreetCommand())
```

### 自定义交互 (ADR-012)

在 `extensions/interactions/` 中添加 `.py` 文件：

```python
# extensions/interactions/confirm_code.py

from quenda.host.interactions import (
    Interaction, InteractionKind, InteractionRequest,
    InteractionResponse, InteractionContext,
)

class CodeReviewInteraction(Interaction):
    @property
    def kind(self) -> InteractionKind:
        return InteractionKind.CONFIRM

    @property
    def description(self) -> str:
        return "代码审查确认"

    def validate(self, request, context):
        errors = []
        if request.kind != "confirm":
            errors.append("此交互需要 confirm 类型")
        return errors

# 导出
interactions = [CodeReviewInteraction()]
```

---

## 安全策略

### 工作空间边界

所有文件操作工具（`ReadFileTool`、`WriteFileTool` 等）都强制工作空间边界检查：

```python
from quenda.tools.base import BaseTool

class MyTool(BaseTool):
    def execute(self, **kwargs):
        path = kwargs["path"]
        try:
            # 自动验证：路径必须在工作空间内
            safe_path = self._validate_workspace_path(str(path))
        except ValueError as e:
            return ToolResult(
                call_id="", name=self.name,
                content=f"安全错误: {e}", is_error=True,
            )
```

### 权限策略

```python
from quenda.host.permission import (
    create_default_policy,
    HostPermissionPolicy,
    PermissivePolicy,
)

# 默认策略（推荐）：允许常规操作，阻止危险操作
policy = create_default_policy()

# 宽松策略（开发环境）
policy = PermissivePolicy()
```

### 敏感操作

内置的安全检查包括：

- 不允许访问工作空间外的文件（`..` 路径穿越）
- Shell 命令有超时限制
- Python 执行在沙箱中进行（仅允许标准库子集）
- HTTP 请求有 SSRF 保护

---

## 主题系统 (ADR-014)

自定义 CLI 界面外观：

```python
from quenda.interface.theme import InterfaceTheme

# 内置预设
theme = InterfaceTheme()        # 默认（彩色 emoji）
theme = InterfaceTheme.minimal()  # 极简
theme = InterfaceTheme.ascii()    # ASCII 兼容
theme = InterfaceTheme.silent()   # 静默模式

# 自定义
theme = InterfaceTheme(
    agent_icon="🐼",
    user_icon="👤",
    success_icon="✅",
    error_icon="❌",
    warning_icon="⚠️",
    tool_icon="🔧",
    show_duration=True,
    spinner_frames=["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
)
```

在 config.yaml 中配置：

```yaml
theme:
  preset: minimal
  # 或
  agent_icon: "🔮"
  show_duration: false
```

---

## 底层 Kernel

如果你需要更底层的控制，可以直接使用 Kernel：

```python
from quenda.kernel import Kernel, Message

# 创建 Kernel（纯同步，无 Session/AI Agent 概念）
kernel = Kernel(model=model, tools=my_tools)

# 直接运行
messages = [
    Message(role="system", content="你是一个助手"),
    Message(role="user", content="你好"),
]

for step in kernel.run(messages):
    if step.type == "model":
        print(f"模型说: {step.content}")
    elif step.type == "tool":
        print(f"工具结果: {step.content}")
```

---

## 下一步

- [API 参考](./08-references.md) — 完整 API 速查表
- [Quenda Code 使用教程](../code/01-quickstart.md) — 使用 Quenda Code CLI

---

<div align="right">
  <a href="./06-events.md">← 上一页</a> ·
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a> ·
  <a href="./08-references.md">下一页 →</a>
</div>
