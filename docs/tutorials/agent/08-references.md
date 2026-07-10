# API 参考

Quenda 框架完整 API 速查表。

---

## 顶层 API (`quenda`)

```python
from quenda import (
    __version__,                    # str: 版本号
    Agent,                          # class: Agent 类
    Session,                        # class: 会话类
    tool,                           # decorator: 工具装饰器

    # 模型相关
    Model,                          # class: 模型运行时
    ModelSpec,                      # class: 模型规格
    ModelCost,                      # class: 模型费用
    Provider,                       # class: 提供商
    ProviderSpec,                   # class: 提供商规格
    get_provider_registry,          # function: 获取全局注册表
)
```

---

## Runtime (`quenda.runtime`)

```python
from quenda.runtime import (
    Agent,          # Agent 类
    AgentConfig,    # Agent 不可变配置
    AgentDefinition,# Agent 协议

    Session,        # 会话类
    SessionState,   # 会话状态（纯数据）

    Run,            # 运行执行器
    RunStatus,      # 运行状态枚举

    # 事件
    RunStarted,
    ModelCalled,
    ModelResponded,
    ToolExecuted,
    ErrorOccurred,
    RunCompleted,
    RunInterrupted,
    RunTerminated,      # 策略终止
    CompressionStarted,
    CompressionCompleted,

    # TraceSink
    TraceSink,          # 协议
    NullTraceSink,      # 空实现
    JsonlTraceSink,     # JSONL 文件

    # TerminationPolicy
    TerminationState,   # 策略输入
    TerminationDecision,# 策略输出
    TerminationPolicy,  # 协议
    NeverTerminatePolicy,       # 默认：不终止
    MaxStepsPolicy,             # 最大步数
    TimeBudgetPolicy,           # 时间预算
    TokenBudgetPolicy,          # Token 预算
    ConsecutiveErrorPolicy,     # 连续错误
    CompositeTerminationPolicy, # 组合策略

    # Tool Policies
    ToolSelectionRequest,
    ToolSelectionDecision,
    ToolSelectionPolicy,
    AllowAllToolSelectionPolicy,
    DenylistToolSelectionPolicy,
    AllowlistToolSelectionPolicy,
    ToolResultEnvelope,
    ProcessedToolResult,
    ToolResultProcessingPolicy,
    PassthroughToolResultProcessingPolicy,
    TruncatingToolResultProcessingPolicy,
    LineLimitedToolResultProcessingPolicy,
)
```

### Agent

```python
agent = Agent(
    name,                    # str: 名称
    system_prompt=None,      # str | None: 系统提示词
    tools=None,              # list[Tool] | None: 工具列表
    model=None,              # Model | None: 模型
    storage=None,            # Storage | None: 存储后端
    compression_policy=None, # CompressionPolicy | None: 压缩策略
    compressor=None,         # Compressor | None: 压缩器
)

agent.name             # str
agent.config           # AgentConfig
agent.model            # Model | None
agent.system_prompt    # str | None
agent.tools            # list[Tool]
agent.storage          # Storage | None

agent.set_model(model)                           # 设置模型
agent.set_system_prompt(prompt)                  # 更新提示词
agent.set_storage(storage)                       # 设置存储

agent.open_session(session_id=None)              # -> Session
agent.load_session(session_id)                   # -> Session | None
agent.list_sessions()                            # -> list[SessionState]

await agent.run(message, model=None, on_event=None)    # -> str
agent.run_sync(message, model=None, on_event=None)     # -> str
```

### Session

```python
session = agent.open_session()

session.id             # str
session.state          # SessionState
session.messages       # list[Message]
session.system_prompt  # str | None
session.tools          # list[Tool]
session.mode           # str: get/set
session.model          # Model | None

session.set_model(model)            # 切换模型
session.set_system_prompt(prompt)   # 更新提示词
session.save()                      # 持久化

await session.send(message, model=None, on_event=None)  # -> str
session.send_sync(message, model=None, on_event=None)   # -> str
session.clear()                     # 清除历史
len(session)                        # 消息数量
```

### SessionState

```python
state = SessionState.create(agent_name, session_id=None)

state.id             # str
state.agent_name     # str
state.messages       # list[Message]
state.metadata       # dict
state.created_at     # datetime
state.usage          # SessionUsage
state.summary_blocks # list[SummaryBlock]
state.archive_refs   # list[str]

state.add_message(message)
state.add_user_message(content)
state.clear()
len(state)
```

### Run

```python
run = Run.create(
    agent,               # AgentDefinition
    session,             # SessionState
    model,               # Model
    storage=None,        # Storage | None
    trace_sink=None,     # TraceSink | None
    termination_policy=None,  # TerminationPolicy | None
)

run.id         # str
run.agent      # AgentDefinition
run.session    # SessionState
run.model      # Model
run.status     # RunStatus
run.trace_sink # TraceSink | None
run.termination_policy  # TerminationPolicy | None

run.on_event(handler)                                 # 注册事件处理
async for event in run.execute(message): ...          # 异步迭代
events = await run.execute_to_completion(message)     # 收集所有事件
events = run.execute_sync(message)                    # 同步执行
```

---

## Kernel (`quenda.kernel`)

底层执行引擎，不依赖 Agent/Session 概念：

```python
from quenda.kernel import (
    Kernel,          # 核心执行引擎
    KernelStep,      # 执行步骤（model/tool）
    Model,           # 模型协议
    Tool,            # 工具协议
    ToolRegistry,    # 工具注册表
    Message,         # 消息
    ModelResponse,   # 模型响应
    ToolCall,        # 工具调用
    ToolResult,      # 工具结果
)

kernel = Kernel(model, tools, max_iterations=100)
for step in kernel.run(messages):
    if step.type == "model":
        response: ModelResponse = step.content
    elif step.type == "tool":
        result: ToolResult = step.content

steps = kernel.run_to_completion(messages)
```

### 核心类型

```python
from quenda.kernel.types import Message, ToolCall, ToolResult
from quenda.kernel.types import ModelResponse, StreamChunk, UsageStats

Message(role="user|assistant|system", content=str|list)

ToolCall(id, name, arguments)

ToolResult(call_id, name, content, is_error=False)

ModelResponse(
    content=None,           # str | None
    tool_calls=[],          # list[ToolCall]
    stop_reason="end_turn", # "end_turn"|"tool_use"|"max_tokens"|"stop_sequence"
    usage=None,             # UsageStats | None
)

StreamChunk(content=None, tool_calls=None, is_final=False)

UsageStats(
    input_tokens=0,
    output_tokens=0,
    cached_input_tokens=None,
    reasoning_tokens=None,
)
```

---

## 工具 (`quenda.tools`)

### 工具装饰器

```python
from quenda import tool

@tool
def my_tool(param1: str, param2: int = 10) -> str:
    """工具描述（第一行作为 description）。"""
    return result

@tool(name="custom_name")
def my_func(x: str) -> str: ...
```

### 内置工具类

```python
from quenda.tools import (
    ListFilesTool,
    SearchTextTool,
    ReadFileTool,
    WriteFileTool,
    ApplyPatchTool,
    RunShellTool,
    PythonExecutionTool,
    RequestInteractionTool,
    HTTPRequestTool,
    WebFetchTool,
    FunctionTool,
)

# 快捷方式
tools = get_core_tools(workspace_root)       # 10 个核心工具
tools = get_filesystem_tools(workspace_root) # 5 个文件工具
tools = get_execution_tools(workspace_root)  # 2 个执行工具
tools = get_network_tools()                  # 2 个网络工具
```

### 工具基类

```python
from quenda.tools.base import BaseTool

class MyTool(BaseTool):
    workspace  # Path: 工作空间根目录

    def _validate_workspace_path(self, path: str) -> Path
    def _truncate_output(self, output: str, max_bytes=1_000_000) -> tuple[str, bool]
```

### 交互工具

```python
from quenda.tools import RequestInteractionTool
# request_interaction(kind, title, message, options)
#   kind: "choice" | "confirm" | "input" | "menu"
#   options: [{id, label, description, is_default}]
```

---

## 模型提供者 (`quenda.providers`)

### ProviderRegistry

```python
from quenda.providers import get_provider_registry

registry = get_provider_registry()

registry.register(spec)                     # 注册提供商
registry.unregister(provider_id)            # 注销
registry.get_provider(provider_id)          # -> Provider | None
registry.get_model(provider_id, model_id)   # -> Model
registry.has_provider(provider_id)          # -> bool
registry.list_providers()                   # -> list[str]
registry.list_all_models()                  # -> list[tuple[str, str]]
```

### ProviderSpec

```python
ProviderSpec(
    id,              # str: 唯一标识
    name,            # str: 显示名称
    base_url,        # str: API 地址
    api="openai-completions",  # str: 协议
    api_key=None,    # str | None: API Key（支持 ${ENV_VAR}）
    headers={},      # dict: 额外请求头
    models=(),       # tuple[ModelSpec]: 模型列表
    timeout=None,    # float | None: 超时
    max_retries=None,# int | None: 重试次数
)
```

### ModelSpec

```python
ModelSpec(
    id,                  # str: 模型 ID
    name,                # str: 模型名称
    input=("text",),     # tuple[str]: 输入类型
    output=("text",),    # tuple[str]: 输出类型
    reasoning=False,     # bool: 是否支持推理
    tool_calling=True,   # bool: 是否支持工具调用
    streaming=True,      # bool: 是否支持流式
    vision=False,        # bool: 是否支持视觉
    context_window=None, # int | None: 上下文窗口
    max_output_tokens=None, # int | None: 最大输出
    cost=None,           # ModelCost | None: 费用
    api=None,            # str | None: 协议覆盖
    base_url=None,       # str | None: URL 覆盖
    headers={},          # dict: 请求头覆盖
)
```

### 错误类型

```python
from quenda.providers.errors import (
    QuendaError,               # 基类
    ProviderError,           # 提供商错误
    AuthenticationError,     # 认证错误
    APIError,                # API 错误
    RateLimitError,          # 限流
    NetworkError,            # 网络错误
    ModelNotFoundError,      # 模型不存在
    UnsupportedFeatureError, # 不支持的特性
)
```

---

## Host 层 (`quenda.host`)

### Agent 加载

```python
from quenda.host import (
    load_agent_from_markdown,  # 从 AGENT.md 加载
    load_agent_package,        # 加载 Agent 包
    load_agent_commands,       # 加载自定义命令
    load_agent_interactions,   # 加载自定义交互
    find_builtin_agent,        # 查找内置 Agent
    setup_agent,               # 完整设置 Agent
)
```

### 存储

```python
from quenda.host.storage import (
    Storage,            # 存储协议
    FileStorage,        # 文件存储实现
    FileStorageConfig,  # 文件存储配置
    RunState,           # 运行状态
)
```

### 命令系统

```python
from quenda.host.commands import (
    Command,             # 命令协议
    CommandResult,       # 命令结果
    CommandContext,      # 命令上下文
    CommandRegistry,     # 命令注册表
    create_default_registry,  # 创建默认注册表

    # 内置命令
    HelpCommand,
    ClearCommand,
    ExitCommand,
    SessionCommand,
    ModelCommand,
    ModeCommand,
    ContextCommand,
    ResetCommand,
    CompressCommand,
    StatusCommand,
)
```

### 交互系统

```python
from quenda.host.interactions import (
    Interaction,
    InteractionKind,
    InteractionRequest,
    InteractionResponse,
    InteractionContext,
    InteractionRegistry,
    ChoiceInteraction,
    ConfirmInteraction,
    InputInteraction,
    MenuInteraction,
)
```

### 工作空间

```python
from quenda.host.workspace import (
    WorkspaceBinding,
    WorkspaceResolver,
)
```

### 身份

```python
from quenda.host.identity import (
    User,
    IdentityResolver,
    EnvIdentityResolver,
    StaticIdentityResolver,
    DefaultUserResolver,
)
```

### 指令系统

```python
from quenda.host.instructions import (
    InstructionScope,
    InstructionSource,
    TemplateContext,
    InstructionComposer,
    resolve_instruction_sources,
)
```

---

## 界面层 (`quenda.interface`)

```python
from quenda.interface import (
    InterfaceTheme,        # 主题配置
    ConsoleRenderer,       # 控制台渲染器
    SpinnerIndicator,      # 加载动画
    StreamingEventHandler, # 流式事件处理
    CollectingEventHandler,# 事件收集
    CompositeEventHandler, # 组合事件处理
    render_markdown_lite,  # Markdown 渲染
    select_option,         # 选项选择器
    create_repl_input,     # 输入处理器
    get_status_bar,        # 状态栏
    WelcomeContext,        # 欢迎上下文
    DefaultWelcomeProvider,# 默认欢迎页
)
```

---

## Policy 系统 (`quenda.runtime`)

### TraceSink

```python
from quenda.runtime import TraceSink, NullTraceSink, JsonlTraceSink

# 协议
class TraceSink(Protocol):
    def record(self, event: AnyEvent) -> None: ...

# 内置实现
sink = NullTraceSink()                      # 空实现
sink = JsonlTraceSink("traces/run.jsonl")   # JSONL 文件

# 使用
run = Run.create(agent, session, model, trace_sink=sink)
```

### TerminationPolicy

```python
from quenda.runtime import (
    TerminationPolicy,
    TerminationState,
    TerminationDecision,
    NeverTerminatePolicy,
    MaxStepsPolicy,
    TimeBudgetPolicy,
    TokenBudgetPolicy,
    ConsecutiveErrorPolicy,
    CompositeTerminationPolicy,
)

# 协议
class TerminationPolicy(Protocol):
    def should_terminate(self, state: TerminationState) -> TerminationDecision: ...

# TerminationState
state = TerminationState(
    step_count=10,
    tool_round_count=5,
    elapsed_time_ms=60000,
    total_input_tokens=10000,
    total_output_tokens=5000,
    total_tokens=15000,
    error_count=0,
    consecutive_error_count=0,
    run_id="...",
    session_id="...",
    agent_name="...",
)

# 内置策略
policy = NeverTerminatePolicy()                    # 默认
policy = MaxStepsPolicy(max_steps=20)              # 最大步数
policy = TimeBudgetPolicy(max_time_ms=300000)      # 时间预算
policy = TokenBudgetPolicy(max_total_tokens=100000)# Token 预算
policy = ConsecutiveErrorPolicy(max_consecutive_errors=3)

# 组合策略（OR 语义）
policy = CompositeTerminationPolicy([
    MaxStepsPolicy(max_steps=50),
    TokenBudgetPolicy(max_total_tokens=100000),
])

# 使用
run = Run.create(agent, session, model, termination_policy=policy)
```

### Tool Policies

```python
# ToolSelectionPolicy - 工具执行审批
from quenda.runtime import (
    ToolSelectionPolicy,
    ToolSelectionRequest,
    ToolSelectionDecision,
    AllowAllToolSelectionPolicy,
    DenylistToolSelectionPolicy,
    AllowlistToolSelectionPolicy,
)

policy = DenylistToolSelectionPolicy(
    denied={"run_shell", "python_execution"}
)
policy = AllowlistToolSelectionPolicy(
    allowed={"read_file", "search_text"}
)

# ToolResultProcessingPolicy - 结果处理
from quenda.runtime import (
    ToolResultProcessingPolicy,
    ToolResultEnvelope,
    ProcessedToolResult,
    PassthroughToolResultProcessingPolicy,
    TruncatingToolResultProcessingPolicy,
    LineLimitedToolResultProcessingPolicy,
)

policy = TruncatingToolResultProcessingPolicy(max_chars=4000)
policy = LineLimitedToolResultProcessingPolicy(max_lines=100)
```

---

## 版本兼容性

- Python: 3.12+
- 当前版本: 0.1.0
- 包名: `quenda`
- 许可证: 待定

---

*此 API 参考对应 Quenda v0.1.0，会随框架更新而同步更新。*

---

<div align="right">
  <a href="./09-policies.md">← 上一页</a> ·
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a>
</div>
