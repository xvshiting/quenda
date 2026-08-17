# Hermes Agent / OpenClaw / Codex 自进化与 Agent 框架机制调研

> 调研时间：2026-08-13。范围限于官方仓库、官方文档和官方 issue；未把二手文章当作实现证据。Hermes 官方仓库为 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)，OpenClaw 官方仓库为 [openclaw/openclaw](https://github.com/openclaw/openclaw)，Codex 仅引用 OpenAI 官方开发者文档。

## 结论摘要

1. Hermes 的“自进化”不是任意改写人格文件，而是三条受控路径：周期性提示写入 `MEMORY.md` / `USER.md`、复杂工具任务后创建或改善 Skill、空闲期 Curator 后台复审。`SOUL.md` 属于用户控制的身份/人格层，官方承诺已有文件不会被覆盖。
2. Hermes 压缩阈值确实按模型上下文容量比例配置（默认 `compression.threshold: 0.50`）；OpenClaw 的主要机制则是 reserve/keep-recent token 和距离阈值的 soft threshold，并非同一种百分比策略。
3. Hermes 的稳定 prompt 前缀、会话启动时 frozen memory snapshot、渐进式项目指令发现都体现了 cache-aware 设计。把频繁变化内容留在后部或 tool result，而不是重写前缀，是合理的框架约束。
4. “框架内置、官方可插拔、market、第三方”四类工具没有在 Hermes 官方材料中被核实为严格分类。可核实的是 built-in toolsets、插件/provider、MCP 和 Skills Hub。
5. OpenClaw 的 lifecycle/plugin hooks 比 Hermes 当前公开实现更完整，尤其适合作为 Quenda 的统一扩展层参考；Hermes 官方 issue 反而明确指出现有 hook 分散，并提议统一 middleware。
6. Hermes `/goal` 和 verify-on-stop 已实现“回答后评估—不满足则继续”的持续执行模式；OpenClaw `sessions_spawn` 则提供成熟的隔离子代理、嵌套和并发控制。

## 1. 自反思与自进化的触发时机

Hermes 官方首页把学习闭环描述为：周期性 memory nudge、复杂任务后自主创建 Skill、Skill 在使用中被改进、跨会话搜索，以及可选的 Honcho 用户建模（[官方文档源码](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/index.mdx#L195-L204)，[README](https://github.com/NousResearch/hermes-agent#L246-L257)）。

更具体的触发有两层：

- 对话内 nudge：官方 issue 记录当前实现使用 `_turns_since_memory` 和 `_iters_since_skill` 计数；默认每 10 个用户 turn 提示记忆维护、每 10 个 tool iteration 提示 Skill 创建，满足条件后进入 background review，`/new` 重置计数（[Hermes issue #18369](https://github.com/NousResearch/hermes-agent/issues/18369)）。新版代码路径和两类 gate 共享 review fork 的实现讨论见 [Hermes issue #42388](https://github.com/NousResearch/hermes-agent/issues/42388)。这是实现证据，不应视为稳定公共 API。
- Curator：官方文档说明它按“距上次运行时间 + 空闲时间”触发，默认约每 168 小时且空闲至少 2 小时；CLI 启动和 gateway cron tick 会检查，并在后台 fork 中运行，不修改活动会话。它支持关闭、手动运行、dry-run、备份及回滚（[Curator 官方文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/curator)）。文档还说明 self-improvement background fork 大约每 10 个 agent turns 复审/改善 Skill，只有 `background_review` 来源才标记为 agent-created。

因此，Quenda 不宜设计成“每轮都反思并改文件”，而应区分低成本 nudge、任务后 review、空闲期 curator，并给每条路径独立 gate、预算、权限和回滚能力。

## 2. Memory、User、Soul、Identity 与 Skill

Hermes 的长期记忆位于 `~/.hermes/memories/`；`MEMORY.md` 与 `USER.md` 在 session start 以 frozen snapshot 注入，agent 通过 memory tool 的 add/replace/remove 更新，历史会话还存入 SQLite `state.db` 并用 FTS5 提供 `session_search`。官方文档给出了默认字符预算（`MEMORY.md` 2200、`USER.md` 1375）和外部 memory provider 与 built-in 并行、而非替换的语义（[Memory 官方文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)）。

`SOUL.md` 的定位不同：它是用户/实例控制的身份、价值观和表达方式，已有文件不会被安装或升级覆盖（[Personality 官方文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/personality)）。本次未找到 Hermes 自动改写 `SOUL.md` 或 Identity 的官方实现证据。

这意味着 Quenda 应采用不同写权限：

- `Memory/User`：允许 agent 在 schema、大小、来源和审计约束下维护。
- `Skill`：允许在任务后或后台 review 中创建/更新，但要有 provenance、验证、版本和回滚。
- `Identity/Soul`：默认只读；模型只能提出 patch，由用户审批或由明确授权的策略应用。

## 3. 上下文压缩与 prompt cache

Hermes 的 `compression.threshold` 是主模型 `context_length` 的比例，默认 `0.50`，同时可配 `target_ratio`、`protect_last_n` 等；核心实现路径由官方开发文档指向 `agent/context_compressor.py`。Gateway 另有 85% 的 hygiene safety net。其 context engine 还可选 `compressor` 或 plugin provider（[Context Compression and Caching](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching/)，[Configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration)）。

Hermes 项目上下文在启动时加载稳定系统内容，子目录 `AGENTS.md` 采用 progressive discovery，内容随 tool result 追加；官方明确把 prompt cache preservation 列为收益之一（[Context Files](https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files)）。Prompt stack 中 `SOUL` 位于前部，之后是 tool guidance、memory/user、skills 和 project context（[Personality](https://hermes-agent.nousresearch.com/docs/user-guide/features/personality)）。

OpenClaw 的 auto-compaction 在接近 context limit 或 overflow 时运行；pre-compaction memory flush 使用距离正式阈值的 `softThresholdTokens`（默认 4000），一次压缩周期只 flush 一次，并以 `NO_REPLY` 静默完成。官方同时指出核心配置偏向 `reserveTokens` / `keepRecentTokens`，源码路径包括 `src/auto-reply/reply/memory-flush.ts` 与 `src/auto-reply/reply/agent-runner-memory.ts`（[Session Management and Compaction](https://github.com/openclaw/openclaw/blob/main/docs/reference/session-management-compaction.md#L354-L413)）。

建议 Quenda 同时支持 ratio 与 absolute reserve，但将阈值计算集中在统一 `ContextBudget` 接口；稳定 system/tool definitions 形成不可变前缀，动态 memory、context 和 tool results 只追加在后部。任何 tool-result 清洗应在持久化或下一次模型调用前完成，而不是重建前缀。

## 4. 工具暴露与分类

Hermes 官方把工具按 logical toolsets 组织，并可按平台/配置启停；可核实的常见集合包括 terminal、file、web、skills、memory、delegation 等（[Tools 官方文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools)）。此外还有插件/context/memory providers、MCP 与 Skills Hub。

本次未发现官方源码或文档定义“框架内置 / 官方可插拔 / market / 第三方”严格四分类。Quenda 可以采用这四个 provenance 标签，但应把它定义成自己的稳定概念，并把“来源”与“默认可见性、启用状态、授权边界”分开：built-in 不等于永远获准执行，Skill allowlist 也不等于 shell 权限边界。OpenClaw 对 bundled、managed、agent、workspace Skills 的可见性与 allowlist 语义可作参考（[Skills Config](https://github.com/openclaw/openclaw/blob/main/docs/tools/skills-config.md)）。

## 5. 框架自解释与聊天式自配置

Hermes 文档站每次部署生成 `/llms.txt`（索引）与 `/llms-full.txt`（全量），专供 LLM 和 coding agent 查询（[文档首页源码](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/index.mdx#L263-L270)）。项目还支持 `.hermes.md` / `HERMES.md`、`AGENTS.md`、`CLAUDE.md`、`SOUL.md` 的优先级与发现机制（[Context Files](https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files)）。

OpenClaw 还提供受限 setup agent：模型辅助配置时只暴露单一 `openclaw` authority tool，提案脱敏、AI history 隐藏 secret、其余工具禁用，并保留确定性的远程 rescue 路径（[OpenClaw CLI 官方文档](https://docs.openclaw.ai/cli/openclaw)）。

对 Quenda，框架知识不应只靠模型训练记忆。应从同一份 typed schema / registry 生成 CLI help、配置参考、LLM 索引、示例与校验器；聊天式配置通过“读取当前配置—生成结构化 proposal—校验 diff—用户审批—原子应用—回滚”完成，并使用最小权限专用工具。

## 6. Hooks、生命周期与 tool-result 处理

OpenClaw 官方 agent-loop 文档列出 Gateway internal hooks 与 plugin hooks，包括 `before_model_resolve`、`before_prompt_build`、`before_agent_reply`、`agent_end`、`before/after_compaction`、`before/after_tool_call`、`tool_result_persist` 以及 message/session/gateway hooks（[Agent Loop](https://github.com/openclaw/openclaw/blob/main/docs/concepts/agent-loop.md#L218-L260)）。插件文档还包含 subagent hooks，并明确 tool result 的 `details` 会在 provider replay/compaction 前剥离、持久化 details 有大小上限（[Plugin Hooks](https://github.com/openclaw/openclaw/blob/main/docs/plugins/hooks.md#L315-L329)，[tool result 处理](https://github.com/openclaw/openclaw/blob/main/docs/plugins/hooks.md#L535-L537)）。

Hermes 的统一 middleware 目前不能当成成熟事实。官方 issue 指出 approval、nudge、sanitize、prompt layering 等逻辑分散，缺少统一 pre/post model hooks，并提议 `AgentMiddleware(before_turn, after_turn, pre_model, post_model, wrap_tool)`（[Hermes issue #626](https://github.com/NousResearch/hermes-agent/issues/626)）。配置文档中可以核实的扩展点之一是 `pre_verify` hook（[Configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration)）。

Quenda 应定义单一 typed lifecycle，并明确 hook 的顺序、是否可变更数据、失败语义、超时、幂等性、可观测性和 cache 影响。最小覆盖面应包括 session、turn、prompt/model、tool call/result/persist、compaction、memory、subagent 和 run completion。

## 7. 多代理与持续评估循环

Hermes 支持隔离 subagent 并行。其 Mixture-of-Agents 是 virtual model provider，不等于任务型 subagent：reference models 不获得工具或 Hermes system prompt，aggregator 才执行正常 agent loop 与工具调用（[Mixture of Agents](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/mixture-of-agents.md)）。

Hermes `/goal` 会在每个 assistant response 后调用 judge；未满足时在同一 session 中 continuation，直到达成、预算耗尽或暂停，默认 `max_turns: 20`。verify-on-stop 会在代码改变但缺少新验证证据时注入 synthetic follow-up，默认最多 3 次（[Configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration)）。这就是用户所述持续评估模式的直接参考。

OpenClaw 的 `sessions_spawn` 提供隔离上下文、可选 fork、非阻塞 completion push、1–5 层嵌套、并发和子节点上限、按深度收紧工具以及 cascade stop（[Subagents](https://docs.openclaw.ai/subagents)，[Subagent Tools](https://docs.openclaw.ai/tools/subagents)）。

Quenda 可把一次执行抽象为持久化 `Run`，其终止条件由 policy 决定，而不是“单次模型返回即结束”；`GoalJudge`、验证证据、预算、暂停/恢复、子任务 DAG 都应成为框架协议，而非某个命令里的特例。

## 8. 沙箱后端

Hermes 统一通过 `terminal.backend` 支持 local、docker、ssh、modal、daytona、vercel_sandbox、singularity 七类后端（[Configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration)）。Quenda 应将执行环境设计成 capability-based backend：统一 exec/file-transfer/cancel/limits 接口，Agent 配置只引用 backend profile；凭据和连接参数由宿主安全配置管理，不能直接进入 prompt。

## 9. 对 Quenda 的建议落地顺序

1. 先定义稳定的生命周期、`ContextBudget`、tool provenance/capability 与 backend 协议；它们是后续能力的公共地基。
2. 实现 cache-aware prompt assembler：不可变前缀、frozen session snapshot、渐进式 context、tool-result processor、ratio/absolute 双阈值压缩。
3. 实现受控 evolution service：独立触发策略、后台 fork、typed patch、来源记录、验证、备份回滚；默认只写 Memory/User/Skill，Identity/Soul 需审批。
4. 从配置 schema 和 extension registry 自动生成框架文档、LLM 索引、示例和契约测试，解决 Agent 不了解自身框架的问题。
5. 加入持久化 Run、goal judge、verify-on-stop 与 subagent scheduler；随后再扩展 BM25/向量检索、SSH/Docker/cloud sandbox。

## 10. 关键纠偏与证据边界

- 有证据：Hermes 自动维护 Memory/User、创建/改善 Skill；无证据：自动改写 Soul/Identity。
- 有证据：Hermes 压缩使用上下文容量比例；OpenClaw 主要公开机制不是同一比例模型。
- 有证据：Hermes 有 toolsets、插件/provider、MCP、Skills Hub；无证据：官方严格四类工具 taxonomy。
- 有证据：OpenClaw 有较完整 plugin lifecycle；Hermes 的统一 middleware 仍主要是官方 issue 中的改进提案。
- `/goal`、verify-on-stop、Curator 和 subagent 都应分别建模；不能把它们笼统合并成一个“自进化”开关。

## 本地源码快照

官方源码计划保存在 `research/vendor/hermes-agent/` 与 `research/vendor/openclaw/`，两者均已加入根 `.gitignore`，与现有 `claude-code/` 本地参考源码约定一致。当前受限网络下的 clone 尝试没有留下可用工作树，两处本地目录均不存在；本文引用均指向上述官方公开仓库/文档，不依赖本地快照。后续网络可用时可直接在这两个已忽略目录重新 clone。

## 实现级补充

> 证据基线：2026-08-13 访问官方 `main`。GitHub blob 链接随 `main` 演进；未取得本地完整快照，因此以下把“官方文档对源码符号/路径的说明”“当前源码 blob”和“官方 issue 对特定版本的源码分析”分开表述。Issue 中的缺陷或提案不等于已发布契约。

### A. Hermes：触发器、状态与持久化

对话内学习不是一个统一反思事件。官方 issue 对当时实现的调用链记录为：`AIAgent` 维护 `_turns_since_memory` 与 `_iters_since_skill`，分别由 user turn 和 tool iteration 推进；满足 `memory.nudge_interval` / `skills.creation_nudge_interval` 后，经 `_spawn_background_review()` 进入独立 review fork，`/new` 清零计数（[issue #18369](https://github.com/NousResearch/hermes-agent/issues/18369)）。后续重构把相关职责移动到 `agent/turn_context.py` 和 `agent/conversation_loop.py`，两类 gate 仍共享 review fork，并暴露写权限耦合问题（[issue #42388](https://github.com/NousResearch/hermes-agent/issues/42388)）。因此 Quenda 应把 `MemoryNudgePolicy`、`SkillReviewPolicy` 和 `ReviewExecutor` 拆开，不共享一个含混布尔 gate。

Curator 是更低频的宿主级后台任务：检查 `interval_hours`（默认 168h）和 idle（默认 2h），入口来自 CLI 启动检查和 gateway cron tick；它 fork 后台上下文，不占用或改写活动会话，支持 disable/manual/dry-run、备份与 rollback（[Curator 文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/curator)）。官方材料没有给出足够稳定的跨进程锁类型、锁文件 schema 或所有异常分支，不能声称其锁/并发协议已经核实。Quenda 应明确采用数据库 lease（owner、expires_at、heartbeat）或原子 compare-and-set，而不是依赖进程内计数；patch 应先写 revision，再验证，最后原子切换 active revision。

可直接采用的状态草案：

```text
EvolutionTrigger { kind, subject_id, observed_revision, reason, counters, created_at }
EvolutionRun { id, trigger_id, status, lease_owner, lease_expires_at, attempt, budget }
ArtifactRevision { artifact_kind, artifact_id, parent_revision, patch, provenance, validation, status }
```

### B. Hermes `/goal` 与 verify-on-stop

官方 goals 文档给出了可执行协议：judge 输入 standing goal 与最近 final response（约最后 4KB），早期兼容格式是 `{"done": bool, "reason": string}`，当前还支持 `verdict: done|continue|wait` 及 `wait_on_session` / `wait_on_pid` / `wait_for_seconds`。状态包括 objective、subgoals、active/paused/done、turn budget、barrier 和 gates；辅助任务名为 `goal_judge`。judge 异常或 JSON 无效时按 `continue` 处理，真正的安全后盾是 turn budget。默认 `goals.max_turns=20`，耗尽后自动 pause；`/goal resume` 将 continuation counter 重置为零。用户真实消息通过 `_pending_input` 优先于 queued continuation；gateway 运行中允许 status/pause/clear/wait/unwait/gate，但拒绝直接替换 standing goal，避免旧 continuation 与新目标竞态。pause/resume/clear 会清 barrier，过期 PID/deadline 会在检查时释放；gate 默认 3 次 retry、5 分钟 timeout，耗尽后 auto-pause。状态持久化在 `SessionDB.state_meta` 的 `goal:<session_id>`，所以 `/resume` 和 compression 后仍可恢复。continuation 只是追加普通 user-role message，不修改 system prompt 或 toolsets，因而保持 prompt cache 前缀（[Goals 文档源码](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/goals.md)）。

verify-on-stop 是另一条有界机制：当代码发生变化而缺少新的验证证据时注入 synthetic follow-up，最多重试若干次（默认 3），可由 `pre_verify` hook 接入自定义验证（[Configuration](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/configuration.md)）。公开文档不足以核实 synthetic message 的稳定内部 schema，Quenda 不应复制字符串协议，应定义 typed event。

建议 API：

```text
GoalState { session_id, objective, subgoals[], status, used_turns, max_turns, barrier?, gates[], reason, revision }
GoalVerdict { verdict: done|continue|wait, reason, wait_on_session?, wait_on_pid?, wait_for_seconds?, evidence_refs[] }
ContinuationDecision { action: stop|continue|pause, prompt?, idempotency_key, remaining_budget }
VerificationEvidence { kind, command, artifact_revision, observed_at, exit_code?, digest? }
```

不要照搬 Hermes 的 judge fail-open 命名：从可用性角度它是“继续”，从资源/外部副作用角度并不安全。Quenda 应允许 per-goal 配置 `on_judge_error = pause|continue|stop`，涉及写外部系统时默认 pause。

### C. Hermes compression：预算、边界与输出

官方实现说明和当前 [`agent/context_compressor.py`](https://github.com/NousResearch/hermes-agent/blob/main/agent/context_compressor.py) 给出以下预算：

```text
threshold_tokens   = context_length * threshold
tail_token_budget  = threshold_tokens * target_ratio
max_summary_tokens = min(context_length * 0.05, 12_000)
```

默认 `threshold=.50`、`target_ratio=.20`、`protect_last_n=20`、硬编码 `protect_first_n=3`。但当前源码还对小于 512K 的 context window 将有效 threshold 至少提高到 75%（只升不降），并把 recent-message 硬 floor 限制为 8；在 protected-tail 压力下至少保留最后 3 条消息。这些常量和动机可见当前源码顶部的 `_SMALL_CTX_WINDOW_LIMIT`、`_SMALL_CTX_THRESHOLD_PERCENT`、`_MAX_TAIL_MESSAGE_FLOOR`、`_PRESSURE_KEEP_RECENT_MESSAGES`（[源码](https://github.com/NousResearch/hermes-agent/blob/main/agent/context_compressor.py)）。

`ContextCompressor.compress()` 的四阶段流程是：先把非保护区中大于 200 字符的旧 tool result 替换为固定占位符；从尾部按 token budget 回走，且至少保护近期消息；调用 `_align_boundary_backward()` 避免拆开 assistant tool-call / tool-result 组；总结中间区并把滚动 summary 与 head/tail 合并（[开发文档](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/context-compression-and-caching.md)）。压缩 summary 目前带 `[CONTEXT COMPACTION — REFERENCE ONLY]` 并作为普通 assistant message 插回 messages（[官方 issue #38392](https://github.com/NousResearch/hermes-agent/issues/38392)）。

实现风险同样重要：历史实现曾因 message-count gate 先于 token check，导致少量超大消息绕过 preflight（[issue #27405](https://github.com/NousResearch/hermes-agent/issues/27405)）；大 tool result 会吞掉 tail budget（[issue #13164](https://github.com/NousResearch/hermes-agent/issues/13164)）；位置式 `protect_first_n` 会造成旧消息“化石化”（[issue #11996](https://github.com/NousResearch/hermes-agent/issues/11996)）。

Quenda 应直接采用预算抽象，但不要照搬“普通 assistant summary + 纯位置保护”：

```text
ContextBudget { model_limit, fixed_prefix_tokens, reserve_tokens, trigger_ratio, target_tokens }
MessageProtection { semantic_role, group_id, minimum_recent_turns, evidence_pin }
CompactionResult { source_revision, summary_block, retained_message_ids, redacted_result_ids, token_estimate }
```

summary 应是 transcript 中的 typed compaction block，UI 可隐藏、provider adapter 可明确序列化；触发必须以完整请求估算（system + tools + messages）为准，message count 只能作为优化提示。稳定 prefix 不变，compaction 只替换动态 transcript 后缀。

压缩入口实际分两层：主 agent 使用真实 API usage 判断 `usedTokens >= contextLimit * threshold`；gateway session hygiene 以 85% 作保险阈值，优先使用最近 API usage，缺失时才用字符估算，且历史至少 4 条才运行。抽象接口已经存在于 `agent/context_engine.py::ContextEngine`（`should_compress`、`compress`、可选 tools、usage tracking），内置实现是 `ContextCompressor`，宿主调用还包括 `run_agent.py::_compress_context` 与 `gateway/run.py` 的 auto-compress。插件引擎从 `plugins/context_engine/<name>` 加载并通过 `register_context_engine()` 注册，但只有显式设置 `context.engine` 才启用（[开发文档](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/context-compression-and-caching.md)）。官方还警告 summary model 的 context window 必须至少等于主模型；否则历史实现可能丢弃 middle，这应在 Quenda 中改为事务性失败并完整保留原 messages。

### C.1 Hermes MemoryProvider 可抽取协议

外部 memory provider 的实现级接口位于 [`agent/memory_provider.py::MemoryProvider`](https://github.com/NousResearch/hermes-agent/blob/main/agent/memory_provider.py)，由 `agent/memory_manager.py::MemoryManager` 管理并在 `run_agent.py` 接线。核心生命周期包括 `initialize`、静态前缀 `system_prompt_block`、每 turn 非阻塞召回 `prefetch(query)`、响应后异步 `sync_turn(user, assistant)`、`get_tool_schemas`、`handle_tool_call` 与 `shutdown`；可选事件包括 `on_turn_start`、`on_session_end`、`on_session_switch`、`on_pre_compress(messages)->str`、`on_memory_write(...)`、`on_delegation` 和 `backup_paths`。写入 metadata 可携带 `write_origin`、`execution_context`、`session_id`、`parent_session_id`、`platform`、`tool_name`（[Memory Providers](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory-providers.md)）。当前只激活一个 external provider，但 built-in MEMORY/USER 始终并存；Quenda 可把这一接口推广为多 provider fan-out，同时要求每个 callback 声明 blocking、timeout 和 failure policy。

### D. Hermes 工具注册、动态 toolsets 与执行后端

官方 Toolsets Reference 明确：内置 toolset 加载后，配置的每个 MCP server 在运行时生成 `mcp-<server>` toolset；插件在初始化时通过 `ctx.register_tool()` 注册；custom toolsets 只是现有集合的组合；`all/*` 扩展到 built-in + dynamic + plugin。`hermes tools` 在更细的单 tool 层写入 enable/disable，禁用 tool 即使所属 toolset 被选中也会被过滤（[Toolsets Reference](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/reference/toolsets-reference.md)）。官方 issue 把最终计算函数指向 `_compute_tool_definitions()`，并记录配置交互曾导致 native tools 被整体过滤的缺陷（[issue #22573](https://github.com/NousResearch/hermes-agent/issues/22573)）。这说明“注册”与“本轮暴露”必须是两个阶段。

建议 Quenda 使用：`ToolDescriptor`（稳定 id/schema/source/capabilities）、`ToolRegistration`（plugin 生命周期）、`ToolExposurePolicy.resolve(turn) -> submitted IDs`、`ToolAuthorization.evaluate(call)` 四层；MCP discovery 只更新 registry，不应自动授权或自动把全部 schema 注入 prompt。Skill 则是可检索说明与程序，不应伪装成执行权限。

Hermes 的 `terminal.backend` 提供统一选择，但后端并非等价：local 直接继承宿主风险；Docker 使用一个可跨进程复用的长生命周期容器，terminal/file/execute_code 共享 `/workspace` 状态，默认 drop capabilities、禁止 privilege escalation、有 PID/CPU/memory/disk/timeout 控制，可关闭网络；SSH 使用 ControlMaster（5 分钟 idle keepalive）和默认 persistent `bash -l`，cwd/env 跨命令保留，涉及 stdin/sudo 时回退 one-shot。Docker 的 literal `docker_env` 与从宿主转发而不落 YAML 的 `docker_forward_env` 也被明确区分（[Configuration: Docker/SSH](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/configuration.md)）。

Quenda 不应只定义 `execute(command)`；可采用：

```text
ExecutionBackend { provision, exec, put, get, cancel, snapshot?, restore?, dispose }
BackendCapabilities { persistent_fs, persistent_process, stdin, sudo, network_policy, resource_limits, snapshots }
ExecutionLease { backend_id, workspace_id, owner_run_id, expires_at }
```

### E. OpenClaw hooks：组合与失败语义

官方 hooks 文档区分观察型和决策型 hook。`before_prompt_build` 可返回 prepend/append context、替换/追加 system context、或 `toolsAllow`；多个 `toolsAllow` 取交集，只能收窄本轮 host-resolved surface。需要原始对话的非 bundled plugin 必须显式设置 `allowConversationAccess`，prompt 注入还受 `allowPromptInjection` 控制（[Plugin Hooks](https://github.com/openclaw/openclaw/blob/main/docs/plugins/hooks.md)）。

决策合并并非“最后写入获胜”：`before_tool_call {block:true}`、`before_install {block:true}`、`message_sending {cancel:true}` 是 terminal decision，低优先级 handler 不再运行；对应 false 不会清除先前 block/cancel。`resolve_exec_env` 按优先级运行，后者同 key 覆盖前者，但宿主随后剔除 `PATH`、`LD_*`、`DYLD_*`、`NODE_OPTIONS`、proxy/TLS 等危险变量，并把过滤结果写入 approval/audit metadata（[Plugin Hooks](https://github.com/openclaw/openclaw/blob/main/docs/plugins/hooks.md)）。

`before_agent_finalize` 可返回 `action:"revise"` 与 `{instruction,idempotencyKey,maxAttempts}`，使额外模型 pass 有界且可重放。`tool_result_persist` 是同步 transcript 变换：在 OpenClaw-owned session 写入前改 assistant tool-result message；`details` 是 UI/诊断元数据，在 provider replay 与 compaction input 前被剥离，持久化还会执行大小 cap，超限替换为摘要并标记 `persistedDetailsTruncated:true`。它不等同“修改模型本轮已看到的 tool result”；官方 feature issue 明确指出该缺口（[issue #34144](https://github.com/openclaw/openclaw/issues/34144)）。此外，官方 bug issue 曾记录 embedded runtime 未触发相关 hooks（[issue #60209](https://github.com/openclaw/openclaw/issues/60209)），所以 Quenda 必须用跨 harness contract tests 保证一致性。

建议统一 hook envelope：

```text
HookContext { run_id, session_id, turn_id, sequence, actor, capabilities }
HookResult<T> { decision, patch?, annotations?, retry?, audit }
HookSpec { phase, priority, mode: observe|transform|guard, timeout, failure_policy }
```

安全 guard 必须 awaited、fail-closed；observer 可隔离失败；transform 必须有确定性排序和不可变输入/显式 patch。不要让插件直接共享可变 messages 数组。

### F. OpenClaw setup agent 与 subagent

OpenClaw setup agent 的关键安全边界是“专用 authority tool，而非普通万能 agent”：只给单一 `openclaw` 配置 authority，隐藏 secret，禁用其他工具，把模型输出限制为可审计 proposal；最终应用仍走宿主校验/策略，远程 rescue 保持确定性（[CLI 文档](https://docs.openclaw.ai/cli/openclaw)）。公开材料未证明这是通用 ACID transaction；Quenda 应自己提供 optimistic revision、schema validation、dry-run、atomic write 和 rollback token。

OpenClaw `sessions_spawn` 非阻塞并立即返回 run id；完成结果以 internal parent-session event push 回请求者。需要结果的父 agent 调用 `sessions_yield` 结束当前 turn，让 completion event 成为下一条 model-visible message。默认 `maxSpawnDepth=1`，可配 1–5；`maxChildrenPerAgent=5`（范围 1–20）、global `maxConcurrent=8`、默认 timeout 900 秒。深度决定 session-tool 权限：leaf 不持有 session tools；orchestrator 仅获得 spawn/list/history 等受限集合。spawn 时把 requester 的 effective sender policy 快照及 role/control scope 写入 session metadata；当前全局/agent/provider/sandbox 限制仍继续生效。`/stop` cascade 到后代；陈旧 run、gateway restart 和 repeated re-wedge 有有界 orphan recovery 与 tombstone（[Subagents](https://github.com/openclaw/openclaw/blob/main/docs/tools/subagents.md)，[Session Tools](https://github.com/openclaw/openclaw/blob/main/docs/concepts/session-tool.md)）。

建议 Quenda 类型：

```text
SpawnRequest { task, parent_run_id, context_mode: isolated|fork, tool_policy, timeout, idempotency_key }
ChildRun { run_id, parent_run_id, depth, status, policy_snapshot, started_at, ended_at }
ChildCompletion { run_id, outcome, result_ref, summary, usage, error? }
CancelScope { run_id, cascade: bool, reason }
```

不要照搬无界 push：completion event 要可持久化、去重、按 parent revision 消费；fan-out 同时受全局 lane、每父节点和预算三层限制。

### G. 可直接采用 / 不要照搬

可直接采用：

- frozen session memory snapshot；后台 evolution fork；artifact revision + provenance + rollback。
- ratio trigger + absolute reserve 的 `ContextBudget`，以及 tool-call/result group 原子保护。
- registry、exposure、authorization 分层；MCP 动态发现不自动授权。
- typed lifecycle、优先级、terminal guard、明确 failure policy 和跨 harness 契约测试。
- goal state 持久化、有界 continuation、用户输入抢占、可暂停恢复。
- subagent 隔离 session、push completion、深度收紧权限、cascade cancel、orphan recovery。
- capability-based execution backend 与 secret forwarding，配置只引用 backend profile。

不要照搬：

- 自动改 `SOUL.md` / Identity；Hermes 官方证据不支持这一行为。
- 用一个计数器/review fork 混合 Memory 与 Skill 写权限。
- 纯 message-count compression gate、位置式永久 head、普通 assistant summary。
- 把 toolset/Skill 可见等同执行授权，或将全部动态 MCP schema 永久塞入 prompt。
- judge 出错一律 continue；有副作用的 Run 应默认 pause。
- 把 `tool_result_persist` 当成本轮模型输入变换；应另设 `before_model_tool_result` phase。
- 不 awaited 的安全 hook、共享可变 messages、不同 runtime 各自漏接 hook。
- 将聊天式配置包装成万能 agent；应是最小权限 proposal/validate/apply/rollback 协议。

## Codex 官方机制补充

Codex 的价值主要不是“照抄一组 hook 名称”，而是展示了如何把稳定
instructions、按需 Skills、插件包、hooks、memory 与 subagent 组合成一套可发现的
定制面。

### Hooks：值得借鉴的是信任与失败边界

Codex 官方 hook 事件覆盖 `SessionStart/SessionEnd`、`UserPromptSubmit`、
`PreToolUse/PermissionRequest/PostToolUse`、`PreCompact/PostCompact`、
`SubagentStart/SubagentStop` 和 `Stop`。多个匹配 hook 会运行；同一事件的 command
hook 可并发。非托管 hook 以内容 hash 取得信任，内容变化后需要重新审查；项目级
hook 只有在项目被信任后才加载。来源配置会合并，而不是由高优先级来源整个替换
（[Hooks 官方文档](https://developers.openai.com/codex/hooks)）。

但边界同样重要：当前真正执行的是 command handler，prompt/agent handler 虽可解析
但会跳过；`PreToolUse` / `PermissionRequest` 也不是所有工具执行面的完备安全边界，
部分 hosted tool 不经过本地 command hook。Quenda 因此应把 hook 作为扩展/集成面，
把真正授权保留在所有执行后端共同经过的 typed policy 中。大输出采用“有限 preview
+ artifact 路径”，可以避免 hook 输出无限膨胀上下文。

### Customization 与插件：同一注册表生成给人和模型的知识

Codex 把 `AGENTS.md` 定位为短小、持久的仓库指导；Skills 使用渐进披露——先暴露
元数据，被选中后再读取 `SKILL.md` 与所需资源/脚本；MCP 负责外部系统；插件用
`.codex-plugin/plugin.json` 打包并可附带 Skills、hooks、MCP、apps 与 assets
（[Customization](https://developers.openai.com/codex/concepts/customization)，
[Build a plugin](https://developers.openai.com/codex/plugins/build)）。

这支持 Quenda 采用一个 typed capability/extension registry，同时生成配置 schema、
CLI help、LLM 索引、authoring Skill、示例和契约测试。Agent 不应依赖训练时“记得
Quenda 怎么配”，而应能查询当前安装版本实际提供的能力。

### Memory 与 subagent：后台维护和显式并行

Codex 官方 memory 机制在会话空闲后后台处理，跳过仍活跃或太短的会话，并在持久化
前做 secret redaction；memory 是辅助召回，不是高于当前仓库指令的权威来源
（[Memories](https://developers.openai.com/codex/memories)）。这与 Hermes 的低频
Curator 一致：维护应离开活动 Run，并受 idle、最小证据量、额度和隐私 gate 约束。

Codex subagent 用隔离上下文并行处理任务，父 agent 汇总结果；本地 Codex 的委派由
用户明确要求或 `AGENTS.md` / Skill 指令触发，而不是每个任务无条件 fan-out
（[Subagents](https://developers.openai.com/codex/subagents)）。Quenda 的默认
orchestration policy 也应显式、可配置，并同时限制每父节点、全局并发和总预算。

### 对 Quenda 的净结论

- 采用：内容 hash 信任、项目 trust gate、来源合并、有限 hook 输出、渐进式 Skill、
  plugin manifest、后台 memory gate、隔离 subagent。
- 不照搬：把本地 hook 当成所有工具的安全边界；安全授权必须在统一执行协议内。
- 物理 prompt/cache 顺序与逻辑指令优先级应分离：稳定前缀优化不能改变 authority。
- Memory/Skill 更新提交新 revision；活动 Session 默认保持 frozen snapshot，显式 reload
  才建立新的 activation epoch。
