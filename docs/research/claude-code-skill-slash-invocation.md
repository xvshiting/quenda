# Claude Code 的 Skill Slash 调用语义

研究日期：2026-07-25

## 结论

Claude Code 将自定义 command 合并进了 Skills。`/skill-name [args]` 是用户显式调用
prompt-based Skill 的入口，不等同于 `/help`、`/compact` 这类由宿主执行固定逻辑的内置命令。

普通自然语言触发和 slash 显式触发最终都会加载完整的 `SKILL.md`，主要区别是触发者、
确定性、参数入口和可见性控制。

| 维度 | 普通自然语言触发 | `/skill-name [args]` |
|---|---|---|
| 触发者 | Claude 根据 description 判断 | 用户明确指定 |
| 确定性 | 可能不触发或选错 Skill | 确定调用指定 Skill |
| 参数 | 来自整条自然语言任务 | skill 名后的文本作为 arguments |
| 发现 | description 提供给 Claude | 默认出现在 `/` 菜单和补全中 |
| 完整内容 | 触发时按需加载 | 调用时按需加载 |
| 禁止方式 | `disable-model-invocation: true` | `user-invocable: false` |

## 参数处理

Claude Code 会在把 Skill 交给模型之前预处理参数：

- `$ARGUMENTS`：skill 名后的完整文本。
- `$ARGUMENTS[N]` 或 `$N`：按 shell quoting 拆分后的第 N 个参数。
- `arguments` frontmatter：声明命名位置参数，可用 `$name` 引用。
- 如果正文没有 `$ARGUMENTS`，Claude Code 会把 `ARGUMENTS: <输入>` 追加到正文末尾。
- `argument-hint` 只用于补全提示。

因此 `/fix-issue 123` 的含义不是先激活 Skill、再单独发送 `123`，而是把参数代入
Skill 内容，形成这一轮交给模型的最终 prompt。

## 调用权限和上下文

- 默认：用户和 Claude 都可以调用；description 常驻可用 Skill 列表，完整正文在调用时加载。
- `disable-model-invocation: true`：仅用户可通过 slash 调用；该 Skill 对 Claude 隐藏，
  直到用户调用时才加载，因此未调用时上下文成本为零。
- `user-invocable: false`：从 `/` 菜单隐藏，只允许 Claude 自动调用。
- Skill 一旦加载，其内容会留在当前会话上下文中；`context: fork` 可以改为在隔离的
  subagent 上下文运行。

## 与传统 Slash Command 的区别

Claude Code 的内置命令可能直接执行宿主行为，例如改变会话、压缩上下文或打开配置界面。
Skill slash 调用则是 prompt-based：宿主负责发现、权限、参数替换和加载，实际任务仍由
模型根据 Skill 指令及工具完成。

自定义 `.claude/commands/<name>.md` 仍兼容，但官方推荐迁移到
`.claude/skills/<name>/SKILL.md`。二者重名时 Skill 优先；插件 Skill 使用
`plugin-name:skill-name` 命名空间避免冲突。

## 对 Quenda 的实现启示

第一版应把 `/skill-name [args]` 建模为一种“转交给模型的命令结果”，而不是让
`SkillCommand.execute()` 直接完成任务：

1. `/` 菜单和补全列出允许用户调用的 Skills。
2. 用户输入后，Host 确定性地加载指定 Skill。
3. Host 将 arguments 注入 Skill 内容或明确附加到本轮模型输入。
4. 本轮继续进入正常 model/tool loop，而不是像普通管理命令一样打印结果后结束。
5. 内置命令冲突策略必须显式定义。

后续若追求 Claude Code 兼容，再加入 `argument-hint`、`arguments`、
`disable-model-invocation`、`user-invocable`、模型覆盖和 forked context。

## 官方来源

- [Extend Claude with skills](https://code.claude.com/docs/en/slash-commands)
- [Extend Claude Code — feature loading overview](https://code.claude.com/docs/en/features-overview)
- [Commands reference](https://code.claude.com/docs/en/commands)
- [Slash commands in the Agent SDK](https://code.claude.com/docs/en/agent-sdk/slash-commands)
