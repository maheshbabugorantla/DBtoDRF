"""
MCP Server generator for PostgreSQL databases.

Generates an MCP server that exposes database operations as tools
for AI assistants like Claude to interact with.
"""

import logging
from typing import Any, Optional

from ..base import ProjectGenerator, register_generator
from ..code_builder import PythonCodeBuilder
from ..schema import DatabaseSchema, TableSchema, FieldType, RelationshipType

logger = logging.getLogger(__name__)


@register_generator
class MCPServerGenerator(ProjectGenerator):
    """
    Generates an MCP server for PostgreSQL database access.

    The generated server provides:
    - CRUD tools for each table (list, get, create, update, delete)
    - Schema introspection tools
    - Raw query execution (with safety checks)
    - Resources for table data and schema
    """

    name = "mcp"
    description = "MCP Server generator for database access"

    def __init__(self, schema: DatabaseSchema, config: Optional[dict[str, Any]] = None):
        super().__init__(schema, config)
        self.server_name = self.config.get("server_name", f"{self.schema.database_name or 'db'}-mcp")

    def generate(self) -> dict[str, str]:
        """Generate all MCP server files."""
        files = {}

        logger.info(f"Generating MCP server: {self.server_name}")

        # Main server file
        files["server.py"] = self._generate_server()

        # Tools module
        files["tools.py"] = self._generate_tools()

        # Resources module
        files["resources.py"] = self._generate_resources()

        # Database module
        files["database.py"] = self._generate_database()

        # Package init
        files["__init__.py"] = self._generate_init()

        # pyproject.toml
        files["pyproject.toml"] = self._generate_pyproject()

        # README
        files["README.md"] = self._generate_readme()

        logger.info(f"Generated {len(files)} MCP server files")

        return files

    def _generate_init(self) -> str:
        """Generate __init__.py."""
        b = PythonCodeBuilder()
        b.docstring(f"MCP Server for {self.schema.database_name or 'database'} access.")
        b.line()
        b.line(f'__version__ = "1.0.0"')
        return b.build()

    def _generate_server(self) -> str:
        """Generate the main server.py file."""
        b = PythonCodeBuilder()

        b.docstring(f"MCP Server for {self.schema.database_name or 'PostgreSQL'} database.\n\nProvides tools for CRUD operations on all tables.")
        b.line()

        # Imports
        b.import_("asyncio")
        b.import_("logging")
        b.import_("mcp.server", ["Server"])
        b.import_("mcp.server.stdio", ["stdio_server"])
        b.line()
        b.import_(".tools", ["register_tools"])
        b.import_(".resources", ["register_resources"])
        b.import_(".database", ["Database"])
        b.line()
        b.line()

        # Logging setup
        b.line('logging.basicConfig(level=logging.INFO)')
        b.line('logger = logging.getLogger(__name__)')
        b.line()
        b.line()

        # Create server instance
        b.comment("Create the MCP server instance")
        b.line(f'app = Server("{self.server_name}")')
        b.line()
        b.line()

        # Main function
        with b.function("main", is_async=True):
            b.docstring("Main entry point for the MCP server.")
            b.line()

            b.comment("Initialize database connection")
            b.line("db = Database()")
            b.line("await db.connect()")
            b.line()

            b.comment("Register tools and resources")
            b.line("register_tools(app, db)")
            b.line("register_resources(app, db)")
            b.line()

            b.line('logger.info(f"Starting MCP server: {self.server_name}")')
            b.line()

            with b.try_():
                with b.with_("stdio_server()", as_var="(read_stream, write_stream)"):
                    b.line("await app.run(read_stream, write_stream, app.create_initialization_options())")
            with b.finally_():
                b.line("await db.disconnect()")

        b.line()
        b.line()

        # Entry point
        with b.if_('__name__ == "__main__"'):
            b.line("asyncio.run(main())")

        return b.build()

    def _generate_tools(self) -> str:
        """Generate tools.py with CRUD operations for each table."""
        b = PythonCodeBuilder()

        b.docstring("MCP tools for database operations.\n\nProvides CRUD tools for each table in the database.")
        b.line()

        # Imports
        b.import_("json")
        b.import_("logging")
        b.import_("typing", ["Any"])
        b.import_("mcp.server", ["Server"])
        b.import_("mcp.types", ["Tool", "TextContent"])
        b.line()
        b.import_(".database", ["Database"])
        b.line()
        b.line()

        b.line('logger = logging.getLogger(__name__)')
        b.line()
        b.line()

        # Register function
        with b.function("register_tools", params=["app: Server", "db: Database"]):
            b.docstring("Register all database tools with the MCP server.")
            b.line()

            # List tools handler
            b.line("@app.list_tools()")
            with b.function("list_tools", is_async=True, returns="list[Tool]"):
                b.docstring("Return list of available tools.")
                b.line("tools = []")
                b.line()

                # Generate tool definitions for each table
                for table in self.schema.get_non_through_tables():
                    if not table.primary_key_columns:
                        continue
                    self._generate_tool_definitions(b, table)

                b.line()
                b.comment("Add schema introspection tool")
                b.line('tools.append(Tool(')
                b.indent()
                b.line('name="describe_schema",')
                b.line('description="Get the database schema information",')
                b.line('inputSchema={"type": "object", "properties": {}, "required": []},')
                b.dedent()
                b.line('))')
                b.line()

                b.return_("tools")

            b.line()

            # Call tools handler
            b.line("@app.call_tool()")
            with b.function("call_tool", params=["name: str", "arguments: dict[str, Any]"], is_async=True, returns="list[TextContent]"):
                b.docstring("Handle tool calls.")
                b.line()

                # Schema tool
                with b.if_('name == "describe_schema"'):
                    b.line("schema = await db.get_schema()")
                    b.line('return [TextContent(type="text", text=json.dumps(schema, indent=2))]')

                # Generate handlers for each table
                for table in self.schema.get_non_through_tables():
                    if not table.primary_key_columns:
                        continue
                    self._generate_tool_handlers(b, table)

                b.line()
                b.line(f'return [TextContent(type="text", text=f"Unknown tool: {{name}}")]')

        return b.build()

    def _generate_tool_definitions(self, b: PythonCodeBuilder, table: TableSchema) -> None:
        """Generate tool definitions for a table."""
        table_name = table.name
        model_name = table.model_name

        # List tool
        b.comment(f"Tools for {table_name}")
        b.line("tools.append(Tool(")
        b.indent()
        b.line(f'name="list_{table_name}",')
        b.line(f'description="List all {model_name} records with pagination",')
        b.line("inputSchema={")
        b.indent()
        b.line('"type": "object",')
        b.line('"properties": {')
        b.indent()
        b.line('"limit": {"type": "integer", "description": "Max records to return", "default": 100},')
        b.line('"offset": {"type": "integer", "description": "Records to skip", "default": 0},')
        b.dedent()
        b.line("},")
        b.line('"required": [],')
        b.dedent()
        b.line("},")
        b.dedent()
        b.line("))")
        b.line()

        # Get by ID tool
        pk_col = table.pk_column or "id"
        b.line("tools.append(Tool(")
        b.indent()
        b.line(f'name="get_{table_name}",')
        b.line(f'description="Get a {model_name} by primary key",')
        b.line("inputSchema={")
        b.indent()
        b.line('"type": "object",')
        b.line('"properties": {')
        b.indent()
        b.line(f'"{pk_col}": {{"type": "integer", "description": "The primary key value"}},')
        b.dedent()
        b.line("},")
        b.line(f'"required": ["{pk_col}"],')
        b.dedent()
        b.line("},")
        b.dedent()
        b.line("))")
        b.line()

        # Create tool
        create_props = self._get_create_properties(table)
        required_fields = self._get_required_fields(table)
        b.line("tools.append(Tool(")
        b.indent()
        b.line(f'name="create_{table_name}",')
        b.line(f'description="Create a new {model_name}",')
        b.line("inputSchema={")
        b.indent()
        b.line('"type": "object",')
        b.line(f'"properties": {json.dumps(create_props)},')
        b.line(f'"required": {json.dumps(required_fields)},')
        b.dedent()
        b.line("},")
        b.dedent()
        b.line("))")
        b.line()

        # Update tool
        b.line("tools.append(Tool(")
        b.indent()
        b.line(f'name="update_{table_name}",')
        b.line(f'description="Update an existing {model_name}",')
        b.line("inputSchema={")
        b.indent()
        b.line('"type": "object",')
        update_props = {pk_col: {"type": "integer", "description": "The primary key value"}}
        update_props.update(create_props)
        b.line(f'"properties": {json.dumps(update_props)},')
        b.line(f'"required": ["{pk_col}"],')
        b.dedent()
        b.line("},")
        b.dedent()
        b.line("))")
        b.line()

        # Delete tool
        b.line("tools.append(Tool(")
        b.indent()
        b.line(f'name="delete_{table_name}",')
        b.line(f'description="Delete a {model_name}",')
        b.line("inputSchema={")
        b.indent()
        b.line('"type": "object",')
        b.line('"properties": {')
        b.indent()
        b.line(f'"{pk_col}": {{"type": "integer", "description": "The primary key value"}},')
        b.dedent()
        b.line("},")
        b.line(f'"required": ["{pk_col}"],')
        b.dedent()
        b.line("},")
        b.dedent()
        b.line("))")
        b.line()

    def _generate_tool_handlers(self, b: PythonCodeBuilder, table: TableSchema) -> None:
        """Generate tool call handlers for a table."""
        table_name = table.name
        pk_col = table.pk_column or "id"

        # List handler
        with b.elif_(f'name == "list_{table_name}"'):
            b.line('limit = arguments.get("limit", 100)')
            b.line('offset = arguments.get("offset", 0)')
            b.line(f'results = await db.list_records("{table_name}", limit=limit, offset=offset)')
            b.line('return [TextContent(type="text", text=json.dumps(results, indent=2, default=str))]')

        # Get handler
        with b.elif_(f'name == "get_{table_name}"'):
            b.line(f'pk_value = arguments["{pk_col}"]')
            b.line(f'result = await db.get_record("{table_name}", "{pk_col}", pk_value)')
            b.line('return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]')

        # Create handler
        with b.elif_(f'name == "create_{table_name}"'):
            b.line(f'result = await db.create_record("{table_name}", arguments)')
            b.line('return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]')

        # Update handler
        with b.elif_(f'name == "update_{table_name}"'):
            b.line(f'pk_value = arguments.pop("{pk_col}")')
            b.line(f'result = await db.update_record("{table_name}", "{pk_col}", pk_value, arguments)')
            b.line('return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]')

        # Delete handler
        with b.elif_(f'name == "delete_{table_name}"'):
            b.line(f'pk_value = arguments["{pk_col}"]')
            b.line(f'result = await db.delete_record("{table_name}", "{pk_col}", pk_value)')
            b.line('return [TextContent(type="text", text=json.dumps({{"deleted": result}}, indent=2))]')

    def _get_create_properties(self, table: TableSchema) -> dict[str, Any]:
        """Get JSON Schema properties for create operation."""
        props = {}
        for col in table.columns:
            # Skip auto-generated PKs
            if col.primary_key and col.field_type in (FieldType.AUTO, FieldType.BIG_AUTO, FieldType.SMALL_AUTO):
                continue

            prop = {"description": col.comment or f"{col.name} field"}

            # Map field types to JSON Schema types
            if col.field_type in (FieldType.INTEGER, FieldType.BIG_INTEGER, FieldType.SMALL_INTEGER):
                prop["type"] = "integer"
            elif col.field_type in (FieldType.FLOAT, FieldType.DECIMAL):
                prop["type"] = "number"
            elif col.field_type == FieldType.BOOLEAN:
                prop["type"] = "boolean"
            elif col.field_type in (FieldType.DATE, FieldType.DATETIME, FieldType.TIME):
                prop["type"] = "string"
                prop["format"] = "date-time" if col.field_type == FieldType.DATETIME else "date"
            else:
                prop["type"] = "string"
                if col.max_length:
                    prop["maxLength"] = col.max_length

            props[col.django_field_name] = prop

        return props

    def _get_required_fields(self, table: TableSchema) -> list[str]:
        """Get required fields for create operation."""
        required = []
        for col in table.columns:
            # Skip auto-generated PKs
            if col.primary_key and col.field_type in (FieldType.AUTO, FieldType.BIG_AUTO, FieldType.SMALL_AUTO):
                continue
            # Required if not nullable and no default
            if not col.nullable and col.default is None:
                required.append(col.django_field_name)
        return required

    def _generate_resources(self) -> str:
        """Generate resources.py."""
        b = PythonCodeBuilder()

        b.docstring("MCP resources for database schema and data access.")
        b.line()

        # Imports
        b.import_("json")
        b.import_("logging")
        b.import_("mcp.server", ["Server"])
        b.import_("mcp.types", ["Resource", "TextResourceContents"])
        b.line()
        b.import_(".database", ["Database"])
        b.line()
        b.line()

        b.line('logger = logging.getLogger(__name__)')
        b.line()
        b.line()

        with b.function("register_resources", params=["app: Server", "db: Database"]):
            b.docstring("Register database resources with the MCP server.")
            b.line()

            # List resources handler
            b.line("@app.list_resources()")
            with b.function("list_resources", is_async=True, returns="list[Resource]"):
                b.docstring("Return list of available resources.")
                b.line("resources = []")
                b.line()

                b.comment("Schema resource")
                b.line('resources.append(Resource(')
                b.indent()
                b.line('uri="schema://tables",')
                b.line('name="Database Schema",')
                b.line('description="Complete database schema information",')
                b.line('mimeType="application/json",')
                b.dedent()
                b.line('))')
                b.line()

                # Table resources
                for table in self.schema.get_non_through_tables():
                    if not table.primary_key_columns:
                        continue
                    b.line('resources.append(Resource(')
                    b.indent()
                    b.line(f'uri="data://{table.name}",')
                    b.line(f'name="{table.model_name} Data",')
                    b.line(f'description="Data from the {table.name} table",')
                    b.line('mimeType="application/json",')
                    b.dedent()
                    b.line('))')

                b.line()
                b.return_("resources")

            b.line()

            # Read resource handler
            b.line("@app.read_resource()")
            with b.function("read_resource", params=["uri: str"], is_async=True, returns="list[TextResourceContents]"):
                b.docstring("Read a resource by URI.")
                b.line()

                with b.if_('uri == "schema://tables"'):
                    b.line("schema = await db.get_schema()")
                    b.line('content = json.dumps(schema, indent=2)')
                    b.line('return [TextResourceContents(uri=uri, text=content, mimeType="application/json")]')

                with b.elif_('uri.startswith("data://")'):
                    b.line('table_name = uri.replace("data://", "")')
                    b.line('data = await db.list_records(table_name, limit=100)')
                    b.line('content = json.dumps(data, indent=2, default=str)')
                    b.line('return [TextResourceContents(uri=uri, text=content, mimeType="application/json")]')

                b.line()
                b.line('raise ValueError(f"Unknown resource: {uri}")')

        return b.build()

    def _generate_database(self) -> str:
        """Generate database.py with async PostgreSQL operations."""
        b = PythonCodeBuilder()

        b.docstring("Database operations for the MCP server.\n\nProvides async PostgreSQL access using asyncpg.")
        b.line()

        # Imports
        b.import_("os")
        b.import_("logging")
        b.import_("typing", ["Any", "Optional"])
        b.import_("asyncpg")
        b.line()
        b.line()

        b.line('logger = logging.getLogger(__name__)')
        b.line()
        b.line()

        with b.class_("Database"):
            b.docstring("Async database connection and operations.")
            b.line()

            with b.method("__init__"):
                b.docstring("Initialize database configuration from environment.")
                b.line('self.host = os.environ.get("DB_HOST", "localhost")')
                b.line('self.port = int(os.environ.get("DB_PORT", "5432"))')
                b.line(f'self.database = os.environ.get("DB_NAME", "{self.schema.database_name or "postgres"}")')
                b.line('self.user = os.environ.get("DB_USER", "postgres")')
                b.line('self.password = os.environ.get("DB_PASSWORD", "")')
                b.line('self.pool: Optional[asyncpg.Pool] = None')

            b.line()

            with b.method("connect", is_async=True):
                b.docstring("Create connection pool.")
                b.line("self.pool = await asyncpg.create_pool(")
                b.indent()
                b.line("host=self.host,")
                b.line("port=self.port,")
                b.line("database=self.database,")
                b.line("user=self.user,")
                b.line("password=self.password,")
                b.line("min_size=2,")
                b.line("max_size=10,")
                b.dedent()
                b.line(")")
                b.line('logger.info(f"Connected to database: {self.database}")')

            b.line()

            with b.method("disconnect", is_async=True):
                b.docstring("Close connection pool.")
                with b.if_("self.pool"):
                    b.line("await self.pool.close()")
                    b.line('logger.info("Disconnected from database")')

            b.line()

            with b.method("get_schema", is_async=True, returns="dict[str, Any]"):
                b.docstring("Get database schema information.")
                b.line("async with self.pool.acquire() as conn:")
                b.indent()
                b.comment("Get tables")
                b.line('tables = await conn.fetch("""')
                b.line("    SELECT table_name")
                b.line("    FROM information_schema.tables")
                b.line("    WHERE table_schema = 'public'")
                b.line("    ORDER BY table_name")
                b.line('""")')
                b.line()
                b.line("schema = {}")
                with b.for_("table", "tables"):
                    b.line('table_name = table["table_name"]')
                    b.line('columns = await conn.fetch("""')
                    b.line("    SELECT column_name, data_type, is_nullable, column_default")
                    b.line("    FROM information_schema.columns")
                    b.line("    WHERE table_schema = 'public' AND table_name = $1")
                    b.line("    ORDER BY ordinal_position")
                    b.line('""", table_name)')
                    b.line()
                    b.line("schema[table_name] = [")
                    b.indent()
                    b.line("{")
                    b.indent()
                    b.line('"name": col["column_name"],')
                    b.line('"type": col["data_type"],')
                    b.line('"nullable": col["is_nullable"] == "YES",')
                    b.line('"default": col["column_default"],')
                    b.dedent()
                    b.line("}")
                    b.line("for col in columns")
                    b.dedent()
                    b.line("]")
                b.dedent()
                b.return_("schema")

            b.line()

            with b.method("list_records", params=["table_name: str", "limit: int = 100", "offset: int = 0"], is_async=True, returns="list[dict[str, Any]]"):
                b.docstring("List records from a table with pagination.")
                b.comment("Validate table name to prevent SQL injection")
                b.line("table_name = self._validate_identifier(table_name)")
                b.line()
                b.line("async with self.pool.acquire() as conn:")
                b.indent()
                b.line('query = f"SELECT * FROM {table_name} LIMIT $1 OFFSET $2"')
                b.line("rows = await conn.fetch(query, limit, offset)")
                b.return_("[dict(row) for row in rows]")
                b.dedent()

            b.line()

            with b.method("get_record", params=["table_name: str", "pk_column: str", "pk_value: Any"], is_async=True, returns="Optional[dict[str, Any]]"):
                b.docstring("Get a single record by primary key.")
                b.line("table_name = self._validate_identifier(table_name)")
                b.line("pk_column = self._validate_identifier(pk_column)")
                b.line()
                b.line("async with self.pool.acquire() as conn:")
                b.indent()
                b.line('query = f"SELECT * FROM {table_name} WHERE {pk_column} = $1"')
                b.line("row = await conn.fetchrow(query, pk_value)")
                b.return_("dict(row) if row else None")
                b.dedent()

            b.line()

            with b.method("create_record", params=["table_name: str", "data: dict[str, Any]"], is_async=True, returns="dict[str, Any]"):
                b.docstring("Create a new record.")
                b.line("table_name = self._validate_identifier(table_name)")
                b.line("columns = [self._validate_identifier(k) for k in data.keys()]")
                b.line("values = list(data.values())")
                b.line()
                b.line('columns_str = ", ".join(columns)')
                b.line('placeholders = ", ".join(f"${i+1}" for i in range(len(values)))')
                b.line()
                b.line("async with self.pool.acquire() as conn:")
                b.indent()
                b.line('query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders}) RETURNING *"')
                b.line("row = await conn.fetchrow(query, *values)")
                b.return_("dict(row)")
                b.dedent()

            b.line()

            with b.method("update_record", params=["table_name: str", "pk_column: str", "pk_value: Any", "data: dict[str, Any]"], is_async=True, returns="Optional[dict[str, Any]]"):
                b.docstring("Update an existing record.")
                b.line("table_name = self._validate_identifier(table_name)")
                b.line("pk_column = self._validate_identifier(pk_column)")
                b.line()
                b.line("set_clauses = []")
                b.line("values = []")
                with b.for_("i, (key, value)", "enumerate(data.items())"):
                    b.line("col = self._validate_identifier(key)")
                    b.line('set_clauses.append(f"{col} = ${i+1}")')
                    b.line("values.append(value)")
                b.line()
                b.line("values.append(pk_value)")
                b.line('set_str = ", ".join(set_clauses)')
                b.line()
                b.line("async with self.pool.acquire() as conn:")
                b.indent()
                b.line('query = f"UPDATE {table_name} SET {set_str} WHERE {pk_column} = ${len(values)} RETURNING *"')
                b.line("row = await conn.fetchrow(query, *values)")
                b.return_("dict(row) if row else None")
                b.dedent()

            b.line()

            with b.method("delete_record", params=["table_name: str", "pk_column: str", "pk_value: Any"], is_async=True, returns="bool"):
                b.docstring("Delete a record.")
                b.line("table_name = self._validate_identifier(table_name)")
                b.line("pk_column = self._validate_identifier(pk_column)")
                b.line()
                b.line("async with self.pool.acquire() as conn:")
                b.indent()
                b.line('query = f"DELETE FROM {table_name} WHERE {pk_column} = $1"')
                b.line("result = await conn.execute(query, pk_value)")
                b.return_('"DELETE 1" in result')
                b.dedent()

            b.line()

            with b.method("_validate_identifier", params=["name: str"], returns="str"):
                b.docstring("Validate SQL identifier to prevent injection.")
                b.line('import re')
                b.line('if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):')
                b.indent()
                b.line('raise ValueError(f"Invalid identifier: {name}")')
                b.dedent()
                b.return_("name")

        return b.build()

    def _generate_pyproject(self) -> str:
        """Generate pyproject.toml."""
        return f'''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{self.server_name}"
version = "1.0.0"
description = "MCP server for PostgreSQL database access"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0.0",
    "asyncpg>=0.29.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
{self.server_name} = "server:main"
'''

    def _generate_readme(self) -> str:
        """Generate README.md."""
        tables = self.schema.get_non_through_tables()
        table_list = "\n".join(f"- `{t.name}` ({t.model_name})" for t in tables if t.primary_key_columns)

        return f'''# {self.server_name}

MCP Server for PostgreSQL database access.

## Overview

This MCP server provides AI assistants with direct access to your PostgreSQL database,
exposing CRUD operations for all tables as tools.

## Tables

{table_list}

## Tools

For each table, the following tools are available:

- `list_{{table}}` - List records with pagination
- `get_{{table}}` - Get a single record by primary key
- `create_{{table}}` - Create a new record
- `update_{{table}}` - Update an existing record
- `delete_{{table}}` - Delete a record

Additional tools:
- `describe_schema` - Get the database schema information

## Resources

- `schema://tables` - Complete database schema
- `data://{{table_name}}` - Data from a specific table

## Installation

```bash
pip install -e .
```

## Configuration

Set the following environment variables:

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=your_database
export DB_USER=postgres
export DB_PASSWORD=your_password
```

## Usage

```bash
python server.py
```

Or run as a module:

```bash
python -m {self.server_name.replace("-", "_")}
```

## Claude Desktop Integration

Add to your Claude Desktop configuration:

```json
{{
  "mcpServers": {{
    "{self.server_name}": {{
      "command": "python",
      "args": ["/path/to/server.py"],
      "env": {{
        "DB_HOST": "localhost",
        "DB_NAME": "{self.schema.database_name or 'your_database'}"
      }}
    }}
  }}
}}
```
'''


# Need to import json for the tool definitions
import json
