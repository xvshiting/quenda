# ADR-005: Quenda Code Agent MVP

## Status

Proposed

## Context

Quenda 是一个 Agent 框架，需要有一个官方 Code Agent 作为：
1. 框架功能的验收用例
2. 用户参考的 Agent 示例
3. 真实使用场景的压力测试

根据 `CLAUDE.md` 的原则：
- Code Agent 必须使用与外部 Agent 相同的公共 API
- 不引入特权分支或私有 API
- 代码特定行为属于 Code Agent 层，不属于 Kernel/Runtime

当前框架状态：
- **Kernel**: ✅ model-tool 循环完成
- **Runtime**: ✅ Agent/Session/Run 完成，事件流可用
- **Host**: 🚧 基础能力可用（loader, storage, identity, workspace, permission）
- **Tools**: ✅ `get_core_tools()` 提供 7 个 coding 工具
- **Providers**: ✅ 9 个内置 Provider，registry 可用

## Decision

### Code Agent 是普通 Agent

Code Agent MVP 必须通过公共 API 实现，不能有特权分支。

它由以下部分组成：

```text
agents/quenda-code/
├── AGENT.md           # Agent 定义（系统提示 + 元数据）
└── tools/             # Code Agent 特有工具（如果有）
```

### AGENT.md 内容

```markdown
---
name: quenda-code
version: 0.1.0
description: Quenda's official coding agent
default_provider: anthropic
default_model: claude-sonnet-4-20250514
---

You are Quenda Code, an expert coding assistant.

## Core Capabilities

You help developers with:
- Reading and understanding codebases
- Writing and modifying code
- Running commands and tests
- Debugging and problem-solving

## Working Principles

1. **Understand before acting**: Read relevant files first.
2. **Small, verified changes**: Make incremental changes and verify.
3. **Explain your reasoning**: Share your thought process.
4. **Respect the codebase**: Follow existing patterns and conventions.

## Tool Usage

- Use `list_files` to explore the workspace structure.
- Use `search_text` to find relevant code locations.
- Use `read_file` to understand specific files.
- Use `write_file` for new files.
- Use `apply_patch` for targeted modifications.
- Use `run_shell` to execute and verify.

When using tools:
- Always understand the current state before making changes.
- Verify changes by running relevant tests or commands.
- Handle errors gracefully and explain what went wrong.
```

### 启动方式

Code Agent 通过通用 CLI 启动，使用与其他 Agent 相同的公共 API：

```bash
# 通用方式 - 适用于任何 Agent
quenda run --agent agents/quenda-code --workspace /path/to/project "你的任务"

# 快捷方式 - quenda code 等价于 quenda run --agent agents/quenda-code
quenda code --workspace /path/to/project "你的任务"
```

### CLI 结构

```text
agents/
  quenda-code/
    AGENT.md           # Code Agent 定义

src/quenda/
  cli.py               # 通用 CLI：quenda run / quenda code
  host/                # Host loading/resolution
  runtime/             # Session/Run execution
```

**不创建独立的 `quenda_code` 包**。Code Agent 只是 `agents/quenda-code/AGENT.md`，通过公共 CLI 启动。

### CLI 实现

```python
# src/quenda/cli.py
import argparse
from pathlib import Path

from quenda.host import load_agent_from_markdown, FileStorage, DefaultUserResolver
from quenda.providers import get_provider_registry
from quenda.runtime import Agent
from quenda.tools import get_core_tools


def run_agent(
    agent_path: Path,
    workspace: Path,
    user_message: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    session_id: str | None = None,
):
    """Run an agent from AGENT.md path."""
    # 1. Load agent definition (public API)
    agent_config = load_agent_from_markdown(agent_path)

    # 2. Setup tools (public API)
    tools = get_core_tools(workspace)

    # 3. Resolve provider/model from AGENT.md or CLI args
    # (MVP: use CLI args or defaults, future: read from AGENT.md frontmatter)
    provider = provider or "anthropic"
    model = model or "claude-sonnet-4-20250514"

    # 4. Get model (public API)
    registry = get_provider_registry()
    model_instance = registry.get_model(provider, model)

    # 5. Setup storage (public API)
    user = DefaultUserResolver().resolve()
    storage = FileStorage(base_dir=user.quenda_dir)

    # 6. Create Agent (public API)
    agent = Agent(
        name=agent_config.name,
        system_prompt=agent_config.system_prompt,
        tools=tools,
        model=model_instance,
        storage=storage,
    )

    # 7. Run (public API)
    if session_id:
        session = agent.load_session(session_id)
        if session is None:
            session = agent.open_session(session_id=session_id)
    else:
        session = agent.open_session()

    return session.send_sync(user_message, on_event=print_event)


def print_event(event):
    """Simple event printer for MVP."""
    match event.type:
        case "run_started":
            print(f"\n🚀 Starting: {event.user_message[:50]}...")
        case "model_responded":
            if event.content:
                print(f"\n{event.content}")
            if event.tool_calls:
                print(f"\n🔧 Using tools: {', '.join(event.tool_calls)}")
        case "tool_executed":
            status = "❌" if event.is_error else "✓"
            print(f"\n{status} {event.tool_name}")
            if event.is_error:
                print(f"   Error: {event.result[:200]}")
        case "run_completed":
            print(f"\n✅ Completed in {event.total_steps} steps")
        case "error_occurred":
            print(f"\n❌ Error: {event.error_message}")


def main():
    parser = argparse.ArgumentParser(description="Quenda Agent Framework")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # quenda run --agent <path> "message"
    run_parser = subparsers.add_parser("run", help="Run an agent")
    run_parser.add_argument("--agent", type=Path, required=True, help="Path to AGENT.md")
    run_parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="Workspace directory")
    run_parser.add_argument("--provider", help="Model provider")
    run_parser.add_argument("--model", help="Model name")
    run_parser.add_argument("--session", help="Resume session by ID")
    run_parser.add_argument("message", help="Task or question")

    # quenda code "message" (shortcut for --agent agents/quenda-code)
    code_parser = subparsers.add_parser("code", help="Run Quenda Code Agent")
    code_parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="Workspace directory")
    code_parser.add_argument("--provider", help="Model provider")
    code_parser.add_argument("--model", help="Model name")
    code_parser.add_argument("--session", help="Resume session by ID")
    code_parser.add_argument("message", help="Task or question")

    args = parser.parse_args()

    if args.command == "run":
        run_agent(
            agent_path=args.agent,
            workspace=args.workspace,
            user_message=args.message,
            provider=args.provider,
            model=args.model,
            session_id=args.session,
        )
    elif args.command == "code":
        # Find agents/quenda-code/AGENT.md relative to package
        agent_path = Path(__file__).parent.parent.parent / "agents" / "quenda-code" / "AGENT.md"
        if not agent_path.exists():
            print(f"Error: Code Agent not found at {agent_path}")
            return 1
        run_agent(
            agent_path=agent_path,
            workspace=args.workspace,
            user_message=args.message,
            provider=args.provider,
            model=args.model,
            session_id=args.session,
        )


if __name__ == "__main__":
    main()
```

### 使用的工具

Code Agent MVP 使用 `get_core_tools()` 提供的 7 个工具：

| 工具 | 用途 |
|------|------|
| `list_files` | 查看目录结构 |
| `search_text` | 搜索代码内容 |
| `read_file` | 读取文件 |
| `write_file` | 创建新文件 |
| `apply_patch` | 修改现有文件 |
| `run_shell` | 执行 shell 命令 |
| `python_execution` | 运行 Python 代码 |

### 第一版 CLI/TUI 边界

MVP 只做最简单的 CLI：
- 接受用户消息
- 输出事件流（文本形式）
- 支持基础参数（workspace, provider, model, session）

**明确不做**：
- 完整 TUI（Rich/Textual 界面）
- 多轮交互 REPL
- 流式 token 输出
- Diff 高亮
- Markdown 渲染
- 进度条
- 文件选择器

这些属于 Interface 层的增强，不在 MVP 范围。

## 验收标准

Code Agent MVP 成功的标准是它能完成以下任务：

### 1. 基础问答

```bash
quenda code --workspace /path/to/project "What does this project do?"
```

期望：
- Agent 能理解项目结构
- 能读取 README 或主要文件
- 能给出合理回答

### 2. 代码探索

```bash
quenda code --workspace /path/to/project "Where is the main entry point?"
```

期望：
- Agent 能搜索和浏览代码
- 能识别入口点
- 能解释推理过程

### 3. 简单修改

```bash
quenda code --workspace /path/to/project "Add a docstring to the main function"
```

期望：
- Agent 能定位目标
- 能生成合理的修改
- 能应用补丁

### 4. 命令执行

```bash
quenda code --workspace /path/to/project "Run the tests and report failures"
```

期望：
- Agent 能执行 shell 命令
- 能解析输出
- 能报告结果

## 框架验证点

Code Agent MVP 应该逼着我们验证：

### AGENT.md 加载
- [ ] `load_agent_from_markdown()` 能正确解析 AGENT.md
- [ ] 系统提示被正确传递给 model
- [ ] 元数据（name, version 等）可用

### 工具系统
- [ ] `get_core_tools()` 返回的工具能正常工作
- [ ] 工具在 workspace 范围内执行
- [ ] 错误被正确处理和报告

### Provider Registry
- [ ] `get_provider_registry()` 能获取 registry
- [ ] `registry.get_model()` 能创建 model
- [ ] Model 能与 Kernel 正常交互

### Runtime 执行
- [ ] `Agent` 类能创建 agent 实例
- [ ] `session.send()` 能执行消息
- [ ] 多轮对话通过 session 持续

### 事件流
- [ ] 事件被正确触发和传递
- [ ] `on_event` 回调能接收所有事件
- [ ] 事件信息足够展示执行过程

### Host 能力
- [ ] `DefaultUserResolver` 能解析用户
- [ ] `FileStorage` 能持久化 session/run
- [ ] Session 能被保存和恢复

### Host 缺失暴露
- [ ] Workspace binding 是否需要最小实现？
- [ ] Permission policy 是否需要配置？
- [ ] 用户配置从哪里读取？

## 明确不做

MVP 阶段明确排除：

1. **Skills** - 留给后续 Trial
2. **多用户** - 单用户即可
3. **Server mode** - 只做 CLI
4. **完整 TUI** - 只做简单文本输出
5. **高级权限系统** - 使用默认 permissive policy
6. **Session browser** - 不做 session 管理 UI
7. **Fancy diff UI** - 只输出文本
8. **流式 token 输出** - 只输出完整消息
9. **多 Agent 协作** - 单 Agent 即可
10. **远程 Provider** - 只用内置 Provider

## 与现有 TODO 的关系

Code Agent MVP 作为新的 Trial 项：

```markdown
### Trial: Quenda Code Agent MVP

- [ ] 创建 `agents/quenda-code/AGENT.md`
- [ ] 创建最小 CLI 入口
- [ ] 验证框架公共 API 可用性
- [ ] 验收测试（基础问答、代码探索、简单修改、命令执行）
- [ ] 记录框架暴露的问题和改进点
```

P0/P1 稳定化工作并行推进，Code Agent 暴露的问题回填到基础设施。

## Consequences

### Positive

- 有真实 Agent 验证框架设计
- 框架 API 的可用性被实战检验
- 发现的问题能指导 P0/P1 优化方向
- 为外部 Agent 作者提供参考示例

### Negative

- 可能发现框架 API 的不足，需要调整
- Host 缺失能力会被提前暴露
- 可能需要临时绕过某些缺失功能

### Mitigation

- 发现的 API 问题记录到 TODO，统一修复
- 临时绕过的功能标注清楚，不引入技术债
- 保持 Code Agent 只用公共 API 的原则

## Recommendation

采纳此 ADR，开始 Code Agent MVP 开发：

1. 创建 `agents/quenda-code/AGENT.md`
2. 创建 `src/quenda/cli.py`（通用 CLI：`quenda run` / `quenda code`）
3. 在 `pyproject.toml` 中注册 `quenda` 命令入口点
4. 用验收测试验证
5. 记录暴露的问题
