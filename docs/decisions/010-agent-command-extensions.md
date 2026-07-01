# ADR-010: Agent 命令扩展机制

## 状态

提议 (2026-06-24)

## 背景

当前 Quenda 的命令系统（`/help`, `/mode`, `/model` 等）全部硬编码在框架的 `src/quenda/host/commands.py` 中。用户无法在不修改框架代码的情况下添加自定义命令。

这违背了 Quenda 的核心设计原则：
- "框架提供机制，用户自己扩展能力"
- "Agent equality" — 官方 Code Agent 和外部 Agent 使用相同的公共 API

用户期望的扩展模型是：
- 用户在仓库外自建一个 agent 目录
- `quenda run --agent /path/to/agent ...`
- Agent 自带自己的命令，不影响框架和其他 agent

## 决策

采用 **Agent Package 命令扩展** 模型：

### 目录结构

```
my-agent/
├── AGENT.md           # 身份、原则、默认行为
├── config.yaml        # 模型、工具、扩展加载配置
├── instructions/      # 可选的指令文件
└── extensions/
    └── commands/      # 命令扩展目录
        ├── status.py  # 自定义命令实现
        ├── deploy.py
        └── ...
```

### 加载契约

`extensions/commands/*.py` 模块必须导出以下之一：

1. **推荐方式：`commands` 列表**
   ```python
   from quenda.host.commands import Command, CommandResult, CommandContext
   
   class StatusCommand:
       @property
       def name(self) -> str:
           return "status"
       
       @property
       def description(self) -> str:
           return "Show deployment status"
       
       @property
       def usage(self) -> str:
           return "/status"
       
       def execute(self, args: str, context: CommandContext) -> CommandResult:
           return CommandResult(status="ok", message="All systems operational")
   
   # 导出命令列表
   commands = [StatusCommand()]
   ```

2. **备选方式：`register` 函数**
   ```python
   def register(registry: CommandRegistry) -> None:
       registry.register(StatusCommand())
       registry.register(DeployCommand())
   ```

### 加载流程

Host 在加载 Agent Package 时：

1. 扫描 `extensions/commands/` 目录
2. 动态加载每个 `.py` 模块
3. 查找 `commands` 列表或 `register` 函数
4. 将命令注册到 `CommandRegistry`
5. 与框架内置命令合并（用户命令可覆盖内置命令）

### 合并策略

- 框架内置命令始终存在（`/help`, `/exit`, `/mode` 等）
- 用户命令按名称注册
- **同名命令**：用户命令覆盖内置命令（允许定制行为）

### 安全边界

- 命令代码运行在 Host 层，拥有与内置命令相同的权限
- 命令通过 `CommandContext` 访问 Session/Agent/Storage
- 命令不应直接访问 Kernel 或 Runtime 内部状态
- 命令代码来自 agent 目录，由用户自行信任

## 理据

### 为什么支持这个模型

1. **用户不改框架**：扩展代码放在 agent 目录，不侵入 Quenda 源码
2. **命令与 Agent 绑定**：每个 agent 有自己的命令集，互不干扰
3. **符合 Unix 哲学**：小模块、可组合、目录即边界
4. **声明式接入 + 代码实现**：平衡灵活性和可维护性

### 为什么不放在 AGENT.md

`AGENT.md` 定义身份和行为准则，不应包含可执行代码。命令是行为实现，需要 Python 代码的能力。

### 为什么不全局注册

全局命令会影响所有 agent，破坏隔离性。Agent-own-commands 是正确的边界。

### 为什么允许覆盖内置命令

用户可能想定制 `/help` 的输出格式，或 `/exit` 的清理逻辑。覆盖而非禁用，保持灵活性。

## 实现

### 涉及文件

| 文件 | 变更 |
|------|------|
| `src/quenda/host/loader.py` | 添加命令扩展扫描和加载 |
| `src/quenda/host/commands.py` | 添加 `merge_registry()` 函数 |
| `src/quenda/cli.py` | 使用合并后的 registry |
| `docs/getting-started.md` | 添加命令扩展文档 |

### 代码示例

```python
# src/quenda/host/loader.py

def load_agent_commands(agent_path: Path, registry: CommandRegistry) -> int:
    """Load command extensions from agent package."""
    commands_dir = agent_path / "extensions" / "commands"
    if not commands_dir.exists():
        return 0
    
    loaded = 0
    for py_file in commands_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        
        module = _load_module(py_file)
        
        # 优先：commands 列表
        if hasattr(module, "commands"):
            for cmd in module.commands:
                registry.register(cmd)
                loaded += 1
        
        # 备选：register 函数
        elif hasattr(module, "register"):
            module.register(registry)
            loaded += 1
    
    return loaded
```

## 后果

### 正面

- 用户可以为特定 agent 定义专用命令
- 命令系统可扩展，无需修改框架
- Agent package 成为完整的自包含单元

### 负面

- 需要动态模块加载（有安全考量）
- 用户需要理解 Command Protocol
- 调试扩展命令可能更复杂

### 风险缓解

- 加载契约简单明确，减少出错
- 不加载 `_` 开头的文件（避免误加载辅助模块）
- 命令加载失败时记录警告，不中断 agent 启动

## 未来扩展

- **命令元数据**：可选的 `*.yaml` 文件定义命令描述、参数提示
- **命令验证**：加载时检查 Command Protocol 实现
- **命令热加载**：开发模式下监听文件变化，重载命令
- **命令隔离**：限制命令访问特定资源