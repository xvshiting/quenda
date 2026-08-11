# Quenda Web UI

A modern web interface for managing and using Quenda agents.

## Quick Start

### Start the server

```bash
# Development mode (with auto-reload)
quenda web --dev

# Production mode
quenda web --host 0.0.0.0 --port 8000
```

### Access the UI

Open your browser and navigate to:
- Development: http://localhost:8000
- Production: http://your-host:8000

## Features

### Agent Management
- ✅ List all agents
- ✅ Create new agents
- ✅ Edit agent configurations
- ✅ Delete agents
- ✅ Use agent templates

### Workspace Management
- ✅ List workspaces
- ✅ Create new workspaces
- ✅ Switch between workspaces
- ✅ Browse workspace files

### Session Management
- ✅ List all sessions
- ✅ Create new sessions
- ✅ Resume sessions
- ✅ Delete sessions
- ✅ View token usage

### Real-time Interaction
- ✅ Chat interface
- ✅ Markdown rendering
- ✅ Code syntax highlighting
- 🚧 WebSocket streaming (in progress)
- 🚧 Tool call visualization (in progress)

## Architecture

```
Frontend (React + TypeScript + TailwindCSS)
    ↓ HTTP/WebSocket
Backend (FastAPI + Python)
    ↓
Quenda Core (Agent, Session, Tools)
```

### Tech Stack

**Frontend**:
- React 18 (hooks, concurrent features)
- TypeScript (type safety)
- TailwindCSS (styling)
- Vite (build tool)
- Zustand (state management)
- React Query (data fetching)
- Monaco Editor (code editing)
- React Markdown (message rendering)

**Backend**:
- FastAPI (web framework)
- WebSocket (real-time communication)
- Uvicorn (ASGI server)

## API Documentation

### REST API

Access the interactive API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Key Endpoints

#### Agents
- `GET /api/agents` - List all agents
- `POST /api/agents` - Create a new agent
- `GET /api/agents/{id}` - Get agent details
- `PUT /api/agents/{id}` - Update agent
- `DELETE /api/agents/{id}` - Delete agent

#### Workspaces
- `GET /api/workspaces` - List all workspaces
- `POST /api/workspaces` - Create a new workspace
- `GET /api/workspaces/{id}` - Get workspace details
- `GET /api/workspaces/{id}/files` - List files in workspace

#### Sessions
- `GET /api/sessions` - List all sessions
- `POST /api/sessions` - Create a new session
- `GET /api/sessions/{id}` - Get session details
- `GET /api/sessions/{id}/messages` - Get session messages
- `POST /api/sessions/{id}/send` - Send a message

### WebSocket

Connect to: `ws://localhost:8000/ws/sessions/{session_id}`

Message format:
```json
{
  "type": "user_message" | "agent_message" | "tool_call" | "tool_result" | "stream_chunk" | "error",
  "content": "...",
  "metadata": {}
}
```

## Development

### Frontend Development

```bash
cd web
npm install
npm run dev
```

The frontend dev server runs at http://localhost:5173 with proxy to the backend.

### Backend Development

```bash
# From quenda root
quenda web --dev
```

### Build for Production

```bash
# Build frontend
cd web
npm run build

# The build output goes to web/dist/
# The FastAPI app serves these static files in production mode
```

## Configuration

### Environment Variables

**Frontend** (`.env` in `web/` directory):
- `VITE_API_URL` - Backend API URL (default: same origin)

**Backend**:
- Configuration is handled through Quenda's standard config system

## Security

### Current Implementation
- CORS enabled for development (localhost:5173, localhost:3000)
- File access restricted to workspace boundaries
- No authentication (for development)

### Production Considerations
- Add authentication (API keys, OAuth, etc.)
- Restrict CORS to your domain
- Add rate limiting
- Use HTTPS
- Add input validation and sanitization

## Troubleshooting

### Port already in use
```bash
# Use a different port
quenda web --port 3000
```

### Frontend not connecting to backend
- Check if backend is running
- Check CORS configuration
- Check Vite proxy settings in `vite.config.ts`

### Build errors
```bash
# Clean and reinstall
cd web
rm -rf node_modules package-lock.json
npm install
```

## Future Roadmap

### Phase 1 (Current)
- ✅ Basic UI structure
- ✅ Agent/Workspace/Session management
- 🚧 Real-time WebSocket communication
- 🚧 Tool call visualization

### Phase 2
- ⬜ Execution history viewer
- ⬜ Token usage analytics
- ⬜ Model switching
- ⬜ Config import/export

### Phase 3
- ⬜ Multi-user support
- ⬜ Plugin system
- ⬜ Collaboration features
- ⬜ Docker deployment

## Contributing

Contributions are welcome! Please read the main contributing guide.

## License

MIT
