"""
MCP (Model Context Protocol) server generators.

This module provides generators for creating MCP servers that expose
database operations to AI assistants like Claude.
"""

from .generator import MCPServerGenerator

__all__ = ["MCPServerGenerator"]
