"""
CLI command to start the Web UI server.
"""

import asyncio
import click
import uvicorn
from pathlib import Path


@click.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--dev", is_flag=True, help="Run in development mode with auto-reload")
@click.option("--no-frontend", is_flag=True, help="Don't serve frontend (useful for development)")
def web(host: str, port: int, dev: bool, no_frontend: bool):
    """
    Start the Quenda Web UI server.
    
    Examples:
        quenda web                      # Start on http://localhost:8000
        quenda web --dev                # Development mode with auto-reload
        quenda web --host 0.0.0.0       # Listen on all interfaces
        quenda web --port 3000          # Use different port
    """
    if dev:
        # Development mode with auto-reload
        uvicorn.run(
            "quenda.web.app:app",
            host=host,
            port=port,
            reload=True,
            reload_dirs=[str(Path(__file__).parent)],
        )
    else:
        # Production mode
        uvicorn.run(
            "quenda.web.app:app",
            host=host,
            port=port,
        )


if __name__ == "__main__":
    web()
