"""
Tool management API routes.
"""

from typing import List, Dict, Any
from fastapi import APIRouter

from quenda.tools import get_core_tools, get_extended_tools


router = APIRouter()


@router.get("")
async def list_tools():
    """List all available tools."""
    # Get core tools (with placeholder workspace)
    tools = get_core_tools(workspace_root=".")
    
    tool_list = []
    for tool in tools:
        tool_info = {
            "name": tool.name,
            "description": tool.description,
            "parameters": {},
        }
        
        # Extract parameter info from tool schema
        if hasattr(tool, "parameters") and tool.parameters:
            for param_name, param_schema in tool.parameters.items():
                tool_info["parameters"][param_name] = {
                    "type": param_schema.get("type", "any"),
                    "description": param_schema.get("description", ""),
                    "required": param_name in tool.required_parameters,
                }
        
        tool_list.append(tool_info)
    
    return tool_list


@router.get("/bundles")
async def list_tool_bundles():
    """List available tool bundles."""
    return [
        {
            "name": "core",
            "description": "Core tools (11 tools): file operations, execution, interaction",
            "tools": [
                "list_files", "search_text", "read_file", "write_file", "apply_patch",
                "execute_python", "run_shell", "get_current_datetime",
                "request_interaction", "request_skill_activation", "activate_resource",
            ]
        },
        {
            "name": "network",
            "description": "Network tools (2 tools): HTTP requests, web fetching",
            "tools": ["http_request", "web_fetch"]
        },
        {
            "name": "extended",
            "description": "Extended tools (13 tools): core + network",
            "tools": [
                "list_files", "search_text", "read_file", "write_file", "apply_patch",
                "execute_python", "run_shell", "get_current_datetime",
                "request_interaction", "request_skill_activation", "activate_resource",
                "http_request", "web_fetch",
            ]
        },
    ]
