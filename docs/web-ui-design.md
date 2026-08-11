# Quenda Web UI 设计文档

## 目标

为 Quenda 提供一个现代化的 Web UI 界面，方便：
- 管理和使用 Agent
- 切换 Workspace
- 查看和恢复历史会话
- 实时交互和工具调用可视化

## 技术栈

### 后端
- **FastAPI** — 现代、高性能的 Python Web 框架
- **WebSocket** — 实时双向通信（agent 执行过程实时推送）
- **Uvicorn** — ASGI 服务器

### 前端
- **React 18** — 现代 React（hooks, concurrent features）
- **TypeScript** — 类型安全
- **TailwindCSS** — 快速样式开发
- **Vite** — 快速构建工具
- **Zustand** — 轻量状态管理
- **React Query** — 数据获取和缓存
- **Monaco Editor** — 代码编辑器（用于编辑 agent 配置）

## 核心功能

### Phase 1: 基础框架
- [ ] FastAPI 后端基础结构
- [ ] React 前端脚手架
- [ ] WebSocket 连接管理
- [ ] 基础 UI 布局

### Phase 2: Agent 管理
- [ ] Agent 列表展示
- [ ] Agent 创建/编辑/删除
- [ ] Agent 配置编辑器（YAML）
- [ ] Agent 模板选择

### Phase 3: Workspace 管理
- [ ] Workspace 列表
- [ ] Workspace 切换
- [ ] Workspace 创建
- [ ] 文件浏览器

### Phase 4: 实时交互
- [ ] 对话界面（类似 ChatGPT）
- [ ] 消息渲染（Markdown + 代码高亮）
- [ ] 工具调用可视化
- [ ] 流式输出支持

### Phase 5: 会话管理
- [ ] 会话列表
- [ ] 会话恢复
- [ ] 会话删除
- [ ] 会话搜索

### Phase 6: 高级功能
- [ ] 执行历史查看
- [ ] Token 使用统计
- [ ] 模型切换
- [ ] 配置导出/导入

## 架构设计

```
┌─────────────────────────────────────────────┐
│                  Frontend                    │
│  (React + TypeScript + TailwindCSS)         │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Agent    │  │Workspace │  │ Session  │ │
│  │ Manager  │  │ Manager  │  │  Chat    │ │
│  └──────────┘  └──────────┘  └──────────┘ │
│         │              │             │      │
│         └──────────────┴─────────────┘      │
│                        │                     │
└────────────────────────┼─────────────────────┘
                         │ HTTP/WebSocket
┌────────────────────────┼─────────────────────┐
│                  Backend                     │
│         (FastAPI + WebSocket)                │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Agent   │  │Workspace │  │ Session  │ │
│  │   API    │  │   API    │  │   API    │ │
│  └──────────┘  └──────────┘  └──────────┘ │
│         │              │             │      │
│         └──────────────┴─────────────┘      │
│                        │                     │
│                  ┌─────┴─────┐              │
│                  │   Quenda  │              │
│                  │   Core    │              │
│                  └───────────┘              │
└─────────────────────────────────────────────┘
```

## API 设计

### REST API

```python
# Agent 管理
GET    /api/agents                    # 列出所有 agent
POST   /api/agents                    # 创建 agent
GET    /api/agents/{id}               # 获取 agent 详情
PUT    /api/agents/{id}               # 更新 agent
DELETE /api/agents/{id}               # 删除 agent

# Workspace 管理
GET    /api/workspaces                # 列出所有 workspace
POST   /api/workspaces                # 创建 workspace
GET    /api/workspaces/{id}           # 获取 workspace 详情
PUT    /api/workspaces/{id}           # 更新 workspace
DELETE /api/workspaces/{id}           # 删除 workspace
GET    /api/workspaces/{id}/files     # 列出文件
GET    /api/workspaces/{id}/files/*   # 读取文件

# Session 管理
GET    /api/sessions                  # 列出所有会话
POST   /api/sessions                  # 创建会话
GET    /api/sessions/{id}             # 获取会话详情
DELETE /api/sessions/{id}             # 删除会话
POST   /api/sessions/{id}/send        # 发送消息
POST   /api/sessions/{id}/run         # 运行 agent（流式）

# 模型和工具
GET    /api/models                    # 列出可用模型
GET    /api/tools                     # 列出可用工具
GET    /api/skills                    # 列出可用 skills
```

### WebSocket API

```python
# WebSocket 连接
WS /ws/sessions/{session_id}          # 实时会话交互

# 消息格式
{
  "type": "user_message" | "agent_message" | "tool_call" | "tool_result" | "error",
  "content": "...",
  "metadata": {...}
}

# 流式消息
{
  "type": "stream_start" | "stream_chunk" | "stream_end",
  "content": "...",
  "delta": "..."
}
```

## 目录结构

```
quenda/
├── src/quenda/
│   ├── web/                    # Web UI 相关代码
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI 应用
│   │   ├── api/                # API 路由
│   │   │   ├── agents.py
│   │   │   ├── workspaces.py
│   │   │   ├── sessions.py
│   │   │   └── websocket.py
│   │   ├── models/             # 数据模型
│   │   │   ├── agent.py
│   │   │   ├── workspace.py
│   │   │   └── session.py
│   │   ├── services/           # 业务逻辑
│   │   │   ├── agent_service.py
│   │   │   ├── workspace_service.py
│   │   │   └── session_service.py
│   │   └── utils/              # 工具函数
│   │       ├── file_utils.py
│   │       └── stream_utils.py
│   └── ...
├── web/                        # 前端代码
│   ├── src/
│   │   ├── components/         # React 组件
│   │   │   ├── AgentManager/
│   │   │   ├── WorkspaceManager/
│   │   │   ├── SessionChat/
│   │   │   └── common/
│   │   ├── hooks/              # 自定义 hooks
│   │   ├── stores/             # Zustand stores
│   │   ├── api/                # API 客户端
│   │   ├── utils/              # 工具函数
│   │   ├── types/              # TypeScript 类型
│   │   └── App.tsx
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── package.json
├── tests/
│   └── web/                    # Web UI 测试
│       ├── test_api.py
│       └── test_websocket.py
└── docs/
    └── web-ui-design.md        # 本文档
```

## 启动方式

```bash
# 开发模式
quenda web --dev

# 生产模式
quenda web --host 0.0.0.0 --port 8000

# 或者
python -m quenda.web.app
```

## 安全考虑

1. **认证**：可选的 API Key 认证
2. **CORS**：配置允许的域名
3. **文件访问**：限制在工作空间内
4. **命令执行**：需要用户确认（通过 UI）

## 性能优化

1. **前端**：
   - 代码分割（React.lazy）
   - 虚拟滚动（长列表）
   - WebSocket 压缩

2. **后端**：
   - 异步 I/O
   - 连接池
   - 缓存策略

## 后续扩展

1. **多用户支持**：用户认证和隔离
2. **插件系统**：自定义工具和 UI 扩展
3. **协作功能**：多人协作编辑
4. **部署支持**：Docker、Kubernetes 部署方案
