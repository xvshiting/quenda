# 快速开始 — Quenda Code

Quenda Code 是 Quenda 框架的正式编码助手。本节教你如何使用 CLI 工具进行 AI 辅助编程。

---

## 安装

```bash
pip install quenda
```

如果 Quenda Code 是独立安装的：

```bash
pip install quenda[code]
```

验证安装：

```bash
quenda --help
```

---

## 快速开始

### 单次执行模式

直接提问，Agent 执行后返回结果：

```bash
quenda code "帮我写一个 Python 斐波那契函数"
```

指定工作空间：

```bash
quenda code --workspace /path/to/my-project "分析项目结构"
```

指定模型：

```bash
quenda code --provider anthropic --model claude-sonnet-4-20250514 "帮我重构这段代码"
```

### 交互式 REPL 模式

不加消息参数进入交互模式：

```bash
quenda code
```

启动后你会看到：

```
🐼 Quenda Code Agent
Workspace: ws_xxx  (当前目录)
Session: abc123...
Model: deepseek/deepseek-v4-flash

> _
```

在 `>` 提示符后输入你的问题或指令。

---

## 基本使用

### 提问

```
> 帮我写一个 REST API 客户端

> 这个函数有什么问题？

> 解释一下这个项目的架构
```

### 使用命令

```
> /help    查看所有命令
> /mode code  切换到编程模式
> /clear  清除对话历史
> /exit   退出
```

### 退出 REPL

```
> /exit
# 或 Ctrl+C / Ctrl+D
```

---

## 工作空间

Quenda Code 默认使用当前目录作为工作空间：

```bash
cd /path/to/my-project
quenda code
# 工作空间: /path/to/my-project
```

工作空间边界意味着 Agent **不能**访问工作空间之外的文件，这是安全设计。

---

## 指定模型

### 方式一：命令行参数

```bash
quenda code --provider anthropic --model claude-sonnet-4-20250514
quenda code --provider openai --model gpt-4o
quenda code --provider deepseek --model deepseek-v4-flash
```

### 方式二：运行时切换

在 REPL 中动态切换模型：

```
> /model                    # 查看当前模型
> /model openai/gpt-4o      # 切换到 OpenAI GPT-4o
> /model deepseek/deepseek-v4-flash  # 切换到 DeepSeek
> /model claude-sonnet-4-20250514    # 在当前提供商下搜索
```

---

## API Key 配置

在环境变量中设置对应的 API Key：

```bash
export DEEPSEEK_API_KEY="sk-xxx"
export ANTHROPIC_API_KEY="sk-ant-xxx"
export OPENAI_API_KEY="sk-xxx"
```

可以同时配置多个，运行中用 `/model` 切换。

---

## 会话管理

### 查看会话

```
> /session info    查看当前会话信息
> /session list    查看所有保存的会话
```

### 恢复会话

```bash
# 启动时指定会话
quenda code --session <session-id>
```

### 清除历史

```
> /clear   清除对话历史
> /reset   重置会话（清除历史并恢复系统提示词）
```

---

## 示例场景

### 代码审查

```
> 帮我 review 一下 src/main.py 这段代码
```

### 修复 Bug

```
> 运行测试发现 test_api.py 报错，帮我看看
```

### 项目分析

```
> 介绍一下这个项目的整体架构
```

### 重构

```
> 把 utils.py 中的几个函数拆分成独立的模块
```

### 学习

```
> 解释一下 Python 的 async/await 机制
```

---

## 下一步

- [命令系统](./02-commands.md) — 所有内置命令详解
- [模式系统](./03-modes.md) — chat/code/architect 三种模式
- [使用技巧](./05-tips.md) — 最佳实践与常见问题

---

<div align="right">
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a> ·
  <a href="./02-commands.md">下一页 →</a>
</div>
