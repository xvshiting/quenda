# ADR-001: 异步策略与工具定义

## 状态

已接受

## 背景

需要确定：
1. Quenda 的异步执行策略
2. 用户定义工具的方式

## 决策

### 异步策略：混合模式

**Kernel 同步，Runtime 异步**

- **Kernel 层**：同步实现
  - 纯函数逻辑，便于测试
  - 不直接调用外部 API（通过 Provider 接口注入）
  - Model Provider 实现可选择同步或异步（通过 `run_in_executor` 适配）

- **Runtime 层**：异步实现
  - 使用 asyncio 管理并发
  - 事件发射异步非阻塞
  - 支持多个 Run 并发执行

**理由**：
- Kernel 核心逻辑简单，同步更易测试和推理
- Runtime 需要处理并发和 I/O，异步更自然
- 分层清晰，职责分明

### 工具定义：装饰器 + 类型注解为主，Tool 协议为扩展

**主要方式：装饰器 + 类型注解**

```python
@tool
def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read file contents."""
    ...
```

- 自动从类型注解生成 JSON Schema
- 自动从 docstring 提取描述
- 支持可选参数和默认值

**扩展方式：Tool 协议**

```python
class MyTool(Tool):
    name: str = "my_tool"
    description: str = "..."
    parameters: dict = {...}

    def execute(self, **kwargs) -> ToolResult:
        ...
```

- 用于需要复杂逻辑的工具
- 用于需要动态参数的工具
- 用于跨语言/跨平台的工具定义

**理由**：
- 装饰器方式覆盖 80% 用例，极简
- Tool 协议提供扩展点，满足特殊需求
- 符合 Python 生态习惯

## 后果

### 正面

- Kernel 测试简单，无需 mock async
- 用户定义工具简单直观
- 灵活性足够，不限制高级用法

### 负面

- 同步/异步边界需要明确处理
- 装饰器实现需要处理类型推断

### 实现

- Kernel 提供同步接口
- Runtime 在调用 Model Provider 时使用 `run_in_executor` 包装同步调用
- 装饰器内部实现 Tool 协议
