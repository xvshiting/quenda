# 工具系统

Quenda 的工具系统是 Agent 能力的核心扩展机制。

---

## 工具协议 (Tool Protocol)

所有工具必须实现 `Tool` 协议：

```python
class Tool(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def parameters(self) -> dict: ...  # JSON Schema
    def execute(self, **kwargs) -> ToolResult: ...
```

框架提供了两种定义方式。

---

## 方式一：@tool 装饰器（推荐）

最简单的工具定义方式：

```python
from quenda import tool

@tool
def search_docs(query: str, max_results: int = 5) -> str:
    """搜索文档库。"""
    # 函数体
    return results

@tool(name="custom_name")  # 自定义工具名
def my_func(x: int) -> str:
    """工具描述（第一行）。"""
    return str(x)
```

### 自动生成

装饰器自动完成以下工作：

1. **工具名** → 函数名（或 `name` 参数）
2. **描述** → docstring 第一行
3. **参数 Schema** → 从类型注解自动生成 JSON Schema
4. **返回值** → 自动包装为 `ToolResult`

### 类型映射

| Python 类型 | JSON Schema 类型 |
|------------|-----------------|
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `list` | `array` |
| `dict` | `object` |
| `Optional[str]` | `string`（非 None 类型） |

### 参数规则

- **无默认值** → 必填参数（加入 `required` 列表）
- **有默认值** → 可选参数（加入 `default`）
- **`_summary`** → 框架保留参数，用于显示，不会传给函数

---

## 方式二：实现 Tool 协议

适用于复杂工具：

```python
from quenda.kernel.types import ToolResult

class MyComplexTool:
    @property
    def name(self) -> str:
        return "complex_tool"

    @property
    def description(self) -> str:
        return "一个复杂工具"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "输入内容",
                },
            },
            "required": ["input"],
        }

    def execute(self, **kwargs: object) -> ToolResult:
        input_data = kwargs.get("input", "")
        result = self._process(input_data)
        return ToolResult(
            call_id="",  # 框架会设置
            name=self.name,
            content=str(result),
        )
```

---

## 方式三：继承 BaseTool

适用于带工作空间的工具：

```python
from pathlib import Path
from quenda.tools.base import BaseTool
from quenda.kernel.types import ToolResult

class MyWorkspaceTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "工作空间内的工具"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径",
                },
            },
            "required": ["path"],
        }

    def execute(self, **kwargs: object) -> ToolResult:
        path = kwargs["path"]
        validated = self._validate_workspace_path(str(path))
        # validated 保证在工作空间内
        ...
```

### BaseTool 提供的功能

| 方法 | 用途 |
|------|------|
| `_validate_workspace_path(path)` | 安全校验路径在工作空间内 |
| `_truncate_output(output, max_bytes)` | 截断过大输出（默认 1MB） |
| `self.workspace` | 工作空间根目录 (Path) |

---

## 内置工具详解

### 核心 10 工具

使用 `get_core_tools(workspace_root)` 获取：

#### 文件系统工具

```python
from quenda.tools import (
    ListFilesTool,   # 列出文件/目录
    SearchTextTool,  # 全文搜索
    ReadFileTool,    # 读取文件
    WriteFileTool,   # 创建文件
    ApplyPatchTool,  # 安全修改文件
)
```

**ListFilesTool** — 浏览目录结构：

```python
# list_files(path="src", depth=2, pattern="*.py")
# 参数：
#   path: 目录路径
#   depth: 遍历深度（默认1）
#   pattern: 通配符过滤
```

**SearchTextTool** — 搜索文本内容：

```python
# search_text(pattern="class.*Handler", include="*.py", context_lines=2)
# 参数：
#   pattern: 搜索模式（支持正则）
#   include: 文件过滤
#   context_lines: 上下文行数
```

**ReadFileTool** — 读取文件内容：

```python
# read_file(path="main.py", start=1, end=50)
# 参数：
#   path: 文件路径
#   start: 起始行（1-indexed，负数从末尾算）
#   end: 结束行
```

**WriteFileTool** — 创建/覆盖文件：

```python
# write_file(path="new.py", content="print('hello')")
# 自动创建父目录
```

**ApplyPatchTool** — 安全修改文件（推荐用于修改）：

```python
# apply_patch(path="file.py", old_text="旧的", new_text="新的")
# 支持 dry_run=True 预览
```

#### 执行工具

```python
from quenda.tools import RunShellTool, PythonExecutionTool
```

**RunShellTool** — 执行 Shell 命令：

```python
# run_shell(command="python test.py", cwd="src", timeout=30)
# 沙箱执行，有超时和安全限制
```

**PythonExecutionTool** — 沙箱执行 Python：

```python
# execute_python(code="print('hello')", timeout=30)
# 受限环境，仅允许标准库子集
```

#### 交互工具

```python
from quenda.tools import RequestInteractionTool
```

当 Agent 需要用户决策时使用：

```python
# request_interaction(
#     kind="choice|confirm|input|menu",
#     title="选择数据库",
#     message="使用哪个数据库？",
#     options=[...],
# )
```

### 网络工具

```python
from quenda.tools import (
    HTTPRequestTool,  # HTTP 请求（SSRF 保护）
    WebFetchTool,     # 网页内容获取
)
```

### 按需导入

```python
# 全部核心工具
from quenda.tools import get_core_tools

# 仅文件系统
from quenda.tools import get_filesystem_tools

# 仅执行
from quenda.tools import get_execution_tools

# 仅网络
from quenda.tools import get_network_tools
```

---

## ToolResult

工具的返回值，框架会将结果返回给模型：

```python
from quenda.kernel.types import ToolResult

ToolResult(
    call_id="",       # 框架会设置
    name="tool_name",
    content="结果文本",
    is_error=False,   # 标记错误
)
```

---

## Skills Framework（能力包）

除了自定义工具，Quenda 还提供了 **Skills** 系统——可组合的能力包，包含指令和资源。

### Skills vs Tools

| 概念 | 用途 | 示例 |
|------|------|------|
| **Tool** | 可执行函数，模型可调用 | `read_file`, `run_shell` |
| **Skill** | 指令包，指导模型行为 | 代码审查、测试编写 |

### 使用 Skills

在 Agent 配置中激活：

```yaml
# config.yaml
skills:
  - code-review    # 代码审查技能
  - testing        # 测试编写技能
```

或在 REPL 中动态激活：

```text
> /skill list                  # 查看可用技能
> /skill activate code-review  # 激活技能
> /skill resources             # 查看技能资源
```

### 创建 Skill

```
.quenda/skills/code-review/
├── SKILL.md           # 技能定义（必需）
├── references/        # 参考文档
│   └── style-guide.md
├── templates/         # 模板文件
│   └── review-report.md
└── scripts/           # 可执行脚本
    └── analyze.py
```

`SKILL.md` 格式：

```yaml
---
name: code-review
description: Apply when reviewing code or providing feedback on code changes.
version: "1.0.0"
---

# Code Review

When reviewing code, provide thorough, constructive feedback...
```

详细说明见 [Skills 文档](../../skills.md)。

---

## 最佳实践

1. **使用 `_summary` 参数**：在工具调用时填写，让用户了解你在做什么
2. **清晰的参数命名**：模型靠名字理解参数含义
3. **完整的 docstring**：模型靠描述决定何时调用工具
4. **错误处理**：在工具内部捕获异常，返回友好的错误信息
5. **适度原子化**：工具粒度适中，太细增加调用次数，太粗降低复用性

---

## 下一步

- [模型提供者](./04-providers.md) — 配置不同的 AI 模型
- [Agent 基础](./02-agent-basics.md) — Agent 核心概念

---

<div align="right">
  <a href="./02-agent-basics.md">← 上一页</a> ·
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a> ·
  <a href="./04-providers.md">下一页 →</a>
</div>
