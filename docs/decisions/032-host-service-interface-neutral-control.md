# ADR-032: Host Service as Interface-neutral Control Interface

## 状态

提议 (2026-07-27)

## 背景

Quenda 当前只有 CLI 接口，但计划支持 Web UI 和其他接口。为了避免在每个接口中重复实现 Agent 运行逻辑，需要一个 Interface-neutral 的控制接口。

### 当前问题

1. **CLI 拥有过多逻辑**：运行循环、交互暂停、权限处理等都在 CLI 层
2. **难以扩展新接口**：Web UI 或 Server 需要复制 CLI 的逻辑
3. **测试困难**：无法独立于 CLI 测试会话控制逻辑
4. **架构不清晰**：Host 与 Interface 的边界模糊

### 期望场景

1. CLI、Web、Server 都使用同一个控制接口
2. 新接口可以快速实现，只需处理 UI 层面的问题
3. 控制逻辑集中在一处，易于测试和维护
4. 明确的分层边界：Core → Host → Service → Interface

## 决策

创建 **HostService** 作为 Interface-neutral 的控制接口。

### 核心抽象

```text
                    ┌──────────────────┐
                    │   Quenda Web     │
                    │ Browser Client   │
                    └────────┬─────────┘
                             │ HTTP + SSE
                    ┌────────▼─────────┐
                    │  quenda-server   │
                    │ Transport Adapter│
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   HostService    │
                    │ Interface-neutral│
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │ Host → Runtime → Kernel     │
              └─────────────────────────────┘

CLI ────────────────────────→ HostService
```

### HostService 接口

```python
class HostService:
    """Interface-neutral agent control service."""

    # Session Management
    def create_session(request: CreateSessionRequest) -> SessionInfo
    def get_session(session_id: str) -> SessionInfo | None
    def list_sessions(workspace_id: str) -> list[SessionInfo]

    # Run Management
    async def start_run(request: StartRunRequest) -> RunHandle
    async def stream_events(run_id: str) -> AsyncIterator[EventEnvelope]
    def get_run(run_id: str) -> RunHandle | None

    # Interaction Handling
    async def respond_to_interaction(request: InteractionResponseRequest) -> None

    # Permission Handling
    async def decide_permission(request: PermissionDecisionRequest) -> None

    # Interrupt Handling
    async def interrupt_run(request: InterruptRequest) -> None

    # Context Management
    def get_context(session_id: str) -> ContextInfo

    # Memory Management
    async def search_memory(request: MemorySearchRequest) -> MemorySearchResult
    async def get_memory_file(path: str) -> MemoryFile | None
```

### 结构化 DTO

所有请求和响应都使用结构化 DTO，而不是原始参数：

- **Session**: `CreateSessionRequest`, `SessionInfo`, `SessionList`
- **Run**: `StartRunRequest`, `RunHandle`, `RunStatus`
- **Event**: `EventEnvelope`
- **Interaction**: `InteractionResponseRequest`
- **Permission**: `PermissionDecisionRequest`
- **Interrupt**: `InterruptRequest`
- **Context**: `ContextSource`, `ContextInfo`
- **Memory**: `MemorySearchRequest`, `MemorySearchResult`, `MemoryFile`
- **Request**: `RequestContext` (for future multi-user)

### 这些类型不应该出现

以下类型属于 Server Adapter，不应该出现在 HostService:

- HTTP 状态码
- Cookie
- WebSocket
- 浏览器 Origin
- ASGI Request
- JSON Response

## 理据

### 为什么创建新的 HostService 而不是扩展现有的 runner.py

1. **runner.py 职责不同**：runner.py 负责一次性设置和执行，不是会话控制
2. **清晰的接口边界**：HostService 提供明确的公共 API
3. **异步优先**：HostService 设计为异步，便于 Server 使用
4. **状态管理**：HostService 管理活跃会话和运行，runner.py 不负责

### 为什么使用结构化 DTO

1. **类型安全**：明确的请求和响应类型
2. **文档化**：类型定义即文档
3. **扩展性**：添加新字段不影响现有接口
4. **序列化友好**：便于转换为 JSON 或其他格式

### 为什么不包括 HTTP 相关类型

1. **Interface-neutral**：CLI 不需要 HTTP，Web 需要
2. **关注点分离**：HostService 关心控制逻辑，Server 关心传输
3. **可测试性**：不依赖 ASGI 或 HTTP 框架

### 为什么需要 RequestContext

虽然当前只有本地 CLI，但 Request Context 为未来的多用户场景预留了扩展点：

```python
@dataclass
class RequestContext:
    user: User | None = None
    client_type: str = "cli"  # "cli", "web", "api"
    request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

## 实现

### Phase 1: 提取 HostService

| 文件 | 变更 |
|------|------|
| `src/quenda/host/service_types.py` | 新建 DTO 类型 |
| `src/quenda/host/service.py` | 新建 HostService |
| `src/quenda/host/cli_adapter.py` | 新建 CLI adapter |
| `src/quenda/host/__init__.py` | 导出新类型 |

### Phase 2: 重构 CLI

| 文件 | 变更 |
|------|------|
| `src/quenda/cli.py` | 改为使用 HostService（可选） |

当前保持向后兼容，CLI 可以继续使用现有的 `run_agent_once` 和 `setup_agent`。

### Phase 3: 实现 Server

| 文件 | 变更 |
|------|------|
| `packages/quenda-server/` | 新建包 |
| HTTP 路由 | 实现 REST API |
| SSE 事件流 | 实现事件推送 |

### Phase 4: 实现 Web UI

| 文件 | 变更 |
|------|------|
| `packages/quenda-web/` | 新建包 |
| Web UI | 实现浏览器界面 |

## 后果

### 正面

- CLI 和 Server 共享同一套控制逻辑
- 新接口实现变得简单
- 清晰的分层边界
- 控制逻辑集中，易于测试
- 为未来多用户场景预留扩展点

### 负面

- 增加了一个抽象层
- 需要更新现有代码
- 增加了类型定义

### 风险

- 如果 HostService 设计不当，可能成为瓶颈
- 如果 DTO 设计过于复杂，可能影响易用性

### 缓解

- 保持 HostService 接口简洁
- DTO 只包含必要字段
- 提供良好的默认值和文档
- 保持向后兼容，逐步迁移

## 与现有 ADR 的关系

### 一致性

- **ADR-003**: Host 不等于某个具体 Web Server ✅ HostService 是 Interface-neutral
- **ADR-004**: 本地模式和 Server 模式共享状态模型 ✅ 使用相同的 DTO
- **ADR-014**: Interface Layer Extensibility ✅ CLI 和 Web 都是 Interface Adapter
- **ADR-019**: Strategy Hooks Over Rich UI ✅ UI 只是 Interface，不驱动架构

### 扩展

- **ADR-026**: Two-path model (StableHostBinding + RunContextSnapshot) ✅ HostService 使用相同的 binding
- **ADR-027**: Skill activation within Run ✅ HostService 支持 skill activation handler

## 未来扩展

### 短期

1. 完善 HostService 实现（interaction/permission 等待机制）
2. 创建 quenda-server 包
3. 创建 quenda-web 包

### 中期

1. 多用户认证
2. 数据库存储
3. 远程 Workspace

### 长期

1. 多 Agent 编排
2. 企业级部署
3. 云服务

## 示例用法

### CLI 使用 HostService

```python
from quenda.host import HostService, CreateSessionRequest, StartRunRequest

service = HostService()

# Create session
session = service.create_session(CreateSessionRequest(
    agent_path=Path("agents/quenda-code"),
    workspace_path=Path.cwd(),
))

# Start run
handle = await service.start_run(StartRunRequest(
    session_id=session.id,
    message="Hello",
))

# Stream events
async for envelope in service.stream_events(handle.id):
    print(envelope.event)
```

### Server 使用 HostService

```python
# In quenda-server
from quenda.host import HostService

service = HostService()

@app.post("/v1/sessions")
async def create_session(request: CreateSessionRequest):
    return service.create_session(request)

@app.post("/v1/sessions/{session_id}/runs")
async def start_run(session_id: str, request: StartRunRequest):
    request.session_id = session_id
    handle = await service.start_run(request)
    return {"run_id": handle.id, "status": handle.status}

@app.get("/v1/runs/{run_id}/events")
async def stream_events(run_id: str):
    async for envelope in service.stream_events(run_id):
        yield f"event: {envelope.event.__class__.__name__}\n"
        yield f"data: {envelope.event.to_json()}\n\n"
```

## 结论

创建 HostService 作为 Interface-neutral 的控制接口，使 CLI、Server 和未来其他接口都能共享同一套 Agent 控制逻辑。这符合 Quenda 的分层架构原则，并为未来的多接口和多用户场景打下基础。
