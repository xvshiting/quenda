# 更新日志

记录 Quenda 框架的重要变更，本文档随框架更新而同步更新。

---

## v0.1.0 (2025-06-24)

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
