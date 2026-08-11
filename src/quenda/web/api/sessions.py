"""
Session management API routes.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from quenda.web.services.session_service import SessionService
from quenda.web.models.session import SessionInfo, SessionMessage


router = APIRouter()


def get_session_service(request: Request) -> SessionService:
    """Get session service from app state."""
    return request.app.state.session_service


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    agent_id: str
    workspace_id: Optional[str] = None
    title: Optional[str] = None


class SendMessageRequest(BaseModel):
    """Request to send a message in a session."""
    message: str
    stream: bool = True  # Whether to stream the response


@router.get("", response_model=List[SessionInfo])
async def list_sessions(
    agent_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: int = 50,
    service: SessionService = Depends(get_session_service)
):
    """List sessions, optionally filtered by agent or workspace."""
    return await service.list_sessions(agent_id, workspace_id, limit)


@router.post("", response_model=SessionInfo)
async def create_session(
    request: CreateSessionRequest,
    service: SessionService = Depends(get_session_service)
):
    """Create a new session."""
    try:
        return await service.create_session(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service)
):
    """Get session details by ID."""
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    service: SessionService = Depends(get_session_service)
):
    """Delete a session."""
    deleted = await service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


@router.get("/{session_id}/messages", response_model=List[SessionMessage])
async def get_messages(
    session_id: str,
    offset: int = 0,
    limit: int = 100,
    service: SessionService = Depends(get_session_service)
):
    """Get messages from a session."""
    messages = await service.get_messages(session_id, offset, limit)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return messages


@router.post("/{session_id}/send")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    service: SessionService = Depends(get_session_service)
):
    """Send a message in a session (non-streaming)."""
    try:
        result = await service.send_message(session_id, request.message, stream=False)
        if result is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/run")
async def run_agent(
    session_id: str,
    request: SendMessageRequest,
    service: SessionService = Depends(get_session_service)
):
    """Run agent in a session (streaming response via WebSocket recommended)."""
    try:
        result = await service.send_message(session_id, request.message, stream=request.stream)
        if result is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{session_id}/usage")
async def get_usage(
    session_id: str,
    service: SessionService = Depends(get_session_service)
):
    """Get token usage for a session."""
    usage = await service.get_usage(session_id)
    if usage is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return usage
