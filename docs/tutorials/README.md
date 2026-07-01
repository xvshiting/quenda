# Kora 框架文档

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0-blue" alt="Version 0.1.0">
  <img src="https://img.shields.io/badge/python-3.12+-green" alt="Python 3.12+">
</p>

**Kora** 是一个轻量级的 AI Agent 框架。提供两套核心产品：

---

## 📚 文档导航

### [Kora Agent 教程](./agent/01-quickstart.md) 🐍

面向 **Python 开发者**，教你如何使用 Kora SDK 构建和运行 AI Agent。

| 章节 | 内容 |
|------|------|
| [快速开始](./agent/01-quickstart.md) | 安装、第一个 Agent、基础用法 |
| [Agent 基础](./agent/02-agent-basics.md) | Agent 概念、系统提示词、配置 |
| [工具系统](./agent/03-tools.md) | 内置工具、@tool 装饰器、自定义工具 |
| [模型提供者](./agent/04-providers.md) | 模型注册、Provider 配置、多模型切换 |
| [会话管理](./agent/05-sessions.md) | Session 生命周期、持久化、上下文管理 |
| [事件系统](./agent/06-events.md) | 运行时事件、实时监控、事件驱动开发 |
| [进阶用法](./agent/07-advanced.md) | 指令系统、压缩策略、扩展机制 |
| [Policy 系统](./agent/09-policies.md) | 策略钩子、TraceSink、TerminationPolicy |
| [API 参考](./agent/08-references.md) | 完整 API 速查表 |

### [Kora Code 教程](./code/01-quickstart.md) 🐼

面向 **终端用户**，教你如何使用 `kora code` 命令行工具进行 AI 辅助编程。

| 章节 | 内容 |
|------|------|
| [快速开始](./code/01-quickstart.md) | 安装、运行、基本使用 |
| [命令系统](./code/02-commands.md) | 内置命令详解（/help, /clear, /exit 等） |
| [模式系统](./code/03-modes.md) | chat/code/architect 三种模式 |
| [自定义 Agent](./code/04-customization.md) | 配置、主题、自定义指令 |
| [使用技巧](./code/05-tips.md) | 最佳实践、常见问题 |

---

## 📋 更新日志

查看 [CHANGELOG.md](./CHANGELOG.md) 了解框架的最新变化。

## 🚀 快速链接

- **安装**: `pip install kora-agent`
- **启动 Kora Code**: `kora code`
- **CLI 帮助**: `kora --help`
- **运行自定义 Agent**: `kora run --agent /path/to/AGENT.md`

---

<div align="right">
  <a href="../../README.md">🏠 返回项目首页</a>
</div>

*文档版本: v0.1.0 · 最后更新: 2025-06-24*
