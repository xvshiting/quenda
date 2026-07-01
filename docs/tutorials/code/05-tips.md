# 使用技巧

Quenda Code 的最佳实践、常见问题和高级用法。

---

## 提问技巧

### ✅ 好的提问

```
❌ 模糊提问：
> 帮我改代码

✅ 清晰提问：
> 在 src/main.py 的第 42 行，handle_timeout 函数中的重试逻辑有 bug。
> 当网络超时时，它不会正确重置连接状态。帮我修复这个问题。

❌ 一次性问太多：
> 帮我重构整个项目

✅ 分步提问：
> 1. 先分析 src/ 目录下的模块依赖关系
> 2. 然后建议重构方案
> 3. 最后逐步实施
```

### 提供上下文

**好的上下文**：

```
我在开发一个 FastAPI 应用，使用 SQLAlchemy 2.0。
在 models/user.py 中定义了 User 模型，
在 api/users.py 中定义了 CRUD 接口。

帮我添加一个软删除功能，要求：
1. 在 User 模型增加 deleted_at 字段
2. 查询时默认过滤已删除的记录
3. 提供恢复接口
```

---

## 工具使用技巧

### 利用 \_summary 参数

工具调用时填写 `_summary` 参数可以让 Agent 的意图更透明：

```text
# Agent 调用工具时会这样显示：
[工具] read_file — 读取配置文件 config.yaml
[工具] search_text — 搜索所有测试文件中包含 "timeout" 的地方
[工具] run_shell — 运行测试验证修复
```

这样你可以在 Agent 执行时清晰了解它在做什么。

### 验证优先

```
> 帮我改完代码后跑一下测试

> 修改了这个函数，验证一下边界情况
```

Agent 在执行任务后会自动调用测试工具验证。

### 善用搜索

当处理大型项目时，先搜索再读取：

```
> 找到项目中所有用到数据库连接的地方
> 帮我 grep 一下所有 TODO 注释
```

---

## 模式选择策略

| 场景 | 推荐模式 | 原因 |
|------|---------|------|
| 快速问答 | chat | 响应最快，不需要代码质量要求 |
| 写代码 | code | 保证完整实现，有测试意识 |
| 调试 bug | code | 先分析再修复，关注根因 |
| 设计系统 | architect | 深入分析，讨论取舍 |
| 代码审查 | code | 关注具体实现问题 |
| 学习新概念 | chat 或 architect | 先 chat 了解，需要深度时切 architect |

### 模式混合使用

```text
# 先了解架构
> /mode architect
> 分析一下这个项目的模块架构

# 再切换到编码模式实现
> /mode code
> 根据刚才的分析，实现用户管理模块
```

---

## 高效工作流

### 探索式

```text
1. /mode architect → 了解项目整体架构
2. /mode code → 深入特定模块
3. 提问、修改、验证
4. /clear → 开始新任务
```

### 任务驱动

```text
1. 明确目标和约束条件
2. Agent 先分析再实施
3. 验证结果（跑测试）
4. 迭代优化
```

### 调试闭环

```text
1. 描述现象（什么错了？期望什么？）
2. Agent 分析根因（读了什么代码？发现了什么？）
3. 提出修复方案
4. 实施修复
5. 验证（重新运行测试）
```

---

## 会话管理

### 什么时候用 /clear

- 开始一个完全不同的话题时
- Agent 的上下文过长，响应变慢时
- 想重置 Agent 的"状态"时

### 什么时候用 /reset

- 系统提示词被污染时（比如 Agent 偏离了角色）
- 切换了模型后希望重新加载模式配置时
- 想让 Agent 重新加载所有指令时

### 什么时候用 /compress

- 会话超过 50 轮，感觉 Agent 开始遗漏细节
- token 用量接近模型上下文限制

---

## CLI 快捷方式

```bash
# 快速提问（不进入交互模式）
quenda code "列出当前目录的文件"

# 指定工作空间和模型
quenda code --workspace ~/projects/myapp --provider openai "分析项目结构"

# 恢复之前的会话
quenda code --session <id>

# 查看版本
quenda --version

# 运行自定义 Agent
quenda run --agent ./my-agent "帮我做..."
```

---

## 常见问题

### Q: 如何切换 API Key？

设置对应的环境变量：

```bash
export DEEPSEEK_API_KEY="sk-new-key"
```

### Q: Agent 访问不了某些文件？

工作空间边界限制。确保文件在运行 `quenda code` 的目录下。

### Q: 如何保存长会话？

会话自动保存。用 `/session info` 查看 ID，下次用 `--session <id>` 恢复。

### Q: 如何改变默认模型？

```bash
# 启动时指定
quenda code --provider anthropic --model claude-sonnet-4-20250514

# 运行时切换
> /model anthropic/claude-sonnet-4-20250514
```

### Q: 输出被截断了？

模型有最大输出 token 限制。可以：

1. 分步提问，不要一次要求太多
2. 使用 code 模式，要求写出完整实现
3. `/compress` 压缩上下文

### Q: 如何加速响应？

1. 切到 chat 模式（减少思考深度）
2. 使用更快的模型（如 deepseek-v4-flash）
3. 定期 `/clear` 减少上下文长度

### Q: 为什么 Agent 的行为和预期不一样？

1. 检查当前模式（`/mode`）
2. 检查系统提示词（`/context`）
3. 尝试 `/reset` 重置
4. 确保提问清晰明确

---

## 进阶技巧

### 用文档驱动开发

```text
> 我要为这个项目写一个新的 CLI 工具
> 先帮我设计接口文档，讨论确认后再实现
```

### 自动化重复任务

```text
> 帮我写一个脚本，自动运行格式化、lint、测试
> 然后每次改完代码都跑一遍
```

### 渐进式重构

```text
> 第一阶段：提取公共函数
> 第二阶段：拆分模块
> 第三阶段：添加类型注解
> 我们一步一步来
```

---

## 下一步

- [创建自定义 Agent](./04-customization.md) — 打造你的专属编码助手
- [Quenda Agent SDK 教程](../agent/01-quickstart.md) — 用 Python 开发 Agent

---

<div align="right">
  <a href="./04-customization.md">← 上一页</a> ·
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a>
</div>
