import unittest
from unittest.mock import Mock, patch, MagicMock
import ast
from typing import List

from drf_auto_generator.ast_codegen.serializers import (
    _is_m2m_through_table,
    create_serializer_meta,
    create_serializer_class,
    generate_serializers_ast,
    generate_serializers_code
)
from drf_auto_generator.introspection_django import TableInfo, ColumnInfo


class TestIsM2MThroughTable(unittest.TestCase):
    """Test cases for _is_m2m_through_table function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_table = Mock(spec=TableInfo)

    def test_not_m2m_through_table_wrong_pk_count(self):
        """Test table with wrong primary key count is not M2M through table."""
        self.mock_table.primary_key_columns = ["id"]  # Only 1 PK
        self.mock_table.relationships = []

        result = _is_m2m_through_table(self.mock_table)
        self.assertFalse(result)

    def test_not_m2m_through_table_wrong_fk_count(self):
        """Test table with wrong foreign key count is not M2M through table."""
        self.mock_table.primary_key_columns = ["user_id", "role_id"]  # 2 PKs
        self.mock_table.relationships = [
            {"type": "many-to-one", "source_columns": ["user_id"]}
        ]  # Only 1 FK

        result = _is_m2m_through_table(self.mock_table)
        self.assertFalse(result)

    def test_not_m2m_through_table_pk_not_handled_by_fk(self):
        """Test table where PK columns are not handled by FK relationships."""
        self.mock_table.primary_key_columns = ["user_id", "role_id"]
        self.mock_table.relationships = [
            {"type": "many-to-one", "source_columns": ["user_id"]},
            {"type": "many-to-one", "source_columns": ["other_id"]}  # Doesn't match PK
        ]

        result = _is_m2m_through_table(self.mock_table)
        self.assertFalse(result)

    def test_is_m2m_through_table_valid(self):
        """Test valid M2M through table."""
        self.mock_table.primary_key_columns = ["user_id", "role_id"]
        self.mock_table.relationships = [
            {"type": "many-to-one", "source_columns": ["user_id"]},
            {"type": "many-to-one", "source_columns": ["role_id"]}
        ]

        result = _is_m2m_through_table(self.mock_table)
        self.assertTrue(result)

    def test_not_m2m_through_table_different_relationship_types(self):
        """Test table with different relationship types."""
        self.mock_table.primary_key_columns = ["user_id", "role_id"]
        self.mock_table.relationships = [
            {"type": "many-to-one", "source_columns": ["user_id"]},
            {"type": "many-to-many", "source_columns": ["role_id"]}  # Wrong type
        ]

        result = _is_m2m_through_table(self.mock_table)
        self.assertFalse(result)

    def test_not_m2m_through_table_missing_source_columns(self):
        """Test table with relationships missing source_columns."""
        self.mock_table.primary_key_columns = ["user_id", "role_id"]
        self.mock_table.relationships = [
            {"type": "many-to-one", "source_columns": ["user_id"]},
            {"type": "many-to-one"}  # Missing source_columns
        ]

        result = _is_m2m_through_table(self.mock_table)
        self.assertFalse(result)


class TestCreateSerializerMeta(unittest.TestCase):
    """Test cases for create_serializer_meta function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_table = Mock(spec=TableInfo)
        self.mock_table.name = "user"

    @patch('drf_auto_generator.ast_codegen.serializers.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.serializers.pluralize')
    @patch('drf_auto_generator.ast_codegen.serializers.create_meta_class')
    @patch('drf_auto_generator.ast_codegen.serializers.create_string_constant')
    def test_create_serializer_meta(self, mock_create_string, mock_create_meta, mock_pluralize, mock_to_pascal):
        """Test creating serializer meta class."""
        mock_pluralize.return_value = "users"
        mock_to_pascal.return_value = "Users"
        mock_create_string.return_value = Mock()
        mock_create_meta.return_value = Mock()

        result = create_serializer_meta(self.mock_table)

        # Verify function calls
        mock_pluralize.assert_called_once_with("user")
        mock_to_pascal.assert_called_once_with("users")
        mock_create_string.assert_called_once_with("__all__")
        mock_create_meta.assert_called_once()

        # Verify meta options structure
        call_args = mock_create_meta.call_args[0][0]
        self.assertEqual(len(call_args), 2)
        self.assertEqual(call_args[0][0], "model")
        self.assertEqual(call_args[1][0], "fields")

        # Verify model reference is an ast.Name with correct id
        model_ast = call_args[0][1]
        self.assertIsInstance(model_ast, ast.Name)
        self.assertEqual(model_ast.id, "Users")
        self.assertIsInstance(model_ast.ctx, ast.Load)

        self.assertEqual(result, mock_create_meta.return_value)


class TestCreateSerializerClass(unittest.TestCase):
    """Test cases for create_serializer_class function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_table = Mock(spec=TableInfo)
        self.mock_table.name = "product"

    @patch('drf_auto_generator.ast_codegen.serializers.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.serializers.pluralize')
    @patch('drf_auto_generator.ast_codegen.serializers.create_class_def')
    @patch('drf_auto_generator.ast_codegen.serializers.create_serializer_meta')
    def test_create_serializer_class(self, mock_create_meta, mock_create_class, mock_pluralize, mock_to_pascal):
        """Test creating serializer class."""
        mock_pluralize.return_value = "products"
        mock_to_pascal.return_value = "Products"
        mock_meta = Mock()
        mock_create_meta.return_value = mock_meta
        mock_create_class.return_value = Mock()

        result = create_serializer_class(self.mock_table)

        # Verify function calls
        mock_pluralize.assert_called_once_with("product")
        mock_to_pascal.assert_called_once_with("products")
        mock_create_meta.assert_called_once_with(self.mock_table)
        mock_create_class.assert_called_once()

        # Verify class definition parameters
        call_args = mock_create_class.call_args
        self.assertEqual(call_args[1]["name"], "ProductsSerializer")
        self.assertEqual(call_args[1]["bases"], ["serializers.ModelSerializer"])
        self.assertEqual(call_args[1]["body"], [mock_meta])

        self.assertEqual(result, mock_create_class.return_value)


class TestGenerateSerializersAst(unittest.TestCase):
    """Test cases for generate_serializers_ast function."""

    def setUp(self):
        """Set up test fixtures."""
        # Regular table with primary key
        self.mock_table1 = Mock(spec=TableInfo)
        self.mock_table1.name = "user"
        self.mock_table1.primary_key_columns = ["id"]

        # Table without primary key
        self.mock_table2 = Mock(spec=TableInfo)
        self.mock_table2.name = "view_table"
        self.mock_table2.primary_key_columns = []

        # M2M through table
        self.mock_table3 = Mock(spec=TableInfo)
        self.mock_table3.name = "user_role"
        self.mock_table3.primary_key_columns = ["user_id", "role_id"]
        self.mock_table3.relationships = [
            {"type": "many-to-one", "source_columns": ["user_id"]},
            {"type": "many-to-one", "source_columns": ["role_id"]}
        ]

        # Another regular table
        self.mock_table4 = Mock(spec=TableInfo)
        self.mock_table4.name = "product"
        self.mock_table4.primary_key_columns = ["id"]

    @patch('drf_auto_generator.ast_codegen.serializers.logger')
    @patch('drf_auto_generator.ast_codegen.serializers.create_serializer_class')
    @patch('drf_auto_generator.ast_codegen.serializers.create_import')
    @patch('drf_auto_generator.ast_codegen.serializers.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.serializers.pluralize')
    @patch('drf_auto_generator.ast_codegen.serializers._is_m2m_through_table')
    def test_generate_serializers_ast_with_mixed_tables(self, mock_is_m2m, mock_pluralize, mock_to_pascal,
                                                       mock_create_import, mock_create_class, mock_logger):
        """Test generating serializers AST with mixed table types."""
        # Setup mocks
        mock_is_m2m.side_effect = lambda table: table.name == "user_role"
        mock_pluralize.side_effect = lambda name: f"{name}s"
        mock_to_pascal.side_effect = lambda name: name.title()

        mock_import1 = Mock()
        mock_import2 = Mock()
        mock_create_import.side_effect = [mock_import1, mock_import2]

        mock_serializer1 = Mock()
        mock_serializer2 = Mock()
        mock_create_class.side_effect = [mock_serializer1, mock_serializer2]

        tables = [self.mock_table1, self.mock_table2, self.mock_table3, self.mock_table4]

        result = generate_serializers_ast(tables, ".models")

        # Verify imports were created
        self.assertEqual(mock_create_import.call_count, 2)

        # Verify first import (rest_framework.serializers)
        call_args1 = mock_create_import.call_args_list[0]
        self.assertEqual(call_args1[0], ("rest_framework", ["serializers"]))

        # Verify second import (models import, excluding M2M through tables and tables without PKs)
        call_args2 = mock_create_import.call_args_list[1]
        self.assertEqual(call_args2[0][0], ".models")
        imported_models = call_args2[0][1]
        self.assertIn("Users", imported_models)
        self.assertIn("Products", imported_models)
        self.assertNotIn("User_roles", imported_models)  # M2M through table excluded
        self.assertNotIn("View_tables", imported_models)  # No PK table excluded

        # Verify serializer classes were created for valid tables only
        self.assertEqual(mock_create_class.call_count, 2)
        mock_create_class.assert_any_call(self.mock_table1)
        mock_create_class.assert_any_call(self.mock_table4)

        # Verify logger messages
        mock_logger.info.assert_called_once_with("Skipping serializer generation for M2M through table: user_role")
        mock_logger.warning.assert_called_once_with("Table view_table does not have a primary key, skipping serializer generation...")

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)
        self.assertEqual(len(result.body), 4)  # 2 imports + 2 serializer classes
        self.assertEqual(result.body[0], mock_import1)
        self.assertEqual(result.body[1], mock_import2)
        self.assertEqual(result.body[2], mock_serializer1)
        self.assertEqual(result.body[3], mock_serializer2)
        self.assertEqual(result.type_ignores, [])

    @patch('drf_auto_generator.ast_codegen.serializers.create_import')
    @patch('drf_auto_generator.ast_codegen.serializers.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.serializers.pluralize')
    @patch('drf_auto_generator.ast_codegen.serializers._is_m2m_through_table')
    def test_generate_serializers_ast_empty_tables(self, mock_is_m2m, mock_pluralize, mock_to_pascal, mock_create_import):
        """Test generating serializers AST with empty table list."""
        mock_is_m2m.return_value = False
        mock_pluralize.return_value = ""
        mock_to_pascal.return_value = ""

        mock_import1 = Mock()
        mock_import2 = Mock()
        mock_create_import.side_effect = [mock_import1, mock_import2]

        result = generate_serializers_ast([], ".models")

        # Verify imports were still created
        self.assertEqual(mock_create_import.call_count, 2)

        # Verify AST module structure with only imports
        self.assertIsInstance(result, ast.Module)
        self.assertEqual(len(result.body), 2)  # Only imports
        self.assertEqual(result.body[0], mock_import1)
        self.assertEqual(result.body[1], mock_import2)

    @patch('drf_auto_generator.ast_codegen.serializers.create_serializer_class')
    @patch('drf_auto_generator.ast_codegen.serializers.create_import')
    @patch('drf_auto_generator.ast_codegen.serializers.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.serializers.pluralize')
    @patch('drf_auto_generator.ast_codegen.serializers._is_m2m_through_table')
    def test_generate_serializers_ast_custom_models_module(self, mock_is_m2m, mock_pluralize, mock_to_pascal,
                                                          mock_create_import, mock_create_class):
        """Test generating serializers AST with custom models module."""
        mock_is_m2m.return_value = False
        mock_pluralize.return_value = "users"
        mock_to_pascal.return_value = "Users"

        mock_import1 = Mock()
        mock_import2 = Mock()
        mock_create_import.side_effect = [mock_import1, mock_import2]
        mock_create_class.return_value = Mock()

        result = generate_serializers_ast([self.mock_table1], "myapp.models")

        # Verify second import uses custom module
        call_args2 = mock_create_import.call_args_list[1]
        self.assertEqual(call_args2[0][0], "myapp.models")

        self.assertIsInstance(result, ast.Module)

    @patch('drf_auto_generator.ast_codegen.serializers.logger')
    @patch('drf_auto_generator.ast_codegen.serializers.create_import')
    @patch('drf_auto_generator.ast_codegen.serializers.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.serializers.pluralize')
    @patch('drf_auto_generator.ast_codegen.serializers._is_m2m_through_table')
    def test_generate_serializers_ast_only_invalid_tables(self, mock_is_m2m, mock_pluralize, mock_to_pascal,
                                                         mock_create_import, mock_logger):
        """Test generating serializers AST with only invalid tables."""
        mock_is_m2m.return_value = True  # All tables are M2M through tables
        mock_pluralize.return_value = "users"
        mock_to_pascal.return_value = "Users"

        mock_import1 = Mock()
        mock_import2 = Mock()
        mock_create_import.side_effect = [mock_import1, mock_import2]

        result = generate_serializers_ast([self.mock_table3], ".models")

        # Verify logger was called
        mock_logger.info.assert_called_once_with("Skipping serializer generation for M2M through table: user_role")

        # Verify AST module structure with only imports
        self.assertIsInstance(result, ast.Module)
        self.assertEqual(len(result.body), 2)  # Only imports, no serializer classes


class TestGenerateSerializersCode(unittest.TestCase):
    """Test cases for generate_serializers_code function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_table = Mock(spec=TableInfo)
        self.mock_table.name = "user"
        self.mock_table.primary_key_columns = ["id"]

    @patch('drf_auto_generator.ast_codegen.serializers.generate_serializers_ast')
    @patch('ast.unparse')
    def test_generate_serializers_code(self, mock_unparse, mock_generate_ast):
        """Test generating serializers code."""
        mock_ast_module = Mock()
        mock_generate_ast.return_value = mock_ast_module
        mock_unparse.return_value = "generated_code"

        result = generate_serializers_code([self.mock_table], ".models")

        # Verify AST generation was called
        mock_generate_ast.assert_called_once_with([self.mock_table], ".models")

        # Verify unparse was called with the AST
        mock_unparse.assert_called_once_with(mock_ast_module)

        # Verify result
        self.assertEqual(result, "generated_code")

    @patch('drf_auto_generator.ast_codegen.serializers.generate_serializers_ast')
    @patch('ast.unparse')
    def test_generate_serializers_code_custom_module(self, mock_unparse, mock_generate_ast):
        """Test generating serializers code with custom models module."""
        mock_ast_module = Mock()
        mock_generate_ast.return_value = mock_ast_module
        mock_unparse.return_value = "custom_generated_code"

        result = generate_serializers_code([self.mock_table], "custom.models")

        # Verify AST generation was called with custom module
        mock_generate_ast.assert_called_once_with([self.mock_table], "custom.models")

        # Verify result
        self.assertEqual(result, "custom_generated_code")


class TestIntegrationScenarios(unittest.TestCase):
    """Integration test scenarios for complex table configurations."""

    def create_mock_table(self, name: str, pk_columns: List[str], relationships: List[dict] = None) -> Mock:
        """Helper to create mock table with specified configuration."""
        mock_table = Mock(spec=TableInfo)
        mock_table.name = name
        mock_table.primary_key_columns = pk_columns
        mock_table.relationships = relationships or []
        return mock_table

    @patch('drf_auto_generator.ast_codegen.serializers.logger')
    @patch('drf_auto_generator.ast_codegen.serializers.create_serializer_class')
    @patch('drf_auto_generator.ast_codegen.serializers.create_import')
    @patch('drf_auto_generator.ast_codegen.serializers.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.serializers.pluralize')
    def test_complex_table_mix_scenario(self, mock_pluralize, mock_to_pascal, mock_create_import,
                                      mock_create_class, mock_logger):
        """Test complex scenario with multiple table types."""
        # Setup various table types
        user_table = self.create_mock_table("user", ["id"])

        product_table = self.create_mock_table("product", ["id"])

        # M2M through table
        user_product_table = self.create_mock_table(
            "user_product",
            ["user_id", "product_id"],
            [
                {"type": "many-to-one", "source_columns": ["user_id"]},
                {"type": "many-to-one", "source_columns": ["product_id"]}
            ]
        )

        # Table without PK
        stats_view = self.create_mock_table("stats_view", [])

        # Table with single PK but multiple FKs (not M2M through)
        order_table = self.create_mock_table(
            "order",
            ["id"],
            [
                {"type": "many-to-one", "source_columns": ["user_id"]},
                {"type": "many-to-one", "source_columns": ["product_id"]}
            ]
        )

        # Setup mocks
        mock_pluralize.side_effect = lambda name: f"{name}s"
        mock_to_pascal.side_effect = lambda name: name.title()
        mock_create_import.return_value = Mock()
        mock_create_class.return_value = Mock()

        tables = [user_table, product_table, user_product_table, stats_view, order_table]

        result = generate_serializers_ast(tables)

        # Verify correct number of serializer classes created
        # Should create for: user, product, order (3 tables)
        # Should skip: user_product (M2M through), stats_view (no PK)
        self.assertEqual(mock_create_class.call_count, 3)

        # Verify logger calls
        mock_logger.info.assert_called_once_with("Skipping serializer generation for M2M through table: user_product")
        mock_logger.warning.assert_called_once_with("Table stats_view does not have a primary key, skipping serializer generation...")

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)
        # 2 imports + 3 serializer classes = 5 total
        self.assertEqual(len(result.body), 5)


if __name__ == '__main__':
    unittest.main()
