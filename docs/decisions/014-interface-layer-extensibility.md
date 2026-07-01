# ADR-014: Interface Layer Extensibility

## 状态

提议 (2026-06-25)

## 背景

当前 Kora 的 Interface 层（`src/kora/interface/`）实现了终端渲染、REPL 交互、状态栏、活动指示器等功能，但大部分实现是硬编码的：

### 当前硬编码内容

| 组件 | 位置 | 硬编码内容 |
|-----|------|-----------|
| 状态栏文本 | `status.py` | `"🤖 mode: {mode} │ [/ for commands]"` |
| 活动指示器 | `activity.py` | spinner 动画帧、消息格式 |
| 欢迎消息 | `cli.py` | `"🤖 Kora Code Agent\n   Workspace: ..."` |
| 事件处理循环 | `cli.py` | indicator + renderer 协作逻辑 |
| 图标和模板 | 多处 | `"✓"`, `"❌"`, `"✅"` 等 |

### 问题

1. **用户无法定制界面风格**：比如使用不同的图标、颜色、动画
2. **无法适配不同终端**：某些终端不支持 emoji 或 Unicode
3. **无法实现静默模式**：CI/CD 场景需要最小化输出
4. **事件处理逻辑耦合**：CLI 层硬编码了 indicator 和 renderer 的协作
5. **不符合框架设计原则**：框架应该提供机制，用户定制策略

### 用户期望的场景

1. **自定义状态栏**：显示项目名、git branch、token 使用量等
2. **自定义动画**：使用不同的 spinner 风格或进度条
3. **静默模式**：CI/CD 环境只输出必要信息
4. **品牌定制**：企业用户希望替换 logo 和配色
5. **可观测性集成**：将事件发送到外部监控系统

## 决策

采用 **Protocol + 默认实现 + 配置注入** 模型，将 Interface 层的硬编码部分抽象为可替换的组件。

### 核心抽象

```
┌─────────────────────────────────────────────────────────┐
│                    InterfaceTheme                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ StatusProvider│  │ Indicator  │  │ WelcomeProvider │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
│                                                          │
│  ┌─────────────────┐  ┌─────────────────────────────┐   │
│  │ ConsoleRenderer │  │ EventHandler (Protocol)     │   │
│  └─────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 1. InterfaceTheme

统一的主题配置容器，包含所有可定制参数：

```python
# src/kora/interface/theme.py

@dataclass
class InterfaceTheme:
    """
    Interface 层的主题配置。

    包含所有可定制的视觉元素和行为。
    """

    # === 图标 ===
    success_icon: str = "✓"
    error_icon: str = "❌"
    agent_icon: str = "🤖"
    thinking_icon: str = "💭"
    complete_icon: str = "✅"
    interrupt_icon: str = "⚠"

    # === 分隔符 ===
    status_separator: str = " │ "

    # === 状态栏模板 ===
    status_idle_template: str = " {agent_icon} mode: {mode}{sep}[/ for commands] "
    status_running_template: str = " {frame} [ESC to interrupt] "
    status_interrupted_template: str = " {interrupt_icon} Interrupted "
    status_error_template: str = " {error_icon} Error │ {message} "

    # === 活动指示器 ===
    spinner_frames: tuple[str, ...] = (
        "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"
    )
    spinner_interval: float = 0.08  # 秒

    # === 欢迎消息模板 ===
    welcome_template: str = """
{agent_icon} {agent_name}
   Workspace: {workspace_id}
   Session: {session_id}
   Model: {provider}/{model}
   Workspace path: {workspace_path}

{instructions}
"""

    # === 完成消息模板 ===
    complete_template: str = "\n\n{complete_icon} Done in {steps} steps{duration}"
    complete_duration_template: str = " ({duration_ms}ms)"
    complete_duration_seconds_template: str = " ({duration_s:.1f}s)"

    # === 工具阶段映射 ===
    tool_phases: dict[str, str] = field(default_factory=lambda: {
        "list_files": "reading",
        "read_file": "reading",
        "search_text": "searching",
        "write_file": "editing",
        "apply_patch": "editing",
        "run_shell": "executing",
        "python_execution": "executing",
        "http_request": "network",
        "web_fetch": "network",
        "web_search": "searching",
    })

    phase_labels: dict[str, str] = field(default_factory=lambda: {
        "reading": "📖 Reading",
        "searching": "🔍 Searching",
        "editing": "✏️ Editing",
        "executing": "⚡ Running",
        "network": "🌐 Fetching",
    })

    # === 错误显示 ===
    max_error_lines: int = 5
    max_message_length: int = 40

    # === 行为开关 ===
    show_duration: bool = True
    show_esc_hint: bool = True
    esc_hint_interval: int = 60  # 每 N 帧显示一次

    @classmethod
    def minimal(cls) -> InterfaceTheme:
        """最小主题：适合 CI/CD 环境"""
        return cls(
            agent_icon="[Kora]",
            success_icon="[OK]",
            error_icon="[ERR]",
            complete_icon="[DONE]",
            interrupt_icon="[INT]",
            spinner_frames=("|", "/", "-", "\\"),
            welcome_template="{agent_name} | {workspace_id}\n",
            show_esc_hint=False,
        )

    @classmethod
    def ascii(cls) -> InterfaceTheme:
        """ASCII 主题：适合不支持 Unicode 的终端"""
        return cls(
            agent_icon="[Kora]",
            success_icon="[+]",
            error_icon="[!]",
            complete_icon="[OK]",
            interrupt_icon="[!]",
            spinner_frames=(".", "o", "O", "0", "O", "o"),
            thinking_icon="[...]",
        )
```

### 2. StatusProvider Protocol

状态栏内容提供者：

```python
# src/kora/interface/status.py

@dataclass
class StatusContext:
    """状态栏上下文信息"""
    mode: str
    model: str
    provider: str
    workspace_id: str
    session_id: str
    current_tool: str | None = None
    tool_summary: str | None = None
    step_count: int = 0
    token_usage: dict | None = None  # 未来扩展


class StatusProvider(Protocol):
    """状态栏内容提供者协议"""

    def get_idle_text(self, context: StatusContext) -> str:
        """空闲状态文本"""
        ...

    def get_running_text(
        self,
        context: StatusContext,
        frame: str,
    ) -> str:
        """运行中状态文本"""
        ...

    def get_interrupted_text(self, context: StatusContext) -> str:
        """中断状态文本"""
        ...

    def get_error_text(self, context: StatusContext, error: str) -> str:
        """错误状态文本"""
        ...


class DefaultStatusProvider:
    """默认状态栏提供者"""

    def __init__(self, theme: InterfaceTheme | None = None):
        self.theme = theme or InterfaceTheme()

    def get_idle_text(self, context: StatusContext) -> str:
        return self.theme.status_idle_template.format(
            agent_icon=self.theme.agent_icon,
            mode=context.mode,
            sep=self.theme.status_separator,
        )

    def get_running_text(self, context: StatusContext, frame: str) -> str:
        return self.theme.status_running_template.format(frame=frame)

    def get_interrupted_text(self, context: StatusContext) -> str:
        return self.theme.status_interrupted_template.format(
            interrupt_icon=self.theme.interrupt_icon,
        )

    def get_error_text(self, context: StatusContext, error: str) -> str:
        message = error[:self.theme.max_message_length]
        return self.theme.status_error_template.format(
            error_icon=self.theme.error_icon,
            message=message,
        )
```

### 3. ActivityIndicator Protocol

活动指示器抽象：

```python
# src/kora/interface/activity.py

class ActivityIndicator(Protocol):
    """活动指示器协议"""

    def start(self) -> None:
        """开始显示"""
        ...

    def stop(self) -> None:
        """停止显示"""
        ...

    def update(self, message: str) -> None:
        """更新消息"""
        ...

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        ...


class SpinnerIndicator:
    """旋转动画指示器（默认实现）"""

    def __init__(
        self,
        theme: InterfaceTheme | None = None,
        stream: TextIO | None = None,
    ):
        self.theme = theme or InterfaceTheme()
        self.stream = stream or sys.stdout
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._message = "Thinking..."

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def update(self, message: str) -> None: ...


class SilentIndicator:
    """静默指示器（无输出）"""

    def start(self) -> None: pass
    def stop(self) -> None: pass
    def update(self, message: str) -> None: pass

    @property
    def is_running(self) -> bool:
        return False


class ProgressIndicator:
    """进度条指示器（未来扩展）"""

    def __init__(self, total: int, theme: InterfaceTheme | None = None):
        self.total = total
        self.current = 0
        self.theme = theme or InterfaceTheme()

    def advance(self, amount: int = 1) -> None:
        self.current += amount
```

### 4. WelcomeProvider Protocol

启动消息提供者：

```python
# src/kora/interface/welcome.py

@dataclass
class WelcomeContext:
    """欢迎消息上下文"""
    agent_name: str
    workspace_id: str
    workspace_path: Path
    session_id: str
    provider: str
    model: str
    instructions: str


class WelcomeProvider(Protocol):
    """欢迎消息提供者协议"""

    def render(self, context: WelcomeContext) -> str:
        """渲染欢迎消息"""
        ...


class DefaultWelcomeProvider:
    """默认欢迎消息提供者"""

    def __init__(self, theme: InterfaceTheme | None = None):
        self.theme = theme or InterfaceTheme()

    def render(self, context: WelcomeContext) -> str:
        return self.theme.welcome_template.format(
            agent_icon=self.theme.agent_icon,
            agent_name=context.agent_name,
            workspace_id=context.workspace_id,
            workspace_path=context.workspace_path,
            session_id=context.session_id,
            provider=context.provider,
            model=context.model,
            instructions=context.instructions,
        )
```

### 5. EventHandler Protocol

事件处理流水线抽象：

```python
# src/kora/interface/events.py

class EventHandler(Protocol):
    """
    事件处理器协议。

    定义如何处理 Runtime 发出的事件。
    """

    def on_run_started(self, event: RunStarted) -> None:
        """Run 开始"""
        ...

    def on_model_responded(self, event: ModelResponded) -> None:
        """Model 响应"""
        ...

    def on_tool_executed(self, event: ToolExecuted) -> None:
        """工具执行完成"""
        ...

    def on_run_completed(self, event: RunCompleted) -> None:
        """Run 完成"""
        ...

    def on_run_interrupted(self, event: RunInterrupted) -> None:
        """Run 中断"""
        ...

    def on_error(self, event: ErrorOccurred) -> None:
        """错误发生"""
        ...


class StreamingEventHandler:
    """
    流式事件处理器（默认实现）。

    边接收事件边渲染输出。
    """

    def __init__(
        self,
        renderer: ConsoleRenderer,
        indicator: ActivityIndicator,
        theme: InterfaceTheme | None = None,
        output: TextIO | None = None,
    ):
        self.renderer = renderer
        self.indicator = indicator
        self.theme = theme or InterfaceTheme()
        self.output = output or sys.stdout

    def on_run_started(self, event: RunStarted) -> None:
        self.indicator.start()

    def on_model_responded(self, event: ModelResponded) -> None:
        self.indicator.stop()
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)
        if event.tool_calls:
            self.indicator.start()

    def on_tool_executed(self, event: ToolExecuted) -> None:
        self.indicator.stop()
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)
        self.indicator.start()

    def on_run_completed(self, event: RunCompleted) -> None:
        self.indicator.stop()
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)


class BatchEventHandler:
    """
    批量事件处理器。

    收集所有事件后一次性处理，适合需要完整上下文的场景。
    """

    def __init__(self, renderer: ConsoleRenderer, theme: InterfaceTheme | None = None):
        self.renderer = renderer
        self.theme = theme or InterfaceTheme()
        self.events: list[AnyEvent] = []

    def on_run_started(self, event: RunStarted) -> None:
        self.events.append(event)

    # ... 其他方法收集事件

    def render_all(self) -> str:
        """渲染所有收集的事件"""
        lines = []
        for event in self.events:
            rendered = self.renderer.render(event)
            if rendered:
                lines.append(rendered)
        return "\n".join(lines)


class CollectingEventHandler:
    """
    收集事件但不输出，适合可观测性集成。
    """

    def __init__(self):
        self.events: list[AnyEvent] = []

    def on_run_started(self, event: RunStarted) -> None:
        self.events.append(event)

    # ... 其他方法收集事件

    def get_events(self) -> list[AnyEvent]:
        return self.events.copy()
```

### 6. 更新 StatusBarManager

使用 StatusProvider 替代硬编码：

```python
# src/kora/interface/status.py

@dataclass
class StatusBarManager:
    """
    Tracks REPL status text for the bottom toolbar.
    """

    stream: TextIO | None = None
    mode: str = "chat"
    state: StatusBarState = StatusBarState.IDLE
    message: str = ""

    # 新增：可替换的状态提供者
    provider: StatusProvider = field(default_factory=DefaultStatusProvider)
    context: StatusContext = field(default_factory=StatusContext)

    def get_text(self) -> str:
        """Get status bar text (for bottom_toolbar callback)."""
        if self.state == StatusBarState.RUNNING:
            return self.provider.get_running_text(
                self.context,
                self._current_frame(),
            )
        if self.state == StatusBarState.INTERRUPTED:
            return self.provider.get_interrupted_text(self.context)
        if self.state == StatusBarState.ERROR:
            return self.provider.get_error_text(self.context, self.message)
        return self.provider.get_idle_text(self.context)
```

### 7. 更新 ConsoleRenderer

使用 InterfaceTheme：

```python
# src/kora/interface/console.py

class ConsoleRenderer:
    """
    Renders Runtime events to console output.
    """

    def __init__(
        self,
        theme: InterfaceTheme | None = None,
        *,
        verbose: bool = False,
    ) -> None:
        self.theme = theme or InterfaceTheme()
        self.verbose = verbose
        self._step_count = 0

    def _render_tool_executed(self, event: ToolExecuted) -> str:
        self._step_count += 1

        # 使用主题中的图标
        icon = self.theme.error_icon if event.is_error else self.theme.success_icon

        # 使用 _summary 或阶段标签
        summary = event.arguments.get("_summary", "")
        if not summary:
            phase = self.theme.tool_phases.get(event.tool_name, "executing")
            phase_label = self.theme.phase_labels.get(phase, "Running")
            summary = f"{phase_label}..."

        line = f"  {icon} {summary}"

        # 时长
        if self.theme.show_duration and event.duration_ms > 0:
            if event.duration_ms < 1000:
                line += f" ({event.duration_ms}ms)"
            else:
                line += f" ({event.duration_ms / 1000:.1f}s)"

        return line

    def _render_run_completed(self, event: RunCompleted) -> str:
        duration_str = ""
        if self.theme.show_duration and event.duration_ms > 0:
            if event.duration_ms < 1000:
                duration_str = self.theme.complete_duration_template.format(
                    duration_ms=event.duration_ms,
                )
            else:
                duration_str = self.theme.complete_duration_seconds_template.format(
                    duration_s=event.duration_ms / 1000,
                )

        return self.theme.complete_template.format(
            complete_icon=self.theme.complete_icon,
            steps=event.total_steps,
            duration=duration_str,
        )
```

### 8. CLI 层简化

CLI 层使用组合而非硬编码：

```python
# src/kora/cli.py (简化后)

def run_repl(
    agent_path: Path,
    workspace: Path,
    *,
    provider: str | None = None,
    model: str | None = None,
    session_id: str | None = None,
    theme: InterfaceTheme | None = None,
) -> int:
    """Run an agent in interactive REPL mode."""
    theme = theme or InterfaceTheme()

    # Setup agent
    setup = setup_agent(agent_path, workspace, provider=provider, model=model)
    if setup is None:
        print(f"Error: Failed to setup agent", file=sys.stderr)
        return 1

    # 创建可配置的组件
    renderer = ConsoleRenderer(theme=theme, verbose=False)
    indicator = SpinnerIndicator(theme=theme)
    status_provider = DefaultStatusProvider(theme)
    welcome_provider = DefaultWelcomeProvider(theme)

    # 欢迎消息
    welcome_ctx = WelcomeContext(
        agent_name="Kora Code Agent",
        workspace_id=setup.workspace_id,
        workspace_path=workspace,
        session_id=setup.session.id,
        provider=setup.provider_name,
        model=setup.model_name,
        instructions="Type your message and press Enter. Type '/' to see commands.",
    )
    print(welcome_provider.render(welcome_ctx))

    # 创建事件处理器
    event_handler = StreamingEventHandler(
        renderer=renderer,
        indicator=indicator,
        theme=theme,
    )

    # REPL 循环
    while True:
        user_input = get_input("> ")
        if user_input.startswith("/"):
            # 命令处理
            pass
        else:
            # 发送消息，使用事件处理器
            session.send_sync(user_input, on_event=event_handler.on_event)
```

## 理据

### 为什么用 Protocol + 默认实现

1. **渐进式定制**：用户可以只替换想改的部分
2. **类型安全**：Protocol 提供明确的接口契约
3. **默认可用**：开箱即用，无需任何配置
4. **可测试**：可以注入 mock 实现进行测试

### 为什么用 InterfaceTheme 而不是多个配置对象

1. **统一管理**：所有视觉配置在一处
2. **易于序列化**：可以保存为 YAML/JSON
3. **便于分享**：用户可以分享主题配置
4. **工厂方法**：提供 `minimal()`, `ascii()` 等预设

### 为什么 EventHandler 是 Protocol 而不是类

1. **灵活性**：用户可以实现自己的处理逻辑
2. **可组合**：可以链式组合多个处理器
3. **可观测性**：可以创建发送到外部系统的处理器

### 为什么不完全使用 Rich/Textual

1. **依赖轻量**：当前实现只需标准库 + prompt_toolkit
2. **简单场景优先**：大多数用户只需要基本定制
3. **可选集成**：用户可以自己在 EventHandler 中使用 Rich

## 实现

### Phase 1: 基础抽象

| 文件 | 变更 |
|------|------|
| `src/kora/interface/theme.py` | 新建 InterfaceTheme |
| `src/kora/interface/status.py` | 添加 StatusProvider Protocol + DefaultStatusProvider |
| `src/kora/interface/activity.py` | 添加 ActivityIndicator Protocol + SilentIndicator |
| `src/kora/interface/__init__.py` | 导出新类型 |

### Phase 2: 渲染器更新

| 文件 | 变更 |
|------|------|
| `src/kora/interface/console.py` | 使用 InterfaceTheme |
| `src/kora/interface/welcome.py` | 新建 WelcomeProvider |
| `src/kora/interface/status.py` | StatusBarManager 使用 StatusProvider |

### Phase 3: 事件处理器

| 文件 | 变更 |
|------|------|
| `src/kora/interface/events.py` | 新建 EventHandler Protocol + 默认实现 |
| `src/kora/cli.py` | 使用 EventHandler 替代硬编码循环 |

### Phase 4: 配置集成

| 文件 | 变更 |
|------|------|
| `src/kora/host/config.py` | 支持从配置加载主题 |
| `agents/kora-code/config.yaml` | 添加主题配置示例 |

### 配置文件示例

```yaml
# config.yaml
interface:
  theme: "default"  # 或 "minimal", "ascii", 或自定义

  # 或内联配置
  theme_config:
    agent_icon: "🤖"
    success_icon: "✓"
    spinner_frames: ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    show_duration: true
```

## 后果

### 正面

- 用户可以定制界面风格和行为
- 支持 CI/CD 静默模式
- 支持无 Unicode 终端
- CLI 层代码更简洁
- 为未来可观测性集成打下基础
- 可测试性提高

### 负面

- 增加了抽象层
- 需要更新现有代码
- 文档需要扩展

### 风险

- 过度抽象可能导致复杂性增加
- 需要确保默认行为与现有体验一致

### 缓解

- 提供预设主题（default, minimal, ascii）
- 保持向后兼容：不传 theme 时使用默认行为
- 分阶段实现，每阶段验证体验

## 未来扩展

### 短期

1. **更多预设主题**：提供 dark/light/high-contrast 等
2. **主题配置文件**：支持 `~/.kora/themes/` 目录
3. **CLI 参数**：`kora code --theme minimal`

### 中期

1. **Token 使用量显示**：在状态栏显示 token 统计
2. **Git 信息显示**：显示当前 branch 和 status
3. **自定义信息提供者**：允许用户注入额外的上下文信息

### 长期

1. **Rich/Textual 集成**：可选的完整 TUI
2. **Web Interface**：基于同样 Protocol 的 Web UI
3. **IDE 集成**：VSCode/JetBrains 插件
