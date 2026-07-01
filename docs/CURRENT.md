# Quenda Current Design State

> Last updated: 2026-06-30

## 项目概述

Quenda 是一个轻量级 Python Agent 框架，采用三层架构设计。

## 项目管理快照

最新项目诊断与规划记录见 [PM-REPORT-2026-06-23.md](PM-REPORT-2026-06-23.md)。
技术雷达与架构决策框架见 [TECH-RADAR.md](TECH-RADAR.md)。
Skills 能力包机制见 [decisions/002-skills-capability-packages.md](decisions/002-skills-capability-packages.md)。
Host 命名与边界说明见 [decisions/003-host-name-and-boundary.md](decisions/003-host-name-and-boundary.md)。
Workspace 身份与用户 Agent 状态模型见 [decisions/004-workspace-identity-and-user-agent-state.md](decisions/004-workspace-identity-and-user-agent-state.md)。
Code Agent MVP 设计见 [decisions/005-quenda-code-agent-mvp.md](decisions/005-quenda-code-agent-mvp.md)。
Interface 事件渲染策略见 [decisions/006-interface-event-rendering.md](decisions/006-interface-event-rendering.md)。
Instruction 层与 Scope Overlay 见 [decisions/007-instruction-layer-and-scope-overlay.md](decisions/007-instruction-layer-and-scope-overlay.md)。
Tool Schema 唯一来源原则见 [decisions/008-tool-schema-single-source.md](decisions/008-tool-schema-single-source.md)。
工具输出折叠策略见 [decisions/009-tool-output-folding.md](decisions/009-tool-output-folding.md)。
Agent 命令扩展机制见 [decisions/010-agent-command-extensions.md](decisions/010-agent-command-extensions.md)。
REPL 命令提示见 [decisions/011-repl-command-hints.md](decisions/011-repl-command-hints.md)。
交互请求与选择控件见 [decisions/012-interaction-requests-and-choice-controls.md](decisions/012-interaction-requests-and-choice-controls.md)。
Agent 包分发模型见 [decisions/013-agent-package-distribution.md](decisions/013-agent-package-distribution.md)。
上下文压缩与分层存储见 [decisions/015-context-compression-and-storage.md](decisions/015-context-compression-and-storage.md)。

## 当前状态

### ✅ 已完成

- **Phase 0-6**: 框架核心全部完成

- **Trial: Quenda Code Agent MVP ✅**
  - `agents/quenda-code/AGENT.md`
  - `src/quenda/cli.py`（`quenda run` / `quenda code`）
  - REPL 交互模式
  - Session 持久化
  - 验收测试全部通过
  - 详见 [ADR-005](decisions/005-quenda-code-agent-mvp.md)

- **Trial: Interface 事件渲染 ✅**
  - 增强 `ToolExecuted` 事件（arguments, duration_ms, result_lines）
  - 框架注入 `_summary` 参数，LLM 生成工具描述
  - `ConsoleRenderer` 渲染器
  - 详见 [ADR-006](decisions/006-interface-event-rendering.md)
  - 当前 REPL 只展示 `summary`，不显示工具名，也不做步骤折叠

- **Interaction Request 机制 ✅**
  - `InteractionRequest` / `InteractionResponse` 结构化交互协议
  - `InteractionRegistry` + `Choice/Confirm/Input/Menu` 内建交互类型
  - Agent-local `extensions/interactions/*.py` 扩展加载
  - `render_interaction_request()` 提供终端可读的选择渲染
  - **LLM 发起交互**：`RequestInteractionTool` 框架保留 tool
    - LLM 调用 `request_interaction` tool 发起 choice/confirm/input/menu
    - Host 层在 Kernel 完成后检测 tool call
    - Interface 层展示并收集用户响应
    - 用户选择后注入 user message，启动下一轮

- **ADR-004 Workspace 身份与状态模型 ✅**
  - `.quenda/workspace.yaml` workspace binding
  - `~/.quenda/users/<user>/agents/<agent>/workspaces/<id>/` 存储布局
  - `WorkspaceResolver` 实现
  - Session 持久化正确包含 assistant message
  - JSON 存储 UTF-8 编码

- **ADR-007 Instruction Layer ✅**
  - `InstructionScope`, `InstructionSource`, `TemplateContext`, `InstructionComposer`
  - `AgentPackage`, `AgentConfigYaml`, `load_agent_package()`
  - Workspace `INSTRUCTIONS.md` scope overlay
  - 模板变量替换（白名单）
  - 详见 [decisions/007-instruction-layer-and-scope-overlay.md](decisions/007-instruction-layer-and-scope-overlay.md)

- **REPL/Slash Commands 稳定化 ✅**
  - `ReplAction` 枚举替代哨兵字符串
  - `ReplRuntime` 封装 REPL 状态管理和命令分发
  - `CommandContext` 公共 API（`get_system_prompt()`, `get_tools()`, `get_mode()`）
  - Session/Agent 添加只读属性（`system_prompt`, `tools`, `mode`）
  - CLI 层精简为纯 I/O，状态管理移至 Host 层
  - 命令补全支持（`Command.get_completions()`）
  - 实时命令提示：输入 `/` 自动显示候选命令
  - `prompt_toolkit` 优先，无依赖时降级到基本 REPL

- **ADR-010 Agent 命令扩展 ✅**
  - `extensions/commands/*.py` 加载契约
  - `load_agent_commands()` 动态加载命令模块
  - `commands` 列表或 `register()` 函数导出方式
  - 用户命令可覆盖内置命令
  - 示例：`agents/quenda-code/extensions/commands/status.py`

- **ADR-002 Skills Framework ✅**
  - **Skills 是 Host 层的能力包机制**
  - `Skill = instructions + resource catalog + optional tools + optional policy metadata`
  - 渐进披露：Discovery（仅 frontmatter）→ Activation（指令）→ Usage（资源）
  - 三层优先级：`user_workspace` > `agent_package` > `user`
  - 用户隔离：`~/.quenda/users/<user>/workspaces/<ws_id>/skills/`
  - Agent 包可打包 Skills：`<agent-package>/skills/`
  - `/skill` REPL 命令：`list`, `activate`, `deactivate`, `resources`
  - Framework Contract：所有 Agent 自动获得 Skills 路径约定
  - 详见 [decisions/002-skills-capability-packages.md](decisions/002-skills-capability-packages.md)
  - 文档：[docs/skills.md](skills.md)

- **ADR-024 Agent-Local Custom Tool Extensions ✅**
  - Agent 通过 `extensions/tools/*.py` 定义自定义工具
  - 支持 `tools` 列表或 `register(builder)` 函数导出
  - `config.yaml` 中通过 `tools.include` 请求自定义工具
  - ToolRegistryBuilder 管理工具注册和冲突检测
  - 自定义工具不能覆盖内置工具名称
  - 详见 [decisions/024-agent-local-custom-tool-extensions.md](decisions/024-agent-local-custom-tool-extensions.md)

- **Agent Package Capability Declaration MVP ✅**
  - Agent 通过 `config.yaml` 声明能力需求
  - **工具声明**：
    - `tools.bundles: ["network"]` - 请求网络工具集
  - **沙盒扩展声明**：
    - `execution.python.allowed_modules: ["requests"]` - 请求额外模块
  - **Host Resolver**：
    - `_resolve_tools()` - 根据配置组装工具集
    - `_resolve_sandbox_config()` - 合并沙盒允许列表
  - **安全原则**：
    - Agent 只能**请求**能力，不能**强制**获得
    - Host 保持对最终能力集的控制权
    - 保守默认值：无显式请求 = 最小能力
    - 阻止列表始终生效，不能被覆盖

### 🚧 进行中

- **P1: Provider 合约稳定化**
  - 补充 registry/model lookup 兼容性测试
  - 验证所有内置 Provider 可发现、可创建 Model

### 📋 待做

- **P2: Host 安全与权限**
  - 工具权限控制系统
  - `.quenda/workspace.yaml` 写保护
  - 身份认证、多租户支持
  - 上下文重建（已完成：`ContextRebuilder` + `set_system_prompt` + CLI 接入）

参见 TODO.md

## 架构层级

### Kernel 层（最底层）

**职责**：执行单个 model-tool 循环

**核心概念**：
- `Model` - 模型调用接口
- `Tool` - 工具接口
- `Loop` - 核心循环逻辑

**设计原则**：
- 同步执行，便于测试
- 通过依赖注入接收 Model 和 Tools
- 不依赖外部服务

**状态**：✅ 已完成

### Runtime 层（中间层）

**职责**：管理 Agent、Session、Run 语义

**核心概念**：
- `Agent` - Agent 定义
- `Session` - 会话管理
- `Run` - 单次执行

**设计原则**：
- 异步实现，处理并发
- 提供事件流供上层观察
- 协调 Kernel 执行

**状态**：✅ 已完成

### Host 层（最外层）

**职责**：作为受信任的外层宿主环境，在 Runtime 执行前完成加载、授权、持久化和组合。

**当前实现**：
- `host/runner.py` — `setup_agent()` 高层 API，串起 15 步编排
  - `AgentSetup` 数据结构，携带所有 resolved pieces
  - `_resolve_tools()` — 能力声明解析，组装工具集
  - `_resolve_sandbox_config()` — 沙盒配置解析
- `host/loader.py` — 加载 agent package、命令扩展、交互扩展、能力声明配置
  - `load_agent_package()` — AGENT.md + config.yaml
  - `load_agent_commands()` — extensions/commands/*.py
  - `load_agent_interactions()` — extensions/interactions/*.py
  - `find_builtin_agent()` — 定位内置 agent 目录
  - `ToolsConfig`, `ExecutionConfig`, `PythonExecutionConfig` — 能力声明配置类
- `host/repl.py` — `ReplRuntime` REPL 状态管理和命令分发
- `host/commands.py` — 命令系统（ADR-008）
- `host/interactions.py` — 交互请求系统（ADR-012）
- `host/context.py` — `ContextRebuilder` 上下文重建
- `host/workspace.py` — `WorkspaceResolver` workspace binding
- `host/storage.py` — `FileStorage` 持久化
- `host/identity.py` — `DefaultUserResolver` 用户身份
- `host/instructions.py` — `InstructionComposer` 指令组合，包含 `FRAMEWORK_CONTRACT`
- `host/permission.py` — 权限控制
- `host/skill/` — Skills 框架（ADR-002）
  - `models.py` — `SkillFrontmatter`, `SkillQuendaMetadata`, `SkillResource`
  - `package.py` — `SkillPackage` dataclass
  - `discovery.py` — `SkillDiscovery` 发现技能，三层优先级
  - `activation.py` — `SkillActivator` 激活/停用技能
  - `resources.py` — `ResourceResolver` 加载技能资源

**不负责**：
- Kernel 的 model-tool loop 语义
- Runtime 的 Agent / Session / Run / Event 语义
- UI、CLI、Server 等具体界面形态
- Provider 协议内部细节
- Tool 具体实现逻辑

**状态**：✅ 已正式化

### Interface 层（交互表现层）

**职责**：把 Host / Runtime 提供的状态和事件转成用户可操作的交互体验。

**当前实现**：
- `interface/console.py` — `ConsoleRenderer` 负责把 Runtime 事件渲染成可读文本
- `interface/interaction.py` — `render_interaction_request()` 负责把结构化交互请求渲染成可读选择
- `interface/repl.py` — REPL 输入处理、命令提示、补全
  - `create_repl_input()` — 创建输入处理器
  - `print_command_menu()` — 打印命令菜单
  - `CommandCompleter` — 命令补全（prompt_toolkit）
  - 降级：无 `prompt_toolkit` 时使用基本 `input()`
- `interface/markdown.py` — Markdown-lite 渲染
  - 支持：**bold**、`code`、代码块、列表、标题
  - 不支持：链接、表格、图片

**不负责**：
- Agent / Session / Run 语义
- 具体命令的状态变更规则
- 上下文重组逻辑
- 工具实现和工具 schema
- Kernel 的 model-tool loop

**边界原则**：
- `cli.py` 是入口，只做参数解析和路由分发
- `interface/` 负责视觉和输入交互适配
- `host/` 负责编排、命令注册和状态管理
- `runtime/` 和 `kernel/` 不应依赖任何具体 UI 实现

**状态**：✅ 已正式化

### CLI 入口层

**职责**：参数解析、路由分发、I/O 输出。

**当前实现**：
- `cli.py` — 仅 ~280 行
  - `main()` — argparse 参数定义和路由
  - `run_agent()` — one-shot 执行
  - `run_repl()` — REPL 执行
  - 调用 `host.setup_agent()` 完成编排
  - 调用 `interface.create_repl_input()` 处理输入

**不负责**：
- 13 步编排逻辑（已移到 host/runner.py）
- 命令执行逻辑（host/repl.py）
- 界面渲染（interface/）

**状态**：✅ 已精简

## 内置工具

### 能力声明（Capability Declaration）

Agent 通过 `config.yaml` 声明能力需求，Host 解析并组装最终工具集：

```yaml
# config.yaml
tools:
  bundles:
    - core     # filesystem + execution + interaction
    - network  # HTTP, web fetch, web search
  include:
    - my_custom_tool  # 从 extensions/tools/ 加载的自定义工具

execution:
  python:
    allowed_modules:
      - requests  # 请求扩展 Python 沙盒
      - httpx
```

**语义原则**：
- 所有 bundle 和 include 都是 **request**
- Host 解析最终能力集（未来可加入 trust/permission policy）

**兼容性默认**：
- 如果 `tools.bundles` 缺失或为空，Host 默认按 `["core"]` 处理
- 这是兼容性措施，不是 "core 天然不需要申请"
- 未来版本可能要求所有能力显式声明

**安全边界**：
- Agent 只能**请求**能力，不能**强制**获得
- 沙盒阻止列表始终生效，不能被覆盖
- 自定义工具不能覆盖内置工具名称

**自定义工具**（ADR-024）：
- 定义：`extensions/tools/*.py`
- 导出：`tools = [...]` 或 `register(builder)`
- 请求：`tools.include: ["my_tool"]`

### 文件系统工具（5 个，capability-based）

| 工具 | 功能 | 覆盖 |
|-----|------|-----|
| ListFilesTool | 列出文件/目录 | ls, find, tree |
| SearchTextTool | 搜索文本（ripgrep 优先） | grep, rg |
| ReadFileTool | 读取文件（支持行范围） | cat, head, tail, sed -n |
| WriteFileTool | 创建/覆写文件 | > |
| ApplyPatchTool | 对已有文件打补丁 | sed, patch |

### 执行工具

| 工具 | 功能 |
|-----|------|
| RunShellTool | 执行 shell 命令（带危险命令过滤） |
| PythonExecutionTool | Python 代码沙箱执行（AST 校验 + 导入限制） |

### 网络工具

| 工具 | 功能 |
|-----|------|
| HTTPRequestTool | HTTP 请求（带 SSRF 防护） |
| WebFetchTool | 获取网页内容 |
| WebSearchTool | DuckDuckGo 搜索 |

### 便捷聚合

| 函数 | 返回 |
|-----|------|
| get_core_tools(workspace) | 7 个核心 Coding Agent 工具 |
| get_filesystem_tools(workspace) | 5 个文件系统工具 |
| get_execution_tools(workspace) | 2 个执行工具 |
| get_network_tools() | 3 个网络工具 |

### Interface 层

| 组件 | 功能 |
|-----|------|
| ConsoleRenderer | 将 Runtime 事件渲染为可读输出 |
| `_summary` 参数 | 框架注入，LLM 生成工具描述 |
| REPL 输出策略 | 默认只展示 `summary`，不显示工具名，不做阶段折叠 |

### Model Providers

采用 Provider-centric 架构：

```
Provider (服务商)
├── id: "deepseek"
├── base_url: "https://api.deepseek.com"
├── api: "openai-completions" | "anthropic-messages"
├── api_key: "${DEEPSEEK_API_KEY}"
└── models: (ModelSpec, ...)
```

| Provider ID | API | 模型 |
|------------|-----|------|
| openai | openai-completions | gpt-4o, gpt-4, gpt-3.5-turbo |
| anthropic | anthropic-messages | claude-3.5-sonnet, claude-3-opus |
| dashscope | openai-completions | qwen-max, qwen-plus, qwen-turbo |
| deepseek | openai-completions | deepseek-chat, deepseek-coder |
| deepseek-anthropic | anthropic-messages | deepseek-v4-flash, deepseek-v4-pro |
| moonshot | openai-completions | moonshot-v1-8k, moonshot-v1-128k |
| jdcloud | openai-completions | glm-5, glm-4 |
| openrouter | openai-completions | anthropic/claude-3.5-sonnet, ... |
| ollama | openai-completions | llama3, mistral, qwen2 |

## 下一步行动

参见 TODO.md
