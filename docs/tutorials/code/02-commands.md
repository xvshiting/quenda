# 命令系统

Kora Code REPL 内置了丰富的斜杠命令，用于管理会话、切换模型、查看状态等。

---

## 命令概览

所有命令以 `/` 开头：

| 命令 | 用途 |
|------|------|
| `/help` | 查看所有可用命令 |
| `/clear` | 清除对话历史 |
| `/reset` | 重置会话（清除历史 + 恢复系统提示词） |
| `/exit` | 退出 |
| `/mode` | 切换交互模式 |
| `/model` | 查看/切换模型 |
| `/session` | 会话管理 |
| `/context` | 查看上下文信息 |
| `/status` | 查看会话状态（含 token 用量） |
| `/compress` | 手动压缩上下文 |
| `//` | 显示命令菜单 |

---

## 命令详解

### `/help` — 帮助

```text
/help         显示所有命令列表
/help model   显示某个命令的详细帮助
```

示例输出：

```
**Available commands:**

  /clear
        清除会话消息历史

  /exit
        退出交互式会话

  /help [command]
        显示可用命令

  ...
```

---

### `/mode` — 切换模式

```text
/mode             查看当前模式
/mode chat        切换为聊天模式
/mode code        切换为代码模式
/mode architect   切换为架构模式
```

模式的作用：

| 模式 | 图标 | 适用场景 | 行为变化 |
|------|------|---------|---------|
| `chat` | 💬 | 一般问答 | 基础对话，无特殊约束 |
| `code` | 💻 | 编程任务 | 聚焦编码，要求写出完整代码 |
| `architect` | 🏗 | 架构设计 | 深入分析，讨论取舍，画架构图 |

切换模式后，Agent 会加载对应的模式指令文件（`mode-<name>.md`），改变其行为。

---

### `/model` — 切换模型

```text
/model                        查看当前模型
/model deepseek/deepseek-v4-flash   切换到指定提供商/模型
/model gpt-4o                 自动搜索匹配的模型
```

示例：

```
> /model
**Current model:** `deepseek/deepseek-v4-flash`

> /model anthropic/claude-sonnet-4-20250514
✅ Switched to `anthropic/claude-sonnet-4-20250514`.
```

---

### `/clear` — 清除历史

```text
/clear   清除当前会话的所有消息
```

清理后上下文重置，但系统提示词保留。适用于开始新话题时。

---

### `/reset` — 重置会话

```text
/reset   清除消息 + 恢复原始系统提示词
```

比 `/clear` 更彻底——不仅清除消息历史，还会重新加载原始的系统提示词（包括模式文件）。

---

### `/session` — 会话管理

```text
/session info    查看当前会话信息
/session list    列出所有保存的会话
```

示例：

```
> /session info
**Session Info:**
  ID: `abc123ef-...`
  Agent: kora-code
  Messages: 15
  Mode: `code`
  Model: `deepseek/deepseek-v4-flash`

> /session list
**Saved sessions:**
  1. `abc123ef...` (15 msgs, 2025-06-24 10:30)
  2. `def456gh...` (8 msgs, 2025-06-23 14:20)
```

恢复会话需要在启动时指定：

```bash
kora code --session <session-id>
```

---

### `/context` — 查看上下文

```text
/context           查看系统提示词
/context tools     查看可用工具列表
/context session   查看会话状态
```

示例：

```
> /context tools
**Available Tools (8):**

  • `list_files` — 列出文件和目录
  • `search_text` — 搜索文本内容
  • `read_file` — 读取文件内容
  • `write_file` — 创建新文件
  • `apply_patch` — 应用修改到文件
  • `execute_python` — 在沙箱中执行 Python 代码
  • `run_shell` — 执行 Shell 命令
  • `request_interaction` — 向用户请求交互
```

---

### `/status` — 会话状态

```text
/status   查看会话的详细状态信息
```

显示内容：

- 会话 ID
- 消息数量
- 当前模式
- 当前模型
- Token 用量（输入/输出/缓存/推理）
- 压缩信息（次数、摘要块数、归档数）

---

### `/compress` — 手动压缩

```text
/compress        自动判断是否需要压缩
/compress force  强制压缩
```

手动触发上下文压缩。通常当会话消息较多、接近上下文窗口上限时使用。

---

## 命令菜单

在 REPL 中输入单斜杠 `/` 即可快速显示命令菜单：

```
> /
```

这是一个快捷方式，等价于 `/help`。

---

## 自定义命令

Agent 包可以在 `extensions/commands/` 中添加自定义命令。例如安装 kora-code 后自带的 `status` 命令：

```python
# extensions/commands/status.py
# 提供 /status 命令
```

你可以在自己的 Agent 包中扩展命令，详见 [自定义 Agent 教程](./04-customization.md)。

---

## 下一步

- [模式系统](./03-modes.md) — 深入了解三种交互模式
- [使用技巧](./05-tips.md) — 最佳实践

---

<div align="right">
  <a href="./01-quickstart.md">← 上一页</a> ·
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a> ·
  <a href="./03-modes.md">下一页 →</a>
</div>
