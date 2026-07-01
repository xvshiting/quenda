# REPL 命令提示设计备注

## 功能

REPL 支持实时命令提示，用户输入 `/` 时自动显示可用命令列表。

## 实现

### 优先级策略

1. **prompt_toolkit 优先**：如果安装了 `prompt_toolkit`，使用 `CommandCompleter` 提供实时补全提示
2. **降级到基本 REPL**：如果没有 `prompt_toolkit`，用户输入 `/` 后回车显示命令菜单

### 降级保证

- CLI 模块导入时不依赖 `prompt_toolkit`
- `HAS_PROMPT_TOOLKIT` 标志控制使用哪种模式
- `_run_repl_basic()` 函数提供无依赖的基本 REPL
- `CommandCompleter` 仅在 `prompt_toolkit` 可用时定义

### 补全数据源统一

所有命令都通过 `CommandRegistry` 管理：
- 内置命令（`/help`, `/mode`, `/model` 等）
- Agent 本地命令（`extensions/commands/*.py`）
- 动态加载的命令扩展

`CommandCompleter` 从同一个 `registry` 获取候选项。

### 用户体验

```
>>> /
/clear     Clear session message history
/context   Show current context
/exit      Exit the interactive session
/help      Show available commands
/mode      Show or switch interaction mode
/model     Show or switch the current model
/reset     Reset session
/session   Show session info
/status    Show agent and session status
```

提示轻量，不打断用户输入流程。
