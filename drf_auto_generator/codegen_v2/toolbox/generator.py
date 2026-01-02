"""
Google MCP Toolbox for Databases generator.

Generates YAML configuration for Google's MCP Toolbox, which provides
a secure, configurable interface for executing pre-defined SQL queries
against PostgreSQL, MySQL, and other databases.

Documentation: https://googleapis.github.io/genai-toolbox/
GitHub: https://github.com/googleapis/genai-toolbox
"""

import logging
from typing import Any, Optional
import yaml

from ..base import ProjectGenerator, register_generator
from ..schema import DatabaseSchema, TableSchema, FieldType, RelationshipType

logger = logging.getLogger(__name__)


@register_generator
class ToolboxGenerator(ProjectGenerator):
    """
    Generates configuration for Google's MCP Toolbox for Databases.

    The generated configuration provides:
    - Database source definitions (PostgreSQL, MySQL, etc.)
    - CRUD tools for each table (list, get, search, create, update, delete)
    - Toolsets for grouping related tools
    - Environment variable support for secure credential management
    """

    name = "toolbox"
    description = "Google MCP Toolbox for Databases configuration generator"

    # Supported database kinds in Toolbox
    DATABASE_KINDS = {
        "postgresql": "postgres",
        "postgres": "postgres",
        "mysql": "mysql",
        "alloydb": "alloydb-postgres",
        "cloudsql-postgres": "cloudsql-postgres",
        "cloudsql-mysql": "cloudsql-mysql",
        "spanner": "spanner",
        "bigquery": "bigquery",
    }

    def __init__(self, schema: DatabaseSchema, config: Optional[dict[str, Any]] = None):
        super().__init__(schema, config)
        self.source_name = self.config.get("source_name", "main-db")
        self.db_kind = self._get_db_kind()

    def _get_db_kind(self) -> str:
        """Get the Toolbox database kind from config or schema."""
        db_type = self.config.get("db_kind") or self.schema.database_type or "postgresql"
        return self.DATABASE_KINDS.get(db_type.lower(), "postgres")

    def generate(self) -> dict[str, str]:
        """Generate all Toolbox configuration files."""
        files = {}

        logger.info(f"Generating Toolbox configuration for: {self.schema.database_name}")

        # Main tools.yaml configuration
        files["tools.yaml"] = self._generate_tools_yaml()

        # Environment template
        files[".env.example"] = self._generate_env_example()

        # README with usage instructions
        files["README.md"] = self._generate_readme()

        # Docker compose for running Toolbox
        files["docker-compose.yaml"] = self._generate_docker_compose()

        logger.info(f"Generated {len(files)} Toolbox configuration files")

        return files

    def _generate_tools_yaml(self) -> str:
        """Generate the main tools.yaml configuration file."""
        config = {
            "sources": self._generate_sources(),
            "tools": self._generate_tools(),
            "toolsets": self._generate_toolsets(),
        }

        # Use YAML with custom formatting for readability
        return yaml.dump(
            config,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        )

    def _generate_sources(self) -> dict[str, Any]:
        """Generate database source configurations."""
        sources = {}

        if self.db_kind == "postgres":
            sources[self.source_name] = {
                "kind": "postgres",
                "host": "${DB_HOST:localhost}",
                "port": "${DB_PORT:5432}",
                "database": f"${{DB_NAME:{self.schema.database_name or 'postgres'}}}",
                "user": "${DB_USER:postgres}",
                "password": "${DB_PASSWORD}",
            }
        elif self.db_kind == "mysql":
            sources[self.source_name] = {
                "kind": "mysql",
                "host": "${DB_HOST:localhost}",
                "port": "${DB_PORT:3306}",
                "database": f"${{DB_NAME:{self.schema.database_name or 'mysql'}}}",
                "user": "${DB_USER:root}",
                "password": "${DB_PASSWORD}",
            }
        elif self.db_kind == "alloydb-postgres":
            sources[self.source_name] = {
                "kind": "alloydb-postgres",
                "project": "${GCP_PROJECT}",
                "region": "${ALLOYDB_REGION:us-central1}",
                "cluster": "${ALLOYDB_CLUSTER}",
                "instance": "${ALLOYDB_INSTANCE}",
                "database": f"${{DB_NAME:{self.schema.database_name or 'postgres'}}}",
                "user": "${DB_USER:postgres}",
                "password": "${DB_PASSWORD}",
            }
        elif self.db_kind == "cloudsql-postgres":
            sources[self.source_name] = {
                "kind": "cloudsql-postgres",
                "project": "${GCP_PROJECT}",
                "region": "${CLOUDSQL_REGION:us-central1}",
                "instance": "${CLOUDSQL_INSTANCE}",
                "database": f"${{DB_NAME:{self.schema.database_name or 'postgres'}}}",
                "user": "${DB_USER:postgres}",
                "password": "${DB_PASSWORD}",
            }
        elif self.db_kind == "bigquery":
            sources[self.source_name] = {
                "kind": "bigquery",
                "project": "${GCP_PROJECT}",
                "dataset": f"${{BQ_DATASET:{self.schema.database_name or 'default'}}}",
            }
        else:
            # Default to postgres
            sources[self.source_name] = {
                "kind": "postgres",
                "host": "${DB_HOST:localhost}",
                "port": "${DB_PORT:5432}",
                "database": f"${{DB_NAME:{self.schema.database_name or 'postgres'}}}",
                "user": "${DB_USER:postgres}",
                "password": "${DB_PASSWORD}",
            }

        return sources

    def _generate_tools(self) -> dict[str, Any]:
        """Generate tool definitions for all tables."""
        tools = {}

        for table in self.schema.get_non_through_tables():
            if not table.primary_key_columns:
                logger.warning(f"Skipping table {table.name}: no primary key")
                continue

            # Generate CRUD tools for each table
            tools.update(self._generate_table_tools(table))

        # Add schema introspection tool
        tools["describe_schema"] = {
            "kind": f"{self.db_kind}-sql",
            "source": self.source_name,
            "description": "Get information about all tables and their columns in the database.",
            "statement": self._get_schema_query(),
        }

        return tools

    def _generate_table_tools(self, table: TableSchema) -> dict[str, Any]:
        """Generate CRUD tools for a single table."""
        tools = {}
        table_name = table.name
        model_name = table.model_name
        pk_col = table.pk_column or table.primary_key_columns[0]

        # List tool with pagination
        tools[f"list_{table_name}"] = {
            "kind": f"{self.db_kind}-sql",
            "source": self.source_name,
            "description": f"List {model_name} records with optional pagination. Returns up to 100 records by default.",
            "parameters": [
                {
                    "name": "limit",
                    "type": "integer",
                    "description": "Maximum number of records to return (default: 100)",
                },
                {
                    "name": "offset",
                    "type": "integer",
                    "description": "Number of records to skip (default: 0)",
                },
            ],
            "statement": f"SELECT * FROM {table_name} LIMIT COALESCE($1, 100) OFFSET COALESCE($2, 0);",
        }

        # Get by ID tool
        tools[f"get_{table_name}"] = {
            "kind": f"{self.db_kind}-sql",
            "source": self.source_name,
            "description": f"Get a single {model_name} by its primary key ({pk_col}).",
            "parameters": [
                {
                    "name": pk_col,
                    "type": self._get_param_type(table, pk_col),
                    "description": f"The {pk_col} of the {model_name} to retrieve",
                },
            ],
            "statement": f"SELECT * FROM {table_name} WHERE {pk_col} = $1;",
        }

        # Search tool (for tables with text fields)
        searchable_fields = table.get_searchable_fields(limit=3)
        if searchable_fields:
            search_conditions = " OR ".join(
                f"{field} ILIKE '%' || $1 || '%'" for field in searchable_fields
            )
            tools[f"search_{table_name}"] = {
                "kind": f"{self.db_kind}-sql",
                "source": self.source_name,
                "description": f"Search for {model_name} records by text. Searches in: {', '.join(searchable_fields)}.",
                "parameters": [
                    {
                        "name": "query",
                        "type": "string",
                        "description": "The search term to look for",
                    },
                ],
                "statement": f"SELECT * FROM {table_name} WHERE {search_conditions} LIMIT 50;",
            }

        # Count tool
        tools[f"count_{table_name}"] = {
            "kind": f"{self.db_kind}-sql",
            "source": self.source_name,
            "description": f"Count the total number of {model_name} records in the database.",
            "statement": f"SELECT COUNT(*) as total FROM {table_name};",
        }

        # Insert tool
        insert_cols, insert_params = self._get_insert_columns(table)
        if insert_cols:
            placeholders = ", ".join(f"${i+1}" for i in range(len(insert_cols)))
            tools[f"create_{table_name}"] = {
                "kind": f"{self.db_kind}-sql",
                "source": self.source_name,
                "description": f"Create a new {model_name} record.",
                "parameters": insert_params,
                "statement": f"INSERT INTO {table_name} ({', '.join(insert_cols)}) VALUES ({placeholders}) RETURNING *;",
            }

        # Update tool
        if insert_cols:
            set_clause = ", ".join(f"{col} = ${i+2}" for i, col in enumerate(insert_cols))
            update_params = [
                {
                    "name": pk_col,
                    "type": self._get_param_type(table, pk_col),
                    "description": f"The {pk_col} of the {model_name} to update",
                },
            ] + insert_params

            tools[f"update_{table_name}"] = {
                "kind": f"{self.db_kind}-sql",
                "source": self.source_name,
                "description": f"Update an existing {model_name} record by primary key.",
                "parameters": update_params,
                "statement": f"UPDATE {table_name} SET {set_clause} WHERE {pk_col} = $1 RETURNING *;",
            }

        # Delete tool
        tools[f"delete_{table_name}"] = {
            "kind": f"{self.db_kind}-sql",
            "source": self.source_name,
            "description": f"Delete a {model_name} record by primary key. Returns the deleted record.",
            "parameters": [
                {
                    "name": pk_col,
                    "type": self._get_param_type(table, pk_col),
                    "description": f"The {pk_col} of the {model_name} to delete",
                },
            ],
            "statement": f"DELETE FROM {table_name} WHERE {pk_col} = $1 RETURNING *;",
        }

        return tools

    def _generate_toolsets(self) -> dict[str, list[str]]:
        """Generate toolset groupings."""
        toolsets = {}
        tables = [t for t in self.schema.get_non_through_tables() if t.primary_key_columns]

        # All tools toolset
        all_tools = ["describe_schema"]
        for table in tables:
            all_tools.extend([
                f"list_{table.name}",
                f"get_{table.name}",
                f"count_{table.name}",
            ])
            if table.get_searchable_fields():
                all_tools.append(f"search_{table.name}")

        toolsets["read_only"] = all_tools

        # Full CRUD toolset
        crud_tools = list(all_tools)
        for table in tables:
            crud_tools.extend([
                f"create_{table.name}",
                f"update_{table.name}",
                f"delete_{table.name}",
            ])

        toolsets["full_crud"] = crud_tools

        # Per-table toolsets
        for table in tables:
            table_tools = [
                f"list_{table.name}",
                f"get_{table.name}",
                f"count_{table.name}",
            ]
            if table.get_searchable_fields():
                table_tools.append(f"search_{table.name}")
            table_tools.extend([
                f"create_{table.name}",
                f"update_{table.name}",
                f"delete_{table.name}",
            ])
            toolsets[f"{table.name}_tools"] = table_tools

        return toolsets

    def _get_insert_columns(self, table: TableSchema) -> tuple[list[str], list[dict]]:
        """Get columns and parameters for INSERT operations."""
        columns = []
        params = []

        for col in table.columns:
            # Skip auto-generated primary keys
            if col.primary_key and col.field_type in (
                FieldType.AUTO, FieldType.BIG_AUTO, FieldType.SMALL_AUTO
            ):
                continue

            columns.append(col.name)
            params.append({
                "name": col.name,
                "type": self._field_type_to_param_type(col.field_type),
                "description": col.comment or f"The {col.name} value",
            })

        return columns, params

    def _get_param_type(self, table: TableSchema, column_name: str) -> str:
        """Get the Toolbox parameter type for a column."""
        col = table.get_column(column_name)
        if col:
            return self._field_type_to_param_type(col.field_type)
        return "string"

    def _field_type_to_param_type(self, field_type: FieldType) -> str:
        """Convert Django field type to Toolbox parameter type."""
        integer_types = {
            FieldType.AUTO, FieldType.BIG_AUTO, FieldType.SMALL_AUTO,
            FieldType.INTEGER, FieldType.BIG_INTEGER, FieldType.SMALL_INTEGER,
            FieldType.POSITIVE_INTEGER, FieldType.POSITIVE_BIG_INTEGER,
            FieldType.POSITIVE_SMALL_INTEGER,
        }
        float_types = {FieldType.FLOAT, FieldType.DECIMAL}
        bool_types = {FieldType.BOOLEAN, FieldType.NULL_BOOLEAN}

        if field_type in integer_types:
            return "integer"
        elif field_type in float_types:
            return "number"
        elif field_type in bool_types:
            return "boolean"
        else:
            return "string"

    def _get_schema_query(self) -> str:
        """Get the SQL query for schema introspection based on database type."""
        if self.db_kind in ("postgres", "alloydb-postgres", "cloudsql-postgres"):
            return """
SELECT
    t.table_name,
    c.column_name,
    c.data_type,
    c.is_nullable,
    c.column_default
FROM information_schema.tables t
JOIN information_schema.columns c ON t.table_name = c.table_name
WHERE t.table_schema = 'public'
  AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name, c.ordinal_position;
"""
        elif self.db_kind in ("mysql", "cloudsql-mysql"):
            return """
SELECT
    TABLE_NAME as table_name,
    COLUMN_NAME as column_name,
    DATA_TYPE as data_type,
    IS_NULLABLE as is_nullable,
    COLUMN_DEFAULT as column_default
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME, ORDINAL_POSITION;
"""
        else:
            return "SELECT 'Schema introspection not supported for this database type' as message;"

    def _generate_env_example(self) -> str:
        """Generate .env.example file."""
        if self.db_kind in ("postgres", "mysql"):
            return f"""# Database connection settings
DB_HOST=localhost
DB_PORT={'5432' if 'postgres' in self.db_kind else '3306'}
DB_NAME={self.schema.database_name or 'your_database'}
DB_USER={'postgres' if 'postgres' in self.db_kind else 'root'}
DB_PASSWORD=your_password_here
"""
        elif "alloydb" in self.db_kind or "cloudsql" in self.db_kind:
            return f"""# Google Cloud settings
GCP_PROJECT=your-project-id
{'ALLOYDB_REGION' if 'alloydb' in self.db_kind else 'CLOUDSQL_REGION'}=us-central1
{'ALLOYDB_CLUSTER' if 'alloydb' in self.db_kind else 'CLOUDSQL_INSTANCE'}=your-instance
{'ALLOYDB_INSTANCE' if 'alloydb' in self.db_kind else ''}={'your-instance' if 'alloydb' in self.db_kind else ''}
DB_NAME={self.schema.database_name or 'postgres'}
DB_USER=postgres
DB_PASSWORD=your_password_here
"""
        elif self.db_kind == "bigquery":
            return f"""# Google Cloud BigQuery settings
GCP_PROJECT=your-project-id
BQ_DATASET={self.schema.database_name or 'your_dataset'}
"""
        else:
            return """# Database settings - configure based on your database type
"""

    def _generate_docker_compose(self) -> str:
        """Generate docker-compose.yaml for running Toolbox."""
        return f"""# Docker Compose for running MCP Toolbox for Databases
# Documentation: https://googleapis.github.io/genai-toolbox/

version: '3.8'

services:
  toolbox:
    image: us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest
    ports:
      - "5000:5000"
    volumes:
      - ./tools.yaml:/app/tools.yaml:ro
    environment:
      - DB_HOST=${{DB_HOST:-host.docker.internal}}
      - DB_PORT=${{DB_PORT:-5432}}
      - DB_NAME=${{DB_NAME:-{self.schema.database_name or 'postgres'}}}
      - DB_USER=${{DB_USER:-postgres}}
      - DB_PASSWORD=${{DB_PASSWORD}}
    command: ["--tools-file", "/app/tools.yaml", "--address", "0.0.0.0:5000"]
    extra_hosts:
      - "host.docker.internal:host-gateway"
"""

    def _generate_readme(self) -> str:
        """Generate README.md with usage instructions."""
        tables = self.schema.get_non_through_tables()
        table_count = len([t for t in tables if t.primary_key_columns])

        table_list = "\n".join(
            f"- `{t.name}` ({t.model_name})"
            for t in tables if t.primary_key_columns
        )

        return f'''# MCP Toolbox Configuration for {self.schema.database_name or "Database"}

This directory contains configuration for [Google's MCP Toolbox for Databases](https://github.com/googleapis/genai-toolbox),
providing AI assistants with secure, pre-defined SQL tools for database access.

## Overview

- **Database**: {self.schema.database_name or "PostgreSQL"}
- **Tables**: {table_count}
- **Database Type**: {self.db_kind}

## Tables

{table_list}

## Tools Generated

For each table, the following tools are available:

| Tool | Description |
|------|-------------|
| `list_{{table}}` | List records with pagination |
| `get_{{table}}` | Get a single record by primary key |
| `search_{{table}}` | Search by text fields (where applicable) |
| `count_{{table}}` | Count total records |
| `create_{{table}}` | Create a new record |
| `update_{{table}}` | Update an existing record |
| `delete_{{table}}` | Delete a record |

Additional tools:
- `describe_schema` - Get database schema information

## Toolsets

- `read_only` - All read operations (list, get, search, count)
- `full_crud` - All operations including create, update, delete
- `{{table}}_tools` - All tools for a specific table

## Installation

### Option 1: Binary Installation

```bash
# macOS/Linux (Homebrew)
brew install googleapis/genai-toolbox/toolbox

# Or download directly
curl -O https://storage.googleapis.com/genai-toolbox/v0.24.0/toolbox-linux-amd64
chmod +x toolbox-linux-amd64
```

### Option 2: Docker

```bash
docker-compose up
```

## Configuration

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your database credentials.

3. Run Toolbox:
   ```bash
   # With binary
   ./toolbox --tools-file tools.yaml

   # With Docker
   docker-compose up
   ```

## Usage with Claude Desktop

Add to your Claude Desktop MCP configuration (`~/.config/claude/claude_desktop_config.json`):

```json
{{
  "mcpServers": {{
    "{self.schema.database_name or 'database'}-toolbox": {{
      "command": "toolbox",
      "args": ["--tools-file", "/path/to/tools.yaml", "--mcp"],
      "env": {{
        "DB_HOST": "localhost",
        "DB_NAME": "{self.schema.database_name or 'your_database'}",
        "DB_USER": "postgres",
        "DB_PASSWORD": "your_password"
      }}
    }}
  }}
}}
```

## Usage with LangChain/LlamaIndex

```python
from toolbox_langchain import ToolboxClient

# Connect to Toolbox server
client = ToolboxClient("http://localhost:5000")

# Load tools
tools = client.load_toolset("read_only")

# Use with your agent
agent = create_agent(llm, tools)
```

## Security Notes

- All SQL queries are pre-defined in `tools.yaml` - no arbitrary SQL execution
- Use environment variables for credentials (never commit `.env`)
- Consider using `read_only` toolset for most AI agents
- Toolbox supports OAuth2/OIDC for authenticated access

## Documentation

- [MCP Toolbox Documentation](https://googleapis.github.io/genai-toolbox/)
- [Configuration Reference](https://googleapis.github.io/genai-toolbox/getting-started/configure/)
- [MCP Integration](https://googleapis.github.io/genai-toolbox/how-to/connect_via_mcp/)
'''
