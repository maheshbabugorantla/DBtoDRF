"""
Tests for the new CodeGen V2 system.

These tests verify that the new CodeBuilder-based code generation
produces valid, correctly formatted Python code.
"""

import pytest
from drf_auto_generator.codegen_v2 import (
    PythonCodeBuilder,
    DatabaseSchema,
    TableSchema,
    ColumnSchema,
    RelationshipSchema,
    IndexSchema,
    FieldType,
    RelationshipType,
)
from drf_auto_generator.codegen_v2.django import (
    DjangoGenerator,
    ModelsGenerator,
    SerializersGenerator,
    ViewsGenerator,
)
from drf_auto_generator.codegen_v2.mcp import MCPServerGenerator


class TestPythonCodeBuilder:
    """Tests for the PythonCodeBuilder utility."""

    def test_simple_line(self):
        """Test adding simple lines."""
        b = PythonCodeBuilder()
        b.line("x = 1")
        b.line("y = 2")
        assert str(b) == "x = 1\ny = 2"

    def test_blank_lines(self):
        """Test adding blank lines."""
        b = PythonCodeBuilder()
        b.line("x = 1")
        b.line()
        b.line("y = 2")
        assert str(b) == "x = 1\n\ny = 2"

    def test_indentation(self):
        """Test manual indentation."""
        b = PythonCodeBuilder()
        b.line("if True:")
        b.indent()
        b.line("print('yes')")
        b.dedent()
        b.line("print('done')")

        expected = "if True:\n    print('yes')\nprint('done')"
        assert str(b) == expected

    def test_block_context_manager(self):
        """Test block context manager."""
        b = PythonCodeBuilder()
        with b.block("if x > 0:"):
            b.line("print('positive')")
        b.line("print('done')")

        expected = "if x > 0:\n    print('positive')\nprint('done')"
        assert str(b) == expected

    def test_class_context_manager(self):
        """Test class context manager."""
        b = PythonCodeBuilder()
        with b.class_("MyClass", bases=["Base"]):
            b.line("x = 1")

        code = str(b)
        assert "class MyClass(Base):" in code
        assert "    x = 1" in code

    def test_function_context_manager(self):
        """Test function context manager."""
        b = PythonCodeBuilder()
        with b.function("add", params=["a", "b"], returns="int"):
            b.return_("a + b")

        code = str(b)
        assert "def add(a, b) -> int:" in code
        assert "    return a + b" in code

    def test_method_context_manager(self):
        """Test method context manager with self."""
        b = PythonCodeBuilder()
        with b.class_("MyClass"):
            with b.method("get_name", returns="str"):
                b.return_("self.name")

        code = str(b)
        assert "def get_name(self) -> str:" in code

    def test_nested_blocks(self):
        """Test nested blocks."""
        b = PythonCodeBuilder()
        with b.class_("Outer"):
            with b.method("do_something"):
                with b.if_("self.ready"):
                    b.line("self.execute()")

        code = str(b)
        assert "class Outer:" in code
        assert "    def do_something(self):" in code
        assert "        if self.ready:" in code
        assert "            self.execute()" in code

    def test_import(self):
        """Test import generation."""
        b = PythonCodeBuilder()
        b.import_("os")
        b.import_("django.db", ["models"])

        code = str(b)
        assert "import os" in code
        assert "from django.db import models" in code

    def test_build_validates_syntax(self):
        """Test that build() validates Python syntax."""
        b = PythonCodeBuilder()
        b.line("def broken(")  # Invalid syntax

        with pytest.raises(SyntaxError):
            b.build(validate=True)

    def test_repr_value(self):
        """Test value representation."""
        assert PythonCodeBuilder.repr_value("hello") == "'hello'"
        assert PythonCodeBuilder.repr_value(42) == "42"
        assert PythonCodeBuilder.repr_value(True) == "True"
        assert PythonCodeBuilder.repr_value(None) == "None"
        assert PythonCodeBuilder.repr_value([1, 2]) == "[1, 2]"


class TestSchemaModels:
    """Tests for the Pydantic schema models."""

    def test_column_schema(self):
        """Test ColumnSchema creation."""
        col = ColumnSchema(
            name="email",
            field_type=FieldType.EMAIL,
            nullable=False,
            unique=True,
            max_length=255,
        )
        assert col.name == "email"
        assert col.field_type == FieldType.EMAIL
        assert col.unique is True

    def test_column_get_field_options(self):
        """Test ColumnSchema.get_field_options()."""
        col = ColumnSchema(
            name="name",
            field_type=FieldType.CHAR,
            nullable=True,
            max_length=100,
        )
        options = col.get_field_options()

        assert options["null"] is True
        assert options["blank"] is True
        assert options["max_length"] == 100

    def test_table_schema_model_name_generation(self):
        """Test automatic model name generation."""
        table = TableSchema(name="user_profiles")
        # Should singularize and PascalCase
        assert table.model_name in ("UserProfile", "UserProfiles")

    def test_table_has_composite_pk(self):
        """Test composite PK detection."""
        table = TableSchema(
            name="order_items",
            primary_key_columns=["order_id", "product_id"],
        )
        assert table.has_composite_pk is True

        single_pk = TableSchema(
            name="users",
            primary_key_columns=["id"],
        )
        assert single_pk.has_composite_pk is False

    def test_relationship_schema(self):
        """Test RelationshipSchema creation."""
        rel = RelationshipSchema(
            name="author",
            type=RelationshipType.MANY_TO_ONE,
            target_table="users",
            on_delete="CASCADE",
        )
        assert rel.django_field_type == "ForeignKey"

    def test_database_schema_yaml_roundtrip(self):
        """Test YAML serialization and deserialization."""
        schema = DatabaseSchema(
            tables=[
                TableSchema(
                    name="users",
                    primary_key_columns=["id"],
                    columns=[
                        ColumnSchema(name="id", field_type=FieldType.AUTO, primary_key=True),
                        ColumnSchema(name="name", field_type=FieldType.CHAR, max_length=100),
                    ],
                )
            ],
            project_name="test_project",
            app_name="api",
        )

        yaml_str = schema.to_yaml()
        assert "users" in yaml_str
        assert "test_project" in yaml_str

        # Round-trip
        loaded = DatabaseSchema.from_yaml(yaml_str)
        assert len(loaded.tables) == 1
        assert loaded.tables[0].name == "users"


class TestDjangoGenerator:
    """Tests for Django code generation."""

    @pytest.fixture
    def sample_schema(self):
        """Create a sample database schema for testing."""
        return DatabaseSchema(
            tables=[
                TableSchema(
                    name="users",
                    model_name="User",
                    primary_key_columns=["id"],
                    columns=[
                        ColumnSchema(name="id", field_type=FieldType.AUTO, primary_key=True),
                        ColumnSchema(name="email", field_type=FieldType.EMAIL, unique=True, max_length=255),
                        ColumnSchema(name="name", field_type=FieldType.CHAR, max_length=100, nullable=True),
                    ],
                ),
                TableSchema(
                    name="posts",
                    model_name="Post",
                    primary_key_columns=["id"],
                    columns=[
                        ColumnSchema(name="id", field_type=FieldType.AUTO, primary_key=True),
                        ColumnSchema(name="title", field_type=FieldType.CHAR, max_length=200),
                        ColumnSchema(name="content", field_type=FieldType.TEXT, nullable=True),
                    ],
                    relationships=[
                        RelationshipSchema(
                            name="author",
                            type=RelationshipType.MANY_TO_ONE,
                            target_table="users",
                            target_model="User",
                            source_column="author_id",
                            on_delete="CASCADE",
                        ),
                    ],
                ),
            ],
            project_name="blog",
            app_name="core",
        )

    def test_models_generator(self, sample_schema):
        """Test models.py generation."""
        generator = ModelsGenerator(sample_schema)
        code = generator.generate()

        # Should be valid Python
        import ast
        ast.parse(code)

        # Check content
        assert "from django.db import models" in code
        assert "class User(models.Model):" in code
        assert "class Post(models.Model):" in code
        assert "models.EmailField" in code
        assert "models.ForeignKey" in code

    def test_serializers_generator(self, sample_schema):
        """Test serializers.py generation."""
        generator = SerializersGenerator(sample_schema)
        code = generator.generate()

        # Should be valid Python
        import ast
        ast.parse(code)

        # Check content
        assert "from rest_framework import serializers" in code
        assert "class UserSerializer(serializers.ModelSerializer):" in code
        assert "class PostSerializer(serializers.ModelSerializer):" in code

    def test_views_generator(self, sample_schema):
        """Test views.py generation."""
        generator = ViewsGenerator(sample_schema)
        code = generator.generate()

        # Should be valid Python
        import ast
        ast.parse(code)

        # Check content
        assert "viewsets.ModelViewSet" in code
        assert "class UserViewSet" in code
        assert "class PostViewSet" in code
        assert "DjangoFilterBackend" in code

    def test_full_django_generator(self, sample_schema):
        """Test full Django project generation."""
        generator = DjangoGenerator(sample_schema)
        files = generator.generate()

        # Should generate all expected files
        assert "core/models.py" in files
        assert "core/serializers.py" in files
        assert "core/views.py" in files
        assert "core/urls.py" in files
        assert "core/admin.py" in files
        assert "blog/settings.py" in files
        assert "manage.py" in files

        # All files should be valid Python (except .txt, .md, .env)
        import ast
        for path, content in files.items():
            if path.endswith('.py'):
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    pytest.fail(f"Invalid Python in {path}: {e}")


class TestMCPGenerator:
    """Tests for MCP server generation."""

    @pytest.fixture
    def sample_schema(self):
        """Create a sample database schema for testing."""
        return DatabaseSchema(
            tables=[
                TableSchema(
                    name="users",
                    model_name="User",
                    primary_key_columns=["id"],
                    columns=[
                        ColumnSchema(name="id", field_type=FieldType.AUTO, primary_key=True),
                        ColumnSchema(name="name", field_type=FieldType.CHAR, max_length=100),
                    ],
                ),
            ],
            database_name="testdb",
            project_name="test",
            app_name="api",
        )

    def test_mcp_generator(self, sample_schema):
        """Test MCP server generation."""
        generator = MCPServerGenerator(sample_schema)
        files = generator.generate()

        # Should generate expected files
        assert "server.py" in files
        assert "tools.py" in files
        assert "resources.py" in files
        assert "database.py" in files
        assert "pyproject.toml" in files
        assert "README.md" in files

        # Python files should be valid
        import ast
        for path, content in files.items():
            if path.endswith('.py'):
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    pytest.fail(f"Invalid Python in {path}: {e}")

        # Check MCP-specific content
        assert "mcp.server" in files["server.py"]
        assert "list_users" in files["tools.py"]
        assert "asyncpg" in files["database.py"]


class TestToolboxGenerator:
    """Tests for Google MCP Toolbox configuration generation."""

    @pytest.fixture
    def sample_schema(self):
        """Create a sample database schema for testing."""
        return DatabaseSchema(
            tables=[
                TableSchema(
                    name="users",
                    model_name="User",
                    primary_key_columns=["id"],
                    columns=[
                        ColumnSchema(name="id", field_type=FieldType.AUTO, primary_key=True),
                        ColumnSchema(name="email", field_type=FieldType.EMAIL, max_length=255),
                        ColumnSchema(name="name", field_type=FieldType.CHAR, max_length=100),
                    ],
                ),
                TableSchema(
                    name="posts",
                    model_name="Post",
                    primary_key_columns=["id"],
                    columns=[
                        ColumnSchema(name="id", field_type=FieldType.AUTO, primary_key=True),
                        ColumnSchema(name="title", field_type=FieldType.CHAR, max_length=200),
                        ColumnSchema(name="content", field_type=FieldType.TEXT, nullable=True),
                    ],
                ),
            ],
            database_name="testdb",
            project_name="test",
            app_name="api",
        )

    def test_toolbox_generator(self, sample_schema):
        """Test Toolbox configuration generation."""
        from drf_auto_generator.codegen_v2.toolbox import ToolboxGenerator

        generator = ToolboxGenerator(sample_schema)
        files = generator.generate()

        # Should generate expected files
        assert "tools.yaml" in files
        assert ".env.example" in files
        assert "README.md" in files
        assert "docker-compose.yaml" in files

    def test_toolbox_yaml_structure(self, sample_schema):
        """Test the structure of generated tools.yaml."""
        import yaml
        from drf_auto_generator.codegen_v2.toolbox import ToolboxGenerator

        generator = ToolboxGenerator(sample_schema)
        files = generator.generate()

        # Parse the YAML
        config = yaml.safe_load(files["tools.yaml"])

        # Check sources section
        assert "sources" in config
        assert "main-db" in config["sources"]
        assert config["sources"]["main-db"]["kind"] == "postgres"

        # Check tools section
        assert "tools" in config
        tools = config["tools"]

        # Should have CRUD tools for each table
        assert "list_users" in tools
        assert "get_users" in tools
        assert "search_users" in tools
        assert "create_users" in tools
        assert "update_users" in tools
        assert "delete_users" in tools

        assert "list_posts" in tools
        assert "get_posts" in tools

        # Check tool structure
        list_tool = tools["list_users"]
        assert list_tool["kind"] == "postgres-sql"
        assert "source" in list_tool
        assert "description" in list_tool
        assert "parameters" in list_tool
        assert "statement" in list_tool

        # Check toolsets section
        assert "toolsets" in config
        assert "read_only" in config["toolsets"]
        assert "full_crud" in config["toolsets"]
        assert "users_tools" in config["toolsets"]
        assert "posts_tools" in config["toolsets"]

    def test_toolbox_search_tools(self, sample_schema):
        """Test that search tools are generated for tables with text fields."""
        import yaml
        from drf_auto_generator.codegen_v2.toolbox import ToolboxGenerator

        generator = ToolboxGenerator(sample_schema)
        files = generator.generate()
        config = yaml.safe_load(files["tools.yaml"])

        # Users has email and name (text fields) - should have search
        assert "search_users" in config["tools"]
        search_tool = config["tools"]["search_users"]
        assert "ILIKE" in search_tool["statement"]

        # Posts has title and content - should have search
        assert "search_posts" in config["tools"]

    def test_toolbox_mysql_support(self, sample_schema):
        """Test MySQL database kind support."""
        import yaml
        from drf_auto_generator.codegen_v2.toolbox import ToolboxGenerator

        generator = ToolboxGenerator(sample_schema, config={"db_kind": "mysql"})
        files = generator.generate()
        config = yaml.safe_load(files["tools.yaml"])

        # Should use mysql kind
        assert config["sources"]["main-db"]["kind"] == "mysql"

        # Tools should use mysql-sql kind
        assert config["tools"]["list_users"]["kind"] == "mysql-sql"

    def test_toolbox_env_example(self, sample_schema):
        """Test .env.example generation."""
        from drf_auto_generator.codegen_v2.toolbox import ToolboxGenerator

        generator = ToolboxGenerator(sample_schema)
        files = generator.generate()

        env_content = files[".env.example"]
        assert "DB_HOST" in env_content
        assert "DB_PORT" in env_content
        assert "DB_NAME" in env_content
        assert "DB_USER" in env_content
        assert "DB_PASSWORD" in env_content

    def test_toolbox_readme_content(self, sample_schema):
        """Test README.md content."""
        from drf_auto_generator.codegen_v2.toolbox import ToolboxGenerator

        generator = ToolboxGenerator(sample_schema)
        files = generator.generate()

        readme = files["README.md"]
        assert "MCP Toolbox" in readme
        assert "users" in readme
        assert "posts" in readme
        assert "Claude Desktop" in readme
        assert "docker" in readme.lower()

    def test_toolbox_index_filter_tools(self):
        """Test that filter tools are generated for indexed columns."""
        import yaml
        from drf_auto_generator.codegen_v2.toolbox import ToolboxGenerator

        # Create schema with indexes
        schema = DatabaseSchema(
            tables=[
                TableSchema(
                    name="orders",
                    model_name="Order",
                    primary_key_columns=["order_id"],
                    columns=[
                        ColumnSchema(name="order_id", field_type=FieldType.AUTO, primary_key=True),
                        ColumnSchema(name="customer_id", field_type=FieldType.INTEGER),
                        ColumnSchema(name="status", field_type=FieldType.CHAR, max_length=20),
                        ColumnSchema(name="order_date", field_type=FieldType.DATE),
                        ColumnSchema(name="total", field_type=FieldType.DECIMAL),
                    ],
                    indexes=[
                        IndexSchema(name="idx_orders_customer", fields=["customer_id"]),
                        IndexSchema(name="idx_orders_status", fields=["status"]),
                        IndexSchema(name="idx_orders_date_status", fields=["order_date", "status"]),
                    ],
                ),
            ],
            database_name="testdb",
            project_name="test",
            app_name="api",
        )

        generator = ToolboxGenerator(schema)
        files = generator.generate()
        config = yaml.safe_load(files["tools.yaml"])
        tools = config["tools"]

        # Should have filter tools for indexed columns
        assert "filter_orders_by_customer_id" in tools
        assert "filter_orders_by_status" in tools
        assert "filter_orders_by_order_date_and_status" in tools

        # Check filter tool structure
        filter_tool = tools["filter_orders_by_customer_id"]
        assert filter_tool["kind"] == "postgres-sql"
        assert "WHERE customer_id = $1" in filter_tool["statement"]
        assert "(indexed for fast lookup)" in filter_tool["description"]

        # Check composite index filter tool
        composite_tool = tools["filter_orders_by_order_date_and_status"]
        assert "WHERE order_date = $1 AND status = $2" in composite_tool["statement"]
        assert "(composite index" in composite_tool["description"]

        # Filter tools should be in read_only toolset
        assert "filter_orders_by_customer_id" in config["toolsets"]["read_only"]
        assert "filter_orders_by_status" in config["toolsets"]["read_only"]

    def test_toolbox_foreign_key_filter_tools(self):
        """Test that filter tools are generated for foreign key columns."""
        import yaml
        from drf_auto_generator.codegen_v2.toolbox import ToolboxGenerator

        schema = DatabaseSchema(
            tables=[
                TableSchema(
                    name="rentals",
                    model_name="Rental",
                    primary_key_columns=["rental_id"],
                    columns=[
                        ColumnSchema(name="rental_id", field_type=FieldType.AUTO, primary_key=True),
                        ColumnSchema(name="film_id", field_type=FieldType.INTEGER),
                        ColumnSchema(name="customer_id", field_type=FieldType.INTEGER),
                        ColumnSchema(name="rental_date", field_type=FieldType.DATETIME),
                    ],
                    relationships=[
                        RelationshipSchema(
                            name="film",
                            type=RelationshipType.MANY_TO_ONE,
                            target_table="films",
                            source_column="film_id",
                        ),
                        RelationshipSchema(
                            name="customer",
                            type=RelationshipType.MANY_TO_ONE,
                            target_table="customers",
                            source_column="customer_id",
                        ),
                    ],
                ),
            ],
            database_name="testdb",
            project_name="test",
            app_name="api",
        )

        generator = ToolboxGenerator(schema)
        files = generator.generate()
        config = yaml.safe_load(files["tools.yaml"])
        tools = config["tools"]

        # Should have filter tools for FK columns
        assert "filter_rentals_by_film_id" in tools
        assert "filter_rentals_by_customer_id" in tools

        # Check FK filter tool structure
        film_filter = tools["filter_rentals_by_film_id"]
        assert "(foreign key to films)" in film_filter["description"]
        assert "WHERE film_id = $1" in film_filter["statement"]
