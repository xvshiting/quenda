# Kora TODO

> 当前执行优先级来自 [docs/PM-REPORT-2026-06-23.md](docs/PM-REPORT-2026-06-23.md)。
> 新架构和技术方案评估请使用 [docs/TECH-RADAR.md](docs/TECH-RADAR.md)。

## 当前优先事项

### P0: 稳定基础设施

- [x] 统一本地开发环境到 Python 3.12+，避免默认 Python 3.9 导致测试收集失败
- [x] 在正确解释器下跑通测试套件，并记录真实失败项
- [x] 建立文档同步检查：README、Getting Started、API Reference、CURRENT 与 `pyproject.toml` 保持一致
- [x] 修复 `ToolResult.call_id` 归属问题：Kernel 在执行后补齐 `call_id`，保持 `Tool.execute(**kwargs)` 简单

### P1: 锁定 Provider 合约

- [x] 明确 Provider-centric 架构的稳定公共 API 边界
- [ ] 补充 registry/model lookup 的兼容性测试
- [ ] 验证所有内置 Provider 可发现、可创建 Model，并有清晰错误语义
- [ ] 为旧 provider 类迁移到 `get_provider_registry().get_model(...)` 写迁移说明

### P2: Host 最小骨架

- [x] 定义 Session/Run 持久化边界
- [x] 选择最小可插拔存储接口（`Storage` Protocol + `FileStorage`）
- [x] 基于 [docs/decisions/004-workspace-identity-and-user-agent-state.md](docs/decisions/004-workspace-identity-and-user-agent-state.md) 实现 workspace binding 与 user-agent-workspace state
- [x] 修复 Session 持久化：正确包含 assistant message
- [x] 修复 JSON 存储：UTF-8 编码（`ensure_ascii=False`）
- [x] **上下文重建**：实现 `ContextRebuilder`，在 `/model` 切换后重建 system prompt
  - `src/kora/host/context.py` — `ContextRebuilder` 类
  - `Agent.set_system_prompt()` / `Session.set_system_prompt()` — 运行时更新 system prompt
  - `ModelCommand` 返回 `rebuild_context=True` + `state_patch`
  - CLI `run_repl()` 接入上下文重建流程
  - 支持 `mode` 模式切换（chat/code/architect）
  - 自动从 `instructions/mode-<name>.md` 加载模式指令
- [x] **更多命令**：实现 `/mode`, `/context`, `/reset`
  - `/mode [chat|code|architect]` — 切换交互模式，重建上下文
  - `/context [show|tools|session]` — 查看当前上下文/工具/会话信息
  - `/reset` — 清空消息并恢复原始系统提示词
- [x] **上下文压缩**：实现 ADR-015 上下文压缩与分层存储
  - `src/kora/runtime/compression.py` — `CompressionStats`, `CompressionDecision`, `CompressionResult`
  - `src/kora/host/compression_policy.py` — `CompressionPolicy`, `DefaultCompressionPolicy`
  - `src/kora/runtime/compressor.py` — `Compressor`, `SummarizerCompressor`
  - `src/kora/runtime/token_estimator.py` — Token 估算
  - `src/kora/runtime/events.py` — `CompressionStarted`, `CompressionCompleted`
  - `src/kora/host/storage.py` — 归档存储支持
  - `/compress` 命令 — 手动触发压缩
  - `/status` 命令 — 查看 token 使用和压缩状态
  - `config.yaml` 支持 `compression` 配置
- [ ] 明确身份认证、权限控制与 Host 层的职责边界
- [ ] 设计本地 HostStore 与 Server HostStore 的同构映射
- [ ] 为 Host-owned 行为补充集成测试规划
- [ ] 暂缓完整 tool permission 与 Host metadata 保护；MVP 先完成 Code Agent / Host / Interface 功能链路

### P2.5: Host reload semantics convergence ✅

- [x] 按 [docs/decisions/026-textual-context-reload-and-capability-rebind.md](docs/decisions/026-textual-context-reload-and-capability-rebind.md) 拆分 Host 的 `text refresh path` 与 `capability binding path`
  - `setup_host_binding()` - Path A: Capability binding (runs once at setup)
  - `refresh_run_context()` - Path B: Text refresh (runs before each run)
- [x] 让 `AGENT.md`、instruction overlays、skill catalog 与 `SKILL.md` 在每次新 run 前重读并重建上下文
  - `refresh_run_context()` re-reads AGENT.md and re-discovers skills
- [x] 调整 Skills durable state：以 `active_skill_names` 为主，避免把已加载 `SkillPackage` 作为长期 session truth
  - `SkillActivator.active_skill_names` is the durable state
  - `active_skills` property resolves on-demand
- [x] 为 capability-affecting config 增加一个显式 `rebind/reload` 入口，保持 model/tool/sandbox/policy 绑定稳定
  - Added `/rebind` command to show binding info and explain restart requirement
- [x] 为上述 reload / rebind 语义补最小集成测试后停止扩展文档，转入实现验证
  - `tests/host/test_reload_semantics.py` covers all key scenarios

### P3: Instruction Layer（ADR-007）✅

- [x] 重构 Agent package 加载：`AGENT.md` + `config.yaml`
- [x] 实现 scope 层级解析（workspace, user, user-agent, workspace-agent）
- [x] 实现 `INSTRUCTIONS.md` per-run 加载
- [x] 实现模板变量替换（白名单变量）

### P4: Interaction Request 机制（ADR-012）✅

- [x] `RequestInteractionTool` — 框架保留 tool，允许 LLM 请求用户交互
- [x] Host 层检测 `request_interaction` tool call
- [x] Interface 层展示 choice/confirm/input/menu
- [x] 用户选择后注入 user message，启动下一轮
- [x] 集成测试覆盖完整流程
- [x] 实现 instruction append-only 组合
- [ ] 暂缓：User scope instructions、Instruction disable 机制

### Trial: Kora Code Agent MVP ✅

- [x] 创建 `agents/kora-code/AGENT.md`（定义系统提示和行为准则）
- [x] 创建 `src/kora/cli.py`（通用 CLI：`kora run` / `kora code`）
- [x] `pyproject.toml` 已有 `kora` 命令入口点配置
- [x] 验收测试 1：基础问答 ✅（Agent 能理解项目结构并给出合理回答）
- [x] 验收测试 2：代码探索 ✅（Agent 能找到入口点，解释代码）
- [x] 验收测试 3：简单修改 ✅（Agent 用 `apply_patch` 正确添加 docstring）
- [x] 验收测试 4：命令执行 ✅（Agent 运行测试，解析输出，报告失败原因）
- [x] 修复测试不一致问题（`get_core_tools()` 返回 7 个工具）
- [x] 实现 REPL 交互模式
- [x] 实现 Session 持久化

### Trial: Interface 事件渲染 ✅

- [x] ADR-006: 定义事件渲染策略
- [x] 增强 `ToolExecuted` 事件（添加 `arguments`, `duration_ms`, `result_lines` 等）
- [x] 创建 `ConsoleRenderer` 渲染器
- [x] 框架注入 `_summary` 参数，LLM 生成工具描述
- [x] Kernel 过滤保留参数后传递给工具
- [x] 修复 Kernel 重复执行工具的 bug

#### 发现的问题（待回填到基础设施）

1. **默认模型配置**：已修复，改用 `deepseek` + `deepseek-v4-flash`
2. **FileStorageConfig.base_dir 默认值**：当前是 `.kora`（相对路径），ADR-004 设计是 `~/.kora`
3. **User 缺少 kora_dir 属性**：CLI 需手动构建 `~/.kora/users/<user_id>` 存储路径
4. **AGENT.md frontmatter 未解析 default_provider/default_model**：CLI 应读取这些值作为默认配置
5. **权限系统暂缓**：完整 tool permission、allow/ask/deny、Host-owned metadata 写保护先不做，保留到 Host 安全阶段

### Trial: Skills 能力包机制 ✅

- [x] 基于 [docs/decisions/002-skills-capability-packages.md](docs/decisions/002-skills-capability-packages.md) 完成 `SKILL.md` schema 设计
- [x] 设计 Host 层 Skill 发现、信任、加载和资源暴露流程
- [x] 明确 Skill 与 Tool、Agent、Runtime、Kernel 的边界
- [x] 实现三层优先级：`user_workspace` > `agent_package` > `user`
- [x] 实现用户隔离：`~/.kora/users/<user>/workspaces/<ws_id>/skills/`
- [x] 实现 Agent 包打包 Skills：`<agent-package>/skills/`
- [x] 实现 Framework Contract：所有 Agent 自动获得 Skills 路径约定
- [x] 实现 `/skill` REPL 命令：`list`, `activate`, `deactivate`, `resources`
- [x] 文档：[docs/skills.md](docs/skills.md)
- [x] 暂缓 marketplace、远程安装、自动脚本执行和复杂依赖解析

## Phase 0: 项目基础 ✅

- [x] 设置 Python 项目结构（pyproject.toml, src/kora/）
- [x] 配置开发环境（pytest, mypy, ruff）
- [x] 创建最小可运行的包结构

## Phase 1: Kernel 层 ✅

- [x] 定义 Model Provider 接口（Protocol）
- [x] 定义 Tool 接口
- [x] 实现 model-tool 循环核心逻辑
- [x] 添加 Kernel 单元测试

## Phase 2: Runtime 层 ✅

- [x] 定义 Agent 协议和 AGENT.md 加载器
- [x] 实现 Session 管理
- [x] 实现 Run 执行流程
- [x] 添加会话持久化接口

## Phase 3: 工具与可观测性 ✅

- [x] 实现文件系统工具集
- [x] 定义事件类型（Event protocol）
- [x] 实现 @tool 装饰器
- [x] 添加工具测试

## Phase 4: 高级工具 ✅

- [x] 实现文件系统增强工具（search, move, copy, rename, mkdir）
- [x] 实现 Shell 执行工具（带安全控制）
- [x] 实现网络工具（HTTP, WebFetch, WebSearch，带 SSRF 防护）
- [x] 实现 Python 代码执行工具（沙箱环境）
- [x] 添加高级工具测试

## Phase 5: 文档 ✅

- [x] 更新 README.md
- [x] 创建入门指南（docs/getting-started.md）
- [x] 创建工具文档（docs/tools.md）
- [x] 创建 API 参考（docs/api.md）
- [x] 更新开发文档

---

## Phase 6: Model Providers ✅

- [x] 实现 OpenAI Provider
- [x] 实现 Anthropic Claude Provider
- [x] 实现 GLM Provider（智谱 AI）
- [x] 实现本地模型支持（Ollama）
- [x] 添加 Provider 测试
- [x] 实现 Provider-centric 架构重构
- [x] 实现 Anthropic Messages API
- [x] 添加错误处理与重试机制
- [x] 添加流式支持（StreamChunk）
- [x] 添加 DeepSeek、Moonshot 等内置 Provider

## Phase 7: Host 层 ✅

- [x] 实现 workspace binding 解析与校验
- [x] 实现 user-agent-workspace state 的存储布局
- [x] 实现持久化接口（Session/Run 存储）
- [x] 实现身份认证（User, IdentityResolver, DefaultUserResolver）
- [x] 实现权限控制（PermissionPolicy, HostPermissionPolicy）
- [x] 添加 Host 层测试（loader, storage, identity, workspace, permission）

## Phase 8: 高级功能 📋

- [x] Skills 能力包机制（ADR-002，已完成）
- [x] Agent Package Capability Declaration（MVP，已完成）
- [ ] 多 Agent 协作
- [ ] 工具组合和链式调用
- [ ] 记忆和上下文管理
- [ ] Runtime/Host 面向用户的流式输出支持

## Phase 9: CLI 和部署 📋

- [ ] 实现命令行接口
- [ ] 实现 Server 模式
- [ ] Docker 支持
- [ ] 部署文档

---

## 开放问题

### 1. 面向用户的流式输出

**问题**：Provider 层已有 `StreamChunk` 等流式基础类型后，Runtime/Host 如何向用户暴露流式输出？

**选项**：
- A) SSE (Server-Sent Events)
- B) WebSocket
- C) 原生异步生成器

**倾向**：选项 C（原生异步生成器），最 Pythonic

### 2. 多 Agent 协作

**问题**：如何实现 Agent 间通信？

**选项**：
- A) 共享消息队列
- B) 直接调用
- C) 工具包装

**倾向**：待研究

### 3. 持久化策略

**问题**：Session/Run 如何持久化？

**选项**：
- A) 文件系统（JSON/SQLite）
- B) 数据库（PostgreSQL/MongoDB）
- C) 可插拔存储接口

**倾向**：选项 C（可插拔存储接口）
