"""
Google MCP Toolbox for Databases generator.

Generates YAML configuration files for Google's MCP Toolbox,
providing AI assistants with database access through pre-defined SQL tools.
"""

from .generator import ToolboxGenerator

__all__ = ["ToolboxGenerator"]
