"""
WebSocket API for real-time session interaction.
"""

import asyncio
import json
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel

from quenda.web.services.session_service import SessionService


router = APIRouter()


class WebSocketMessage(BaseModel):
    """WebSocket message format."""
    type: str  # "user_message", "tool_call", "tool_result", "stream_chunk", "error"
    content: Any
    metadata: Dict[str, Any] = {}


class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
    
    def disconnect(self, session_id: str):
        """Remove a WebSocket connection."""
        self.active_connections.pop(session_id, None)
    
    async def send_message(self, session_id: str, message: WebSocketMessage):
        """Send a message to a specific session."""
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_json(message.model_dump())
    
    async def broadcast(self, message: WebSocketMessage):
        """Broadcast a message to all connections."""
        for websocket in self.active_connections.values():
            await websocket.send_json(message.model_dump())


manager = ConnectionManager()


@router.websocket("/sessions/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    # service: SessionService = Depends(get_session_service)  # Can't use Depends with WebSocket
):
    """
    WebSocket endpoint for real-time session interaction.
    
    Message types:
    - user_message: User sends a message
    - agent_message: Agent responds
    - tool_call: Agent calls a tool
    - tool_result: Tool returns a result
    - stream_start: Streaming starts
    - stream_chunk: Streaming chunk
    - stream_end: Streaming ends
    - error: Error occurred
    """
    await manager.connect(session_id, websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "user_message":
                # Process user message
                user_content = message.get("content", "")
                
                # TODO: Get session service from app state and run agent
                # For now, send a placeholder response
                await manager.send_message(
                    session_id,
                    WebSocketMessage(
                        type="stream_start",
                        content="",
                        metadata={"message_id": "msg_123"}
                    )
                )
                
                # Simulate streaming
                for i in range(3):
                    await asyncio.sleep(0.5)
                    await manager.send_message(
                        session_id,
                        WebSocketMessage(
                            type="stream_chunk",
                            content=f"Chunk {i+1}",
                            metadata={"delta": f"Chunk {i+1} "}
                        )
                    )
                
                await manager.send_message(
                    session_id,
                    WebSocketMessage(
                        type="stream_end",
                        content="Full response here",
                        metadata={}
                    )
                )
            
            elif message.get("type") == "ping":
                # Heartbeat
                await manager.send_message(
                    session_id,
                    WebSocketMessage(type="pong", content="", metadata={})
                )
    
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        # Send error message
        await manager.send_message(
            session_id,
            WebSocketMessage(
                type="error",
                content=str(e),
                metadata={}
            )
        )
        manager.disconnect(session_id)
