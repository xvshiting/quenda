"""
Session service - business logic for session management.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from quenda.web.models.session import SessionInfo, SessionMessage, SessionUsage
from quenda import Agent
from quenda.runtime import SessionState


class SessionService:
    """Service for managing sessions."""
    
    def __init__(self, sessions_dir: Optional[Path] = None):
        """
        Initialize session service.
        
        Args:
            sessions_dir: Directory to store session data. If None, uses default.
        """
        self.sessions_dir = sessions_dir or Path.home() / ".quenda" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory session cache (for active sessions)
        self._active_sessions: Dict[str, Any] = {}
    
    async def list_sessions(
        self, 
        agent_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        limit: int = 50
    ) -> List[SessionInfo]:
        """List sessions, optionally filtered."""
        sessions = []
        
        # Scan sessions directory
        for session_dir in self.sessions_dir.iterdir():
            if session_dir.is_dir():
                session_info = await self._load_session_info(session_dir.name)
                if session_info:
                    # Apply filters
                    if agent_id and session_info.agent_id != agent_id:
                        continue
                    if workspace_id and session_info.workspace_id != workspace_id:
                        continue
                    
                    sessions.append(session_info)
        
        # Sort by updated_at (newest first)
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        
        return sessions[:limit]
    
    async def create_session(self, request) -> SessionInfo:
        """Create a new session."""
        session_id = str(uuid.uuid4())[:8]
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        now = datetime.now()
        session_data = {
            "id": session_id,
            "agent_id": request.agent_id,
            "workspace_id": request.workspace_id,
            "title": request.title or f"Session {session_id}",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "message_count": 0,
            "total_tokens": 0,
            "status": "active",
        }
        
        # Save session metadata
        import json
        with open(session_dir / "session.json", "w") as f:
            json.dump(session_data, f, indent=2)
        
        return SessionInfo(**session_data)
    
    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session by ID."""
        return await self._load_session_info(session_id)
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            return False
        
        # Remove directory
        import shutil
        shutil.rmtree(session_dir)
        
        # Remove from active sessions
        self._active_sessions.pop(session_id, None)
        
        return True
    
    async def get_messages(self, session_id: str, offset: int = 0, limit: int = 100) -> Optional[List[SessionMessage]]:
        """Get messages from a session."""
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            return None
        
        messages_file = session_dir / "messages.json"
        if not messages_file.exists():
            return []
        
        import json
        with open(messages_file, "r") as f:
            messages_data = json.load(f)
        
        messages = [SessionMessage(**msg) for msg in messages_data]
        return messages[offset:offset+limit]
    
    async def send_message(self, session_id: str, message: str, stream: bool = True) -> Optional[Dict[str, Any]]:
        """Send a message in a session."""
        # TODO: Implement actual agent interaction
        # For now, return a placeholder response
        
        session_info = await self.get_session(session_id)
        if not session_info:
            return None
        
        # Save user message
        user_msg = SessionMessage(
            id=str(uuid.uuid4())[:8],
            session_id=session_id,
            role="user",
            content=message,
            created_at=datetime.now(),
        )
        await self._save_message(session_id, user_msg)
        
        # TODO: Get actual agent and run it
        # For now, return placeholder response
        agent_msg = SessionMessage(
            id=str(uuid.uuid4())[:8],
            session_id=session_id,
            role="assistant",
            content=f"Received: {message}\n\n(This is a placeholder response. Agent integration pending.)",
            created_at=datetime.now(),
        )
        await self._save_message(session_id, agent_msg)
        
        return {
            "user_message": user_msg.model_dump(),
            "agent_message": agent_msg.model_dump(),
        }
    
    async def get_usage(self, session_id: str) -> Optional[SessionUsage]:
        """Get token usage for a session."""
        session_info = await self.get_session(session_id)
        if not session_info:
            return None
        
        return SessionUsage(
            session_id=session_id,
            total_input_tokens=0,
            total_output_tokens=0,
            total_tokens=0,
            message_count=session_info.message_count,
        )
    
    async def _load_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """Load session info from file."""
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            return None
        
        session_file = session_dir / "session.json"
        if not session_file.exists():
            return None
        
        import json
        with open(session_file, "r") as f:
            data = json.load(f)
        
        return SessionInfo(**data)
    
    async def _save_message(self, session_id: str, message: SessionMessage):
        """Save a message to the session."""
        session_dir = self.sessions_dir / session_id
        messages_file = session_dir / "messages.json"
        
        # Load existing messages
        messages_data = []
        if messages_file.exists():
            import json
            with open(messages_file, "r") as f:
                messages_data = json.load(f)
        
        # Append new message
        messages_data.append(message.model_dump())
        
        # Save
        import json
        with open(messages_file, "w") as f:
            json.dump(messages_data, f, indent=2)
        
        # Update session metadata
        session_info = await self._load_session_info(session_id)
        if session_info:
            session_info.message_count += 1
            session_info.updated_at = datetime.now()
            await self._update_session_info(session_info)
    
    async def _update_session_info(self, session_info: SessionInfo):
        """Update session info file."""
        session_dir = self.sessions_dir / session_info.id
        session_file = session_dir / "session.json"
        
        import json
        with open(session_file, "w") as f:
            json.dump(session_info.model_dump(), f, indent=2)
