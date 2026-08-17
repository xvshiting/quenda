"""
Session management API routes.
"""

import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from quenda.web.models.session import (
    SessionActivity,
    SessionInfo,
    SessionInteraction,
    SessionMessage,
)
from quenda.web.services.session_service import SessionService

router = APIRouter()


def get_session_service(request: Request) -> SessionService:
    """Get session service from app state."""
    return request.app.state.session_service


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    agent_id: str
    workspace_id: str | None = None
    title: str | None = None
    provider: str | None = None
    model: str | None = None


class UpdateSessionRequest(BaseModel):
    """Mutable session preferences."""

    title: str | None = None
    provider: str | None = None
    model: str | None = None


class AttachmentRequest(BaseModel):
    """Base64 file payload supplied by the browser."""

    name: str
    media_type: str = "application/octet-stream"
    data: str


class SendMessageRequest(BaseModel):
    """Request to send a message in a session."""
    message: str
    stream: bool = True  # Whether to stream the response
    attachments: list[AttachmentRequest] = Field(default_factory=list)


class InteractionAnswer(BaseModel):
    """One answer in a single or batched interaction response."""

    question_id: str
    selected_option_ids: list[str] = Field(default_factory=list)
    value: str | None = None


class RespondToInteractionRequest(BaseModel):
    """Answers submitted by the Web interaction card."""

    answers: list[InteractionAnswer]


@router.get("", response_model=list[SessionInfo])
async def list_sessions(
    agent_id: str | None = None,
    workspace_id: str | None = None,
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
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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


@router.put("/{session_id}", response_model=SessionInfo)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    service: SessionService = Depends(get_session_service),
):
    """Update the title or select the model used by future turns."""
    try:
        session = await service.update_session(
            session_id,
            title=request.title,
            provider=request.provider,
            model=request.model,
            update_model=bool(request.model_fields_set & {"provider", "model"}),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if session is None:
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


@router.get("/{session_id}/messages", response_model=list[SessionMessage])
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


@router.get("/{session_id}/activities", response_model=list[SessionActivity])
async def get_activities(
    session_id: str,
    service: SessionService = Depends(get_session_service),
):
    """Get inspectable Runtime activity recorded for the session."""
    activities = await service.get_activities(session_id)
    if activities is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return activities


@router.get("/{session_id}/interactions", response_model=list[SessionInteraction])
async def get_interactions(
    session_id: str,
    pending_only: bool = False,
    service: SessionService = Depends(get_session_service),
):
    """Get durable interaction requests, including those restored after refresh."""
    interactions = await service.get_interactions(session_id, pending_only=pending_only)
    if interactions is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return interactions


@router.post("/{session_id}/interactions/{interaction_id}/respond")
async def respond_to_interaction(
    session_id: str,
    interaction_id: str,
    request: RespondToInteractionRequest,
    service: SessionService = Depends(get_session_service),
):
    """Answer a pending interaction and continue the paused conversation."""
    try:
        result = await service.respond_to_interaction(
            session_id,
            interaction_id,
            [answer.model_dump() for answer in request.answers],
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.get("/{session_id}/commands")
async def list_commands(
    session_id: str,
    input: str = "",
    service: SessionService = Depends(get_session_service),
):
    """List Slash commands or candidates for the current input."""
    try:
        commands = await service.list_commands(session_id, input)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if commands is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return commands


@router.get("/{session_id}/attachments/{attachment_id}")
async def get_attachment(
    session_id: str,
    attachment_id: str,
    service: SessionService = Depends(get_session_service),
):
    """Preview or download a recorded session attachment."""
    path = await service.get_attachment_path(session_id, attachment_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    filename = path.name.split("-", 1)[-1]
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    disposition = (
        "inline"
        if media_type.startswith(("image/", "video/", "audio/"))
        or media_type == "application/pdf"
        else "attachment"
    )
    return FileResponse(
        path,
        filename=filename,
        media_type=media_type,
        content_disposition_type=disposition,
    )


@router.post("/{session_id}/send")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    service: SessionService = Depends(get_session_service)
):
    """Send a message in a session (non-streaming)."""
    try:
        result = await service.send_message(
            session_id,
            request.message,
            attachments=request.attachments,
            stream=False,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return result
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{session_id}/run")
async def run_agent(
    session_id: str,
    request: SendMessageRequest,
    service: SessionService = Depends(get_session_service)
):
    """Run agent in a session (streaming response via WebSocket recommended)."""
    try:
        result = await service.send_message(
            session_id,
            request.message,
            attachments=request.attachments,
            stream=request.stream,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return result
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
