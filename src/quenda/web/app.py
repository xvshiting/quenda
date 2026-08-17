"""
FastAPI application for Quenda Web UI.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from quenda.host import AgentHomeManager, find_builtin_agent
from quenda.web.api import agents, models, sessions, system, tools, websocket, workspaces
from quenda.web.services.agent_service import AgentService
from quenda.web.services.session_service import SessionService
from quenda.web.services.workspace_service import WorkspaceService

# Global services (initialized on startup)
workspace_service: WorkspaceService | None = None
agent_service: AgentService | None = None
session_service: SessionService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global workspace_service, agent_service, session_service

    # Initialize services
    home_manager = AgentHomeManager()
    if find_builtin_agent("quenda-code") is not None:
        home_manager.ensure("quenda-code", source="quenda-code")
    quenda_root = home_manager.root
    workspace_service = WorkspaceService(quenda_root / "workspaces.json")
    agent_service = AgentService(manager=home_manager)
    session_service = SessionService(
        quenda_root / "sessions",
        agent_manager=home_manager,
        workspace_service=workspace_service,
    )

    # Store in app state
    app.state.workspace_service = workspace_service
    app.state.agent_service = agent_service
    app.state.session_service = session_service

    yield

    # Cleanup on shutdown
    pass


# Create FastAPI app
app = FastAPI(
    title="Quenda Web UI",
    description="Web interface for managing and using Quenda agents",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


@app.get("/api")
async def api_root():
    """API discovery endpoint."""
    return {
        "name": "Quenda Web UI",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


# Serve static files (for production build)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Serve SPA for all non-API routes."""
        # If requesting a static file that exists, serve it
        file_path = static_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)

        # Otherwise, serve index.html (for client-side routing)
        return FileResponse(static_dir / "index.html")
