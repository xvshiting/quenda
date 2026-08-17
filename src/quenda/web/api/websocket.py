"""WebSocket API for real-time session interaction."""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from quenda.web.services.session_service import SessionService
from quenda.runtime.cancellation import CancellationToken

router = APIRouter()


class WebSocketMessage(BaseModel):
    """WebSocket message format."""

    type: str  # "user_message", "tool_call", "tool_result", "stream_chunk", "error"
    content: Any
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

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
    service: SessionService = websocket.app.state.session_service
    if await service.get_session(session_id) is None:
        await websocket.accept()
        await websocket.send_json(
            WebSocketMessage(type="error", content="Session not found").model_dump()
        )
        await websocket.close(code=1008)
        return

    await manager.connect(session_id, websocket)
    active_turn_task: asyncio.Task[None] | None = None
    active_token: CancellationToken | None = None

    async def run_user_turn(
        user_content: str,
        attachments: list[Any],
        token: CancellationToken,
    ) -> None:
        nonlocal active_turn_task, active_token
        await manager.send_message(
            session_id,
            WebSocketMessage(type="stream_start", content=""),
        )
        try:
            delta_tasks: list[asyncio.Task[None]] = []

            def send_delta(content: str) -> None:
                delta_tasks.append(asyncio.create_task(manager.send_message(
                    session_id,
                    WebSocketMessage(type="stream_chunk", content=content),
                )))

            result = await service.send_message(
                session_id,
                user_content,
                attachments=attachments,
                stream=True,
                on_delta=send_delta,
                cancellation_token=token,
            )
            if delta_tasks:
                await asyncio.gather(*delta_tasks)
            if token.is_cancelled:
                await manager.send_message(
                    session_id,
                    WebSocketMessage(type="stream_interrupted", content=""),
                )
                return
            if result is None:
                raise ValueError("Session not found")
            interaction = result.get("interaction")
            if interaction is not None:
                await manager.send_message(
                    session_id,
                    WebSocketMessage(
                        type="interaction_requested",
                        content=interaction,
                        metadata={"activities": result.get("activities", [])},
                    ),
                )
                return
            agent_message = result["agent_message"]
            await manager.send_message(
                session_id,
                WebSocketMessage(
                    type="stream_end",
                    content=agent_message["content"],
                    metadata={
                        "message_id": agent_message["id"],
                        "activities": result.get("activities", []),
                    },
                ),
            )
        except (RuntimeError, ValueError) as exc:
            if token.is_cancelled:
                await manager.send_message(
                    session_id,
                    WebSocketMessage(type="stream_interrupted", content=""),
                )
            else:
                await manager.send_message(
                    session_id,
                    WebSocketMessage(type="error", content=str(exc)),
                )
        finally:
            active_token = None
            active_turn_task = None

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await manager.send_message(
                    session_id,
                    WebSocketMessage(type="error", content="Message must be valid JSON"),
                )
                continue

            # Handle different message types
            if message.get("type") == "user_message":
                user_content = str(message.get("content", "")).strip()
                attachments = message.get("attachments") or []
                if not user_content and not attachments:
                    await manager.send_message(
                        session_id,
                        WebSocketMessage(type="error", content="Message cannot be empty"),
                    )
                    continue

                if active_turn_task is not None and not active_turn_task.done():
                    await manager.send_message(
                        session_id,
                        WebSocketMessage(type="error", content="A turn is already running"),
                    )
                    continue
                active_token = CancellationToken()
                active_turn_task = asyncio.create_task(
                    run_user_turn(user_content, attachments, active_token)
                )

            elif message.get("type") == "interrupt":
                if active_token is not None:
                    active_token.cancel()

            elif message.get("type") == "interaction_response":
                interaction_id = str(message.get("interaction_id", ""))
                answers = message.get("answers") or []
                try:
                    result = await service.respond_to_interaction(
                        session_id, interaction_id, answers
                    )
                    if result is None:
                        raise ValueError("Session not found")
                    if result.get("interaction") is not None:
                        await manager.send_message(
                            session_id,
                            WebSocketMessage(
                                type="interaction_requested",
                                content=result["interaction"],
                                metadata={"activities": result.get("activities", [])},
                            ),
                        )
                    else:
                        agent_message = result["agent_message"]
                        await manager.send_message(
                            session_id,
                            WebSocketMessage(
                                type="stream_end",
                                content=agent_message["content"],
                                metadata={
                                    "message_id": agent_message["id"],
                                    "activities": result.get("activities", []),
                                },
                            ),
                        )
                except (RuntimeError, ValueError) as exc:
                    await manager.send_message(
                        session_id,
                        WebSocketMessage(type="error", content=str(exc)),
                    )

            elif message.get("type") == "ping":
                # Heartbeat
                await manager.send_message(
                    session_id, WebSocketMessage(type="pong", content="", metadata={})
                )

    except WebSocketDisconnect:
        if active_token is not None:
            active_token.cancel()
        manager.disconnect(session_id)
    except Exception as exc:
        await manager.send_message(
            session_id,
            WebSocketMessage(
                type="error",
                content=str(exc),
            ),
        )
        manager.disconnect(session_id)
