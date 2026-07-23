# 自定义 Quenda Code

学会配置和扩展 Quenda Code，打造属于你自己的编码 Agent。

---

## 配置方式

### 1. 命令行参数

```bash
# 指定工作空间
quenda code --workspace /path/to/project

# 指定模型
quenda code --provider deepseek --model deepseek-v4-flash

# 恢复会话
quenda code --session abc123

# 一次性任务
quenda code "帮我重构这个项目"
```

### 2. 配置文件

Quenda Code 的配置在内置 Agent 包的 `config.yaml` 中：

```
# 内置 Quenda Code 配置路径
quenda_code/agent/config.yaml
```

#### 模型配置

```yaml
model:
  provider: deepseek      # 默认提供商
  name: deepseek-v4-flash # 默认模型
```

#### 指令配置

```yaml
instructions:
  include:
    - instructions/coding.md
    - instructions/communication.md
```

#### 主题配置

```yaml
theme:
  # 预设：default, minimal, ascii, silent
  preset: default

  # 或单独覆盖
  agent_icon: "🐼"
  user_icon: "👤"
  success_icon: "✅"
  error_icon: "❌"
  warning_icon: "⚠️"
  tool_icon: "🔧"
  show_duration: true
```

#### 压缩配置

```yaml
compression:
  enabled: true
  threshold_ratio: 0.8      # 达到 80% 上下文时压缩
  keep_last_n_messages: 10   # 保留最近消息数
  archive_raw_messages: true # 归档原始消息
```

---

## 主题自定义

Quenda Code 支持四种内置主题预设：

### 默认主题 (Default)

使用彩色 emoji 图标，适合大多数终端：

```yaml
theme:
  preset: default
```

### 极简主题 (Minimal)

减少视觉噪音：

```yaml
theme:
  preset: minimal
```

### ASCII 主题

兼容不支持 emoji 的终端：

```yaml
theme:
  preset: ascii
```

### 静默主题 (Silent)

最小化输出，适合 CI/CD 场景：

```yaml
theme:
  preset: silent
```

### 完全自定义

```yaml
theme:
  agent_icon: "🤖"
  user_icon: "👤"
  success_icon: "✓"
  error_icon: "✗"
  warning_icon: "!"
  show_duration: false
  spinner_frames: ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
```

---

## 创建自定义 Agent

你可以基于 Quenda Code 的架构创建自己的 Agent。

### 目录结构

```
my-agent/
├── AGENT.md                  # 核心身份定义
├── config.yaml               # 配置
└── instructions/             # 指令文件
    ├── principles.md         # 工作原则
    ├── communication.md      # 沟通风格
    ├── coding.md             # 编码规范
    ├── mode-code.md          # Code 模式指令
    └── mode-architect.md     # Architect 模式指令
```

### AGENT.md 示例

```markdown
---
name: my-code-agent
version: 1.0.0
description: 我的自定义编码助手
---

你是一个专业的 Python 编码助手...

## 核心原则

- 代码优先，简洁至上
- ...
```

### config.yaml 示例

```yaml
model:
  provider: deepseek
  name: deepseek-v4-flash

instructions:
  include:
    - instructions/coding.md
    - instructions/communication.md

theme:
  agent_icon: "🐍"

compression:
  enabled: true
  threshold_ratio: 0.8
  keep_last_n_messages: 10
```

### 运行自定义 Agent

```bash
# 单次执行
quenda run --agent /path/to/my-agent "帮我做个事情"

# 交互模式
quenda run --agent /path/to/my-agent

# 指定模型
quenda run --agent /path/to/my-agent --provider openai --model gpt-4o
```

---

## 添加自定义命令

Agent 包支持通过 `extensions/commands/` 扩展斜杠命令。

### 创建自定义命令

```python
# my-agent/extensions/commands/deploy.py

from quenda.host.commands import Command, CommandResult, CommandContext

class DeployCommand:
    @property
    def name(self) -> str:
        return "deploy"

    @property
    def description(self) -> str:
        return "部署当前项目"

    @property
    def usage(self) -> str:
        return "/deploy [env]"

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        env = args.strip() or "staging"
        # 执行部署逻辑...
        return CommandResult(
            status="ok",
            message=f"✅ 已部署到 {env} 环境",
        )

commands = [DeployCommand()]
```

### 目录结构

```
my-agent/
├── AGENT.md
├── config.yaml
└── extensions/
    └── commands/
        └── deploy.py    # 自动加载
```

---

## 工作空间配置

Quenda 使用 `.quenda/workspace.yaml` 管理工作空间绑定：

```yaml
schema_version: 1
id: "ws_xxx"
name: "MyProject"
binding:
  created_at: "2026-06-30T10:00:00"
  path_hint: "/path/to/project"
```

这个文件通常自动生成，不需要手动管理。

---

## 下一步

- [使用技巧](./05-tips.md) — 最佳实践与常见问题
- [Quenda Agent 教程](../agent/01-quickstart.md) — 深入 SDK 开发

---

<div align="right">
  <a href="./03-modes.md">← 上一页</a> ·
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a> ·
  <a href="./05-tips.md">下一页 →</a>
</div>
