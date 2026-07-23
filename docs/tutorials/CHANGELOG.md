# 更新日志

记录 Quenda 框架的重要变更，本文档随框架更新而同步更新。

---

## v0.3.0 (2026-06-30)

### 🚀 重要更新

Quenda 框架 v0.3.0 版本，包含多项重要新特性和改进。

### Skills Framework ✨

可组合的能力包系统，扩展 Agent 行为：

- **三层优先级**：user_workspace > agent_package > user
- **渐进披露**：Discovery → Activation → Usage
- **资源系统**：references、templates、assets、scripts
- **REPL 命令**：`/skill list`、`/skill activate`、`/skill deactivate`、`/skill resources`

### Custom Tool Extensions

Agent 通过 `extensions/tools/*.py` 定义自定义工具：

- 支持 `tools` 列表或 `register(builder)` 函数导出
- 在 `config.yaml` 中通过 `tools.include` 请求
- 不能覆盖内置工具名称

### Context Compression

自动上下文压缩，支持长对话：

- 可配置压缩策略（threshold_ratio、keep_last_n_messages）
- 手动触发 `/compress` 命令
- 归档原始消息，保留摘要

### Interaction Requests

结构化交互协议：

- LLM 可通过 `request_interaction` 工具发起交互
- 支持四种类型：choice、confirm、input、menu
- Agent-local 扩展：`extensions/interactions/*.py`

### Policy 系统

运行时策略控制：

- `TerminationPolicy` - 控制何时停止执行
- `ToolSelectionPolicy` - 控制哪些工具允许执行
- `ToolResultProcessingPolicy` - 控制工具结果如何进入上下文
- `TraceSink` - 观察运行时事件

### Multimodal 支持

多模态消息架构：

- 图像输入支持
- 资源激活工具 `ActivateResourceTool`

### 架构改进

- **ADR-024**: Agent-Local Custom Tool Extensions
- **ADR-025**: Skill Lifetime and Prompt Residency
- **ADR-026**: Textual Context Reload and Capability Rebind
- **ADR-027**: Multimodal Input Foundation
- **ADR-028**: Capability-Based Model Routing
- **ADR-029**: Unify Code and Command Execution

---

## v0.2.0 (2026-06-15)

### 新特性

### Agent Package Bundled Skills

Skills 可以打包在 Agent 包中：

- 安装时自动可用
- 版本一致性
- 卸载时自动清理

### Workspace 身份模型

- `.quenda/workspace.yaml` workspace binding
- `~/.quenda/users/<user>/agents/<agent>/workspaces/<id>/` 存储布局
- 用户隔离和多租户支持

### 命令扩展增强

- `extensions/commands/*.py` 加载契约
- 用户命令可覆盖内置命令
- 命令补全支持

### Provider 合约稳定化

- 26 个内置 provider
- 300+ 模型支持
- Registry/model lookup 兼容性测试

---

## v0.1.0 (2026-06-24)

### 🎉 初始版本

Quenda 框架的第一个公开版本。

### Agent SDK

- **Agent**: 支持 `Agent` 类的创建、配置和运行
- **Session**: 支持持久化会话，多轮对话
- **Tool**: `@tool` 装饰器自动生成 JSON Schema
- **Kernel**: 纯同步的 model-tool 执行循环
- **Events**: 完整的运行时事件体系（8 种事件类型）

### 内置工具（8 个核心工具）

- `ListFilesTool` — 文件列表
- `SearchTextTool` — 文本搜索
- `ReadFileTool` — 文件读取
- `WriteFileTool` — 文件写入
- `ApplyPatchTool` — 安全 Patch
- `PythonExecutionTool` — 沙箱执行 Python
- `RunShellTool` — Shell 命令
- `RequestInteractionTool` — 用户交互

### 模型提供商（26 个）

- OpenAI, Anthropic, DeepSeek, Google, Mistral, Cohere
- DashScope(通义千问), Zhipu(智谱), Moonshot(月之暗面)
- DeepSeek(深度求索), Stepfun(阶跃星辰), MiniMax
- X.AI(Grok), Groq, Together, Fireworks, Perplexity
- NVIDIA, Cerebras, Ollama, OpenRouter
- VolcEngine(火山引擎), Xiaomi(小米), Tencent(腾讯)
- JDCloud(京东云), SiliconFlow(硅基流动)

### Quenda Code CLI

- `quenda code` — 交互式 REPL 模式
- `quenda code "message"` — 一次性执行模式
- `quenda run --agent` — 运行自定义 Agent
- 三种交互模式：chat / code / architect

### 命令系统

- `/help`, `/clear`, `/reset`, `/exit`
- `/mode`, `/model`, `/session`
- `/context`, `/status`, `/compress`

### 架构特性

- **ADR-004**: 工作空间绑定与存储路径
- **ADR-007**: Agent 包加载（AGENT.md + config.yaml）
- **ADR-008**: 斜杠命令系统
- **ADR-010**: 命令扩展机制
- **ADR-012**: 交互请求与选择控件
- **ADR-013**: 内置 Agent 发现
- **ADR-014**: 界面主题扩展
- **ADR-015**: 上下文压缩

---

## 版本命名规则

Quenda 使用语义化版本：`MAJOR.MINOR.PATCH`

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向下兼容的功能新增
- **PATCH**: 向下兼容的 Bug 修复

---

## 查看版本

```bash
python -c "import quenda; print(quenda.__version__)"
```
