"""
Main entry point for the new CodeGen V2 system.

This module provides the primary interface for generating code from
database schemas using the new CodeBuilder-based approach.
"""

import logging
from pathlib import Path
from typing import Any, Optional

from drf_auto_generator.domain.models import TableInfo as LegacyTableInfo

from .schema import DatabaseSchema
from .converter import convert_tables_to_schema
from .base import default_registry, CodeGenerator
from .django import DjangoGenerator
from .mcp import MCPServerGenerator
from .toolbox import ToolboxGenerator

logger = logging.getLogger(__name__)


def generate_from_tables(
    tables: list[LegacyTableInfo],
    output_dir: str,
    project_name: str = "django_project",
    app_name: str = "api",
    database_name: Optional[str] = None,
    generators: Optional[list[str]] = None,
    config: Optional[dict[str, Any]] = None,
) -> dict[str, list[Path]]:
    """
    Generate code from legacy TableInfo objects.

    This is the main entry point that bridges the existing introspection
    system with the new code generation system.

    Args:
        tables: List of TableInfo objects from database introspection
        output_dir: Directory to write generated files
        project_name: Name of the Django project
        app_name: Name of the Django app
        database_name: Optional database name
        generators: List of generator names to use (default: ["django"])
        config: Optional additional configuration

    Returns:
        Dictionary mapping generator names to lists of generated file paths
    """
    # Convert to new schema format
    logger.info("Converting tables to new schema format...")
    schema = convert_tables_to_schema(
        tables=tables,
        project_name=project_name,
        app_name=app_name,
        database_name=database_name,
    )

    # Use default generators if not specified
    if generators is None:
        generators = ["django"]

    # Merge config
    full_config = {
        "project_name": project_name,
        "app_name": app_name,
        "database_name": database_name,
        **(config or {}),
    }

    return generate_from_schema(
        schema=schema,
        output_dir=output_dir,
        generators=generators,
        config=full_config,
    )


def generate_from_schema(
    schema: DatabaseSchema,
    output_dir: str,
    generators: Optional[list[str]] = None,
    config: Optional[dict[str, Any]] = None,
) -> dict[str, list[Path]]:
    """
    Generate code from a DatabaseSchema.

    Args:
        schema: The database schema IR
        output_dir: Directory to write generated files
        generators: List of generator names to use (default: ["django"])
        config: Optional additional configuration

    Returns:
        Dictionary mapping generator names to lists of generated file paths
    """
    if generators is None:
        generators = ["django"]

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = {}

    for gen_name in generators:
        logger.info(f"Running generator: {gen_name}")

        try:
            generator = default_registry.create(gen_name, schema)

            # Pass config if generator supports it
            if hasattr(generator, 'config') and config:
                generator.config.update(config)

            # Generate and write files
            written_files = generator.write_files(output_path)
            results[gen_name] = written_files

            logger.info(f"Generator {gen_name} produced {len(written_files)} files")

        except KeyError:
            logger.error(f"Generator '{gen_name}' not found")
            available = default_registry.available_generators
            logger.info(f"Available generators: {available}")
            raise

    return results


def generate_django_project(
    tables: list[LegacyTableInfo],
    output_dir: str,
    project_name: str,
    app_name: str,
    config: Optional[dict[str, Any]] = None,
) -> list[Path]:
    """
    Convenience function to generate a Django project.

    Args:
        tables: List of TableInfo objects from database introspection
        output_dir: Directory to write generated files
        project_name: Name of the Django project
        app_name: Name of the Django app
        config: Optional additional configuration

    Returns:
        List of generated file paths
    """
    results = generate_from_tables(
        tables=tables,
        output_dir=output_dir,
        project_name=project_name,
        app_name=app_name,
        generators=["django"],
        config=config,
    )
    return results.get("django", [])


def generate_mcp_server(
    tables: list[LegacyTableInfo],
    output_dir: str,
    server_name: Optional[str] = None,
    database_name: Optional[str] = None,
    config: Optional[dict[str, Any]] = None,
) -> list[Path]:
    """
    Convenience function to generate an MCP server.

    Args:
        tables: List of TableInfo objects from database introspection
        output_dir: Directory to write generated files
        server_name: Name for the MCP server
        database_name: Database name
        config: Optional additional configuration

    Returns:
        List of generated file paths
    """
    full_config = {
        "server_name": server_name or f"{database_name or 'db'}-mcp",
        **(config or {}),
    }

    results = generate_from_tables(
        tables=tables,
        output_dir=output_dir,
        project_name="mcp_server",
        app_name="server",
        database_name=database_name,
        generators=["mcp"],
        config=full_config,
    )
    return results.get("mcp", [])


def generate_toolbox_config(
    tables: list[LegacyTableInfo],
    output_dir: str,
    database_name: Optional[str] = None,
    db_kind: str = "postgresql",
    config: Optional[dict[str, Any]] = None,
) -> list[Path]:
    """
    Convenience function to generate Google MCP Toolbox configuration.

    Args:
        tables: List of TableInfo objects from database introspection
        output_dir: Directory to write generated files
        database_name: Database name
        db_kind: Database type (postgresql, mysql, alloydb, cloudsql-postgres, etc.)
        config: Optional additional configuration

    Returns:
        List of generated file paths
    """
    full_config = {
        "db_kind": db_kind,
        **(config or {}),
    }

    results = generate_from_tables(
        tables=tables,
        output_dir=output_dir,
        project_name="toolbox",
        app_name="tools",
        database_name=database_name,
        generators=["toolbox"],
        config=full_config,
    )
    return results.get("toolbox", [])


def list_generators() -> list[dict[str, str]]:
    """List all available generators."""
    return default_registry.list_generators()


# Ensure generators are registered when module is imported
def _ensure_generators_registered():
    """Make sure all generators are registered."""
    # These are already registered via @register_generator decorator
    # Just importing them is enough
    pass


_ensure_generators_registered()
