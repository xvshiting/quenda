"""
Agent management API routes.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from quenda.web.services.agent_service import AgentService
from quenda.web.models.agent import AgentConfig, AgentSummary


router = APIRouter()


def get_agent_service(request: Request) -> AgentService:
    """Get agent service from app state."""
    return request.app.state.agent_service


class CreateAgentRequest(BaseModel):
    """Request to create a new agent."""
    name: str
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: List[str] = []
    model: Optional[str] = None
    config_yaml: Optional[str] = None  # Raw YAML config


class UpdateAgentRequest(BaseModel):
    """Request to update an agent."""
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    model: Optional[str] = None
    config_yaml: Optional[str] = None


@router.get("", response_model=List[AgentSummary])
async def list_agents(
    service: AgentService = Depends(get_agent_service)
):
    """List all available agents."""
    return await service.list_agents()


@router.post("", response_model=AgentConfig)
async def create_agent(
    request: CreateAgentRequest,
    service: AgentService = Depends(get_agent_service)
):
    """Create a new agent."""
    try:
        return await service.create_agent(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{agent_id}", response_model=AgentConfig)
async def get_agent(
    agent_id: str,
    service: AgentService = Depends(get_agent_service)
):
    """Get agent details by ID."""
    agent = await service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentConfig)
async def update_agent(
    agent_id: str,
    request: UpdateAgentRequest,
    service: AgentService = Depends(get_agent_service)
):
    """Update an agent."""
    try:
        agent = await service.update_agent(agent_id, request)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    service: AgentService = Depends(get_agent_service)
):
    """Delete an agent."""
    deleted = await service.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "deleted", "agent_id": agent_id}


@router.get("/{agent_id}/templates")
async def get_agent_templates(
    service: AgentService = Depends(get_agent_service)
):
    """Get available agent templates."""
    return await service.get_templates()
