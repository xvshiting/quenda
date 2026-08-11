"""
Agent service - business logic for agent management.
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import yaml

from quenda.web.models.agent import AgentConfig, AgentSummary, AgentTemplate


class AgentService:
    """Service for managing agents."""
    
    def __init__(self, agents_dir: Optional[Path] = None):
        """
        Initialize agent service.
        
        Args:
            agents_dir: Directory to store agent configs. If None, uses default.
        """
        self.agents_dir = agents_dir or Path.home() / ".quenda" / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
    
    async def list_agents(self) -> List[AgentSummary]:
        """List all available agents."""
        agents = []
        
        # Scan agents directory
        for agent_file in self.agents_dir.glob("*/AGENT.md"):
            agent_id = agent_file.parent.name
            summary = await self._load_agent_summary(agent_id)
            if summary:
                agents.append(summary)
        
        # Also include Quenda Code agent (bundled)
        # TODO: Dynamically discover bundled agents
        agents.append(AgentSummary(
            id="quenda-code",
            name="Quenda Code",
            description="Official coding agent",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            model="GLM-5",
            tool_count=11,
        ))
        
        return agents
    
    async def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """Get agent by ID."""
        # Check if it's a bundled agent
        if agent_id == "quenda-code":
            # TODO: Load from package
            return AgentConfig(
                id="quenda-code",
                name="Quenda Code",
                description="Official coding agent",
                system_prompt="You are Quenda Code...",
                tools=["list_files", "read_file", "write_file", "run_shell"],
                model="GLM-5",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        
        # Load from file system
        agent_dir = self.agents_dir / agent_id
        if not agent_dir.exists():
            return None
        
        return await self._load_agent_config(agent_id)
    
    async def create_agent(self, request) -> AgentConfig:
        """Create a new agent."""
        agent_id = request.name.lower().replace(" ", "-")
        agent_dir = self.agents_dir / agent_id
        
        if agent_dir.exists():
            raise ValueError(f"Agent '{agent_id}' already exists")
        
        agent_dir.mkdir(parents=True, exist_ok=True)
        
        # Create AGENT.md
        agent_md = agent_dir / "AGENT.md"
        frontmatter = {
            "name": request.name,
            "description": request.description,
        }
        
        with open(agent_md, "w") as f:
            f.write("---\n")
            yaml.dump(frontmatter, f)
            f.write("---\n\n")
            if request.system_prompt:
                f.write(request.system_prompt)
            f.write("\n")
        
        # Create config.yaml if provided
        if request.config_yaml:
            config_file = agent_dir / "config.yaml"
            with open(config_file, "w") as f:
                f.write(request.config_yaml)
        
        return await self._load_agent_config(agent_id)
    
    async def update_agent(self, agent_id: str, request) -> Optional[AgentConfig]:
        """Update an agent."""
        agent_dir = self.agents_dir / agent_id
        if not agent_dir.exists():
            return None
        
        # Load existing config
        config = await self._load_agent_config(agent_id)
        if not config:
            return None
        
        # Update fields
        if request.name:
            # Update name in AGENT.md
            pass
        if request.system_prompt:
            # Update system prompt in AGENT.md
            pass
        if request.config_yaml:
            # Update config.yaml
            config_file = agent_dir / "config.yaml"
            with open(config_file, "w") as f:
                f.write(request.config_yaml)
        
        # Reload and return
        return await self._load_agent_config(agent_id)
    
    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        agent_dir = self.agents_dir / agent_id
        if not agent_dir.exists():
            return False
        
        # Remove directory
        import shutil
        shutil.rmtree(agent_dir)
        return True
    
    async def get_templates(self) -> List[AgentTemplate]:
        """Get available agent templates."""
        return [
            AgentTemplate(
                id="coding",
                name="Coding Agent",
                description="Agent for code generation and debugging",
                category="coding",
                config={
                    "tools": ["core"],
                    "model": "deepseek-v4-flash",
                }
            ),
            AgentTemplate(
                id="chat",
                name="Chat Agent",
                description="General-purpose conversational agent",
                category="chat",
                config={
                    "tools": ["core"],
                    "model": "gpt-4o",
                }
            ),
            AgentTemplate(
                id="analysis",
                name="Analysis Agent",
                description="Agent for data analysis and reporting",
                category="analysis",
                config={
                    "tools": ["core", "network"],
                    "model": "claude-3-5-sonnet",
                }
            ),
        ]
    
    async def _load_agent_summary(self, agent_id: str) -> Optional[AgentSummary]:
        """Load agent summary from file system."""
        agent_config = await self._load_agent_config(agent_id)
        if not agent_config:
            return None
        
        return AgentSummary(
            id=agent_config.id,
            name=agent_config.name,
            description=agent_config.description,
            created_at=agent_config.created_at,
            updated_at=agent_config.updated_at,
            model=agent_config.model,
            tool_count=len(agent_config.tools),
        )
    
    async def _load_agent_config(self, agent_id: str) -> Optional[AgentConfig]:
        """Load full agent config from file system."""
        agent_dir = self.agents_dir / agent_id
        if not agent_dir.exists():
            return None
        
        agent_md = agent_dir / "AGENT.md"
        if not agent_md.exists():
            return None
        
        # Parse AGENT.md
        with open(agent_md, "r") as f:
            content = f.read()
        
        # Parse frontmatter
        metadata = {}
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                metadata = frontmatter or {}
                system_prompt = parts[2].strip()
        
        # Load config.yaml if exists
        config_yaml = None
        config_file = agent_dir / "config.yaml"
        if config_file.exists():
            with open(config_file, "r") as f:
                config_yaml = f.read()
        
        return AgentConfig(
            id=agent_id,
            name=metadata.get("name", agent_id),
            description=metadata.get("description"),
            system_prompt=system_prompt,
            tools=[],  # TODO: Load from config
            model=metadata.get("model"),
            config_yaml=config_yaml,
            created_at=datetime.fromtimestamp(agent_md.stat().st_ctime),
            updated_at=datetime.fromtimestamp(agent_md.stat().st_mtime),
            metadata=metadata,
        )
