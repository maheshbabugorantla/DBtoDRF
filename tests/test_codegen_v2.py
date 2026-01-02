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
