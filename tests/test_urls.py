import unittest
from unittest.mock import Mock, patch, MagicMock
import ast
from typing import List

from drf_auto_generator.ast_codegen.urls import (
    generate_urls_ast,
    generate_urls_code
)
from drf_auto_generator.introspection_django import TableInfo, ColumnInfo


class TestGenerateUrlsAst(unittest.TestCase):
    """Test cases for generate_urls_ast function."""

    def setUp(self):
        """Set up test fixtures."""
        # Regular table with primary key
        self.mock_table1 = Mock(spec=TableInfo)
        self.mock_table1.name = "user"
        self.mock_table1.primary_key_columns = ["id"]
        self.mock_table1.is_m2m_through_table = False

        # Table without primary key
        self.mock_table2 = Mock(spec=TableInfo)
        self.mock_table2.name = "view_table"
        self.mock_table2.primary_key_columns = []
        self.mock_table2.is_m2m_through_table = False

        # M2M through table
        self.mock_table3 = Mock(spec=TableInfo)
        self.mock_table3.name = "user_role"
        self.mock_table3.primary_key_columns = ["user_id", "role_id"]
        self.mock_table3.is_m2m_through_table = True

        # Another regular table
        self.mock_table4 = Mock(spec=TableInfo)
        self.mock_table4.name = "product"
        self.mock_table4.primary_key_columns = ["id"]
        self.mock_table4.is_m2m_through_table = False

    @patch('drf_auto_generator.ast_codegen.urls.logger')
    @patch('drf_auto_generator.ast_codegen.urls.create_import')
    @patch('drf_auto_generator.ast_codegen.urls.create_assign')
    @patch('drf_auto_generator.ast_codegen.urls.create_call')
    @patch('drf_auto_generator.ast_codegen.urls.create_attribute_call')
    @patch('drf_auto_generator.ast_codegen.urls.create_string_constant')
    @patch('drf_auto_generator.ast_codegen.urls.create_keyword')
    @patch('drf_auto_generator.ast_codegen.urls.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.urls.pluralize')
    @patch('drf_auto_generator.ast_codegen.urls.to_snake_case')
    def test_generate_urls_ast_with_valid_tables(self, mock_to_snake, mock_pluralize, mock_to_pascal,
                                               mock_create_keyword, mock_create_string, mock_create_attr_call,
                                               mock_create_call, mock_create_assign, mock_create_import, mock_logger):
        """Test generating URLs AST with valid tables."""
        # Setup mocks
        mock_pluralize.side_effect = lambda name: f"{name}s"
        mock_to_pascal.side_effect = lambda name: name.title()
        mock_to_snake.side_effect = lambda name: name.lower()

        mock_create_import.return_value = Mock()
        mock_create_assign.return_value = Mock()
        mock_create_call.return_value = Mock()
        mock_create_attr_call.return_value = Mock()
        mock_create_string.return_value = Mock()
        mock_create_keyword.return_value = Mock()

        tables = [self.mock_table1, self.mock_table4]

        result = generate_urls_ast(tables, ".views")

        # Verify imports were created
        self.assertEqual(mock_create_import.call_count, 3)
        import_calls = mock_create_import.call_args_list
        self.assertEqual(import_calls[0][0], ("django.urls", ["path", "include"]))
        self.assertEqual(import_calls[1][0], ("rest_framework.routers", ["DefaultRouter"]))
        self.assertEqual(import_calls[2][0], (".views",))

        # Verify router assignment was created
        mock_create_assign.assert_any_call(target="router", value=mock_create_call.return_value)
        mock_create_call.assert_any_call("DefaultRouter")

        # Verify router registrations were created
        self.assertEqual(mock_create_attr_call.call_count, 2)  # Two valid tables

        # Verify table name conversions
        mock_pluralize.assert_any_call("user")
        mock_pluralize.assert_any_call("product")
        mock_to_pascal.assert_any_call("users")
        mock_to_pascal.assert_any_call("products")
        mock_to_snake.assert_any_call("user")
        mock_to_snake.assert_any_call("product")

        # Verify no logger warnings/info for valid tables
        mock_logger.warning.assert_not_called()
        mock_logger.info.assert_not_called()

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)
        self.assertEqual(result.type_ignores, [])

    @patch('drf_auto_generator.ast_codegen.urls.logger')
    @patch('drf_auto_generator.ast_codegen.urls.create_import')
    @patch('drf_auto_generator.ast_codegen.urls.create_assign')
    @patch('drf_auto_generator.ast_codegen.urls.create_call')
    @patch('drf_auto_generator.ast_codegen.urls.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.urls.pluralize')
    @patch('drf_auto_generator.ast_codegen.urls.to_snake_case')
    def test_generate_urls_ast_with_no_pk_table(self, mock_to_snake, mock_pluralize, mock_to_pascal,
                                              mock_create_call, mock_create_assign, mock_create_import, mock_logger):
        """Test generating URLs AST with table that has no primary key."""
        # Setup mocks
        mock_pluralize.return_value = "view_tables"
        mock_to_pascal.return_value = "ViewTables"
        mock_to_snake.return_value = "view_table"

        mock_create_import.return_value = Mock()
        mock_create_assign.return_value = Mock()
        mock_create_call.return_value = Mock()

        tables = [self.mock_table2]  # Table without PK

        result = generate_urls_ast(tables, ".views")

        # Verify warning was logged
        mock_logger.warning.assert_called_once_with("Table view_table does not have a primary key, skipping URL registration...")

        # Verify no router registrations were created (only imports, router assignment, urlpatterns)
        # Should not call functions related to registration since table is skipped
        mock_to_pascal.assert_not_called()
        mock_pluralize.assert_not_called()
        mock_to_snake.assert_not_called()

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)

    @patch('drf_auto_generator.ast_codegen.urls.logger')
    @patch('drf_auto_generator.ast_codegen.urls.create_import')
    @patch('drf_auto_generator.ast_codegen.urls.create_assign')
    @patch('drf_auto_generator.ast_codegen.urls.create_call')
    @patch('drf_auto_generator.ast_codegen.urls.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.urls.pluralize')
    @patch('drf_auto_generator.ast_codegen.urls.to_snake_case')
    def test_generate_urls_ast_with_m2m_through_table(self, mock_to_snake, mock_pluralize, mock_to_pascal,
                                                     mock_create_call, mock_create_assign, mock_create_import, mock_logger):
        """Test generating URLs AST with M2M through table."""
        # Setup mocks
        mock_pluralize.return_value = "user_roles"
        mock_to_pascal.return_value = "UserRoles"
        mock_to_snake.return_value = "user_role"

        mock_create_import.return_value = Mock()
        mock_create_assign.return_value = Mock()
        mock_create_call.return_value = Mock()

        tables = [self.mock_table3]  # M2M through table

        result = generate_urls_ast(tables, ".views")

        # Verify info was logged
        mock_logger.info.assert_called_once_with("Skipping URL registration for M2M through table: user_role")

        # Verify no router registrations were created (only imports, router assignment, urlpatterns)
        mock_to_pascal.assert_not_called()
        mock_pluralize.assert_not_called()
        mock_to_snake.assert_not_called()

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)

    @patch('drf_auto_generator.ast_codegen.urls.logger')
    @patch('drf_auto_generator.ast_codegen.urls.create_import')
    @patch('drf_auto_generator.ast_codegen.urls.create_assign')
    @patch('drf_auto_generator.ast_codegen.urls.create_call')
    @patch('drf_auto_generator.ast_codegen.urls.create_attribute_call')
    @patch('drf_auto_generator.ast_codegen.urls.create_string_constant')
    @patch('drf_auto_generator.ast_codegen.urls.create_keyword')
    @patch('drf_auto_generator.ast_codegen.urls.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.urls.pluralize')
    @patch('drf_auto_generator.ast_codegen.urls.to_snake_case')
    def test_generate_urls_ast_with_mixed_tables(self, mock_to_snake, mock_pluralize, mock_to_pascal,
                                                mock_create_keyword, mock_create_string, mock_create_attr_call,
                                                mock_create_call, mock_create_assign, mock_create_import, mock_logger):
        """Test generating URLs AST with mixed table types."""
        # Setup mocks
        mock_pluralize.side_effect = lambda name: f"{name}s"
        mock_to_pascal.side_effect = lambda name: name.title()
        mock_to_snake.side_effect = lambda name: name.lower()

        mock_create_import.return_value = Mock()
        mock_create_assign.return_value = Mock()
        mock_create_call.return_value = Mock()
        mock_create_attr_call.return_value = Mock()
        mock_create_string.return_value = Mock()
        mock_create_keyword.return_value = Mock()

        tables = [self.mock_table1, self.mock_table2, self.mock_table3, self.mock_table4]

        result = generate_urls_ast(tables, ".views")

        # Verify both warning and info were logged
        mock_logger.warning.assert_called_once_with("Table view_table does not have a primary key, skipping URL registration...")
        mock_logger.info.assert_called_once_with("Skipping URL registration for M2M through table: user_role")

                # Verify router registrations were created only for valid tables (2 tables)
        self.assertEqual(mock_create_attr_call.call_count, 2)

        # Verify conversions were called only for valid tables
        # pluralize is called twice per table (viewset name + URL path)
        self.assertEqual(mock_pluralize.call_count, 4)  # 2 tables * 2 calls each
        self.assertEqual(mock_to_pascal.call_count, 2)
        self.assertEqual(mock_to_snake.call_count, 2)

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)

    @patch('drf_auto_generator.ast_codegen.urls.create_import')
    @patch('drf_auto_generator.ast_codegen.urls.create_assign')
    @patch('drf_auto_generator.ast_codegen.urls.create_call')
    def test_generate_urls_ast_empty_tables(self, mock_create_call, mock_create_assign, mock_create_import):
        """Test generating URLs AST with empty table list."""
        mock_create_import.return_value = Mock()
        mock_create_assign.return_value = Mock()
        mock_create_call.return_value = Mock()

        result = generate_urls_ast([], ".views")

        # Verify imports were still created
        self.assertEqual(mock_create_import.call_count, 3)

        # Verify router assignment was created
        mock_create_assign.assert_called()
        mock_create_call.assert_called()

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)

    @patch('drf_auto_generator.ast_codegen.urls.create_import')
    @patch('drf_auto_generator.ast_codegen.urls.create_assign')
    @patch('drf_auto_generator.ast_codegen.urls.create_call')
    @patch('drf_auto_generator.ast_codegen.urls.create_attribute_call')
    @patch('drf_auto_generator.ast_codegen.urls.create_string_constant')
    @patch('drf_auto_generator.ast_codegen.urls.create_keyword')
    @patch('drf_auto_generator.ast_codegen.urls.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.urls.pluralize')
    @patch('drf_auto_generator.ast_codegen.urls.to_snake_case')
    def test_generate_urls_ast_custom_views_module(self, mock_to_snake, mock_pluralize, mock_to_pascal,
                                                  mock_create_keyword, mock_create_string, mock_create_attr_call,
                                                  mock_create_call, mock_create_assign, mock_create_import):
        """Test generating URLs AST with custom views module."""
        # Setup mocks
        mock_pluralize.return_value = "users"
        mock_to_pascal.return_value = "Users"
        mock_to_snake.return_value = "user"

        mock_create_import.return_value = Mock()
        mock_create_assign.return_value = Mock()
        mock_create_call.return_value = Mock()
        mock_create_attr_call.return_value = Mock()
        mock_create_string.return_value = Mock()
        mock_create_keyword.return_value = Mock()

        result = generate_urls_ast([self.mock_table1], "myapp.views")

        # Verify custom views module import
        import_calls = mock_create_import.call_args_list
        self.assertEqual(import_calls[2][0], ("myapp.views",))

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)

    @patch('drf_auto_generator.ast_codegen.urls.create_import')
    @patch('drf_auto_generator.ast_codegen.urls.create_assign')
    @patch('drf_auto_generator.ast_codegen.urls.create_call')
    @patch('drf_auto_generator.ast_codegen.urls.create_attribute_call')
    @patch('drf_auto_generator.ast_codegen.urls.create_string_constant')
    @patch('drf_auto_generator.ast_codegen.urls.create_keyword')
    @patch('drf_auto_generator.ast_codegen.urls.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.urls.pluralize')
    @patch('drf_auto_generator.ast_codegen.urls.to_snake_case')
    def test_generate_urls_ast_registration_details(self, mock_to_snake, mock_pluralize, mock_to_pascal,
                                                   mock_create_keyword, mock_create_string, mock_create_attr_call,
                                                   mock_create_call, mock_create_assign, mock_create_import):
        """Test the detailed registration call structure."""
        # Setup mocks
        mock_pluralize.return_value = "users"
        mock_to_pascal.return_value = "Users"
        mock_to_snake.return_value = "user"

        mock_create_import.return_value = Mock()
        mock_create_assign.return_value = Mock()
        mock_create_call.return_value = Mock()
        mock_create_attr_call.return_value = Mock()
        mock_create_string.return_value = Mock()
        mock_create_keyword.return_value = Mock()

        result = generate_urls_ast([self.mock_table1], ".views")

        # Verify router.register call was created with correct parameters
        mock_create_attr_call.assert_called_once()
        call_args = mock_create_attr_call.call_args

        # Verify object and attribute names
        self.assertEqual(call_args[1]["obj_name"], "router")
        self.assertEqual(call_args[1]["attr_name"], "register")

        # Verify string constant creation for URL path
        mock_create_string.assert_any_call("user")  # URL path

        # Verify keyword creation for basename
        mock_create_keyword.assert_called_once()
        keyword_call_args = mock_create_keyword.call_args
        self.assertEqual(keyword_call_args[0][0], "basename")

        # Verify basename string constant
        mock_create_string.assert_any_call("user")  # basename (table.name.lower())

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)

    def test_generate_urls_ast_complex_table_names(self):
        """Test URL generation with complex table names that need conversion."""
        # Create table with complex name
        complex_table = Mock(spec=TableInfo)
        complex_table.name = "UserProfile"
        complex_table.primary_key_columns = ["id"]
        complex_table.is_m2m_through_table = False

        with patch('drf_auto_generator.ast_codegen.urls.create_import') as mock_import, \
             patch('drf_auto_generator.ast_codegen.urls.create_assign') as mock_assign, \
             patch('drf_auto_generator.ast_codegen.urls.create_call') as mock_call, \
             patch('drf_auto_generator.ast_codegen.urls.create_attribute_call') as mock_attr_call, \
             patch('drf_auto_generator.ast_codegen.urls.create_string_constant') as mock_string, \
             patch('drf_auto_generator.ast_codegen.urls.create_keyword') as mock_keyword, \
             patch('drf_auto_generator.ast_codegen.urls.to_pascal_case') as mock_to_pascal, \
             patch('drf_auto_generator.ast_codegen.urls.pluralize') as mock_pluralize, \
             patch('drf_auto_generator.ast_codegen.urls.to_snake_case') as mock_to_snake:

            # Setup mocks for name conversions
            mock_pluralize.return_value = "UserProfiles"
            mock_to_pascal.return_value = "UserProfiles"
            mock_to_snake.return_value = "user_profile"

            mock_import.return_value = Mock()
            mock_assign.return_value = Mock()
            mock_call.return_value = Mock()
            mock_attr_call.return_value = Mock()
            mock_string.return_value = Mock()
            mock_keyword.return_value = Mock()

            result = generate_urls_ast([complex_table], ".views")

            # Verify name conversion functions were called with correct input
            # pluralize is called twice: once for viewset name and once for URL path
            self.assertEqual(mock_pluralize.call_count, 2)
            mock_pluralize.assert_any_call("UserProfile")  # For viewset name
            mock_pluralize.assert_any_call("user_profile")  # For URL path after to_snake_case
            mock_to_pascal.assert_called_once_with("UserProfiles")
            mock_to_snake.assert_called_once_with("UserProfile")

            # Verify AST module structure
            self.assertIsInstance(result, ast.Module)


class TestGenerateUrlsCode(unittest.TestCase):
    """Test cases for generate_urls_code function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_table = Mock(spec=TableInfo)
        self.mock_table.name = "user"
        self.mock_table.primary_key_columns = ["id"]
        self.mock_table.is_m2m_through_table = False

    @patch('drf_auto_generator.ast_codegen.urls.generate_urls_ast')
    @patch('ast.unparse')
    def test_generate_urls_code(self, mock_unparse, mock_generate_ast):
        """Test generating URLs code."""
        mock_ast_module = Mock()
        mock_generate_ast.return_value = mock_ast_module
        mock_unparse.return_value = "generated_urls_code"

        result = generate_urls_code([self.mock_table], ".views")

        # Verify AST generation was called
        mock_generate_ast.assert_called_once_with([self.mock_table], ".views")

        # Verify unparse was called with the AST
        mock_unparse.assert_called_once_with(mock_ast_module)

        # Verify result
        self.assertEqual(result, "generated_urls_code")

    @patch('drf_auto_generator.ast_codegen.urls.generate_urls_ast')
    @patch('ast.unparse')
    def test_generate_urls_code_custom_views_module(self, mock_unparse, mock_generate_ast):
        """Test generating URLs code with custom views module."""
        mock_ast_module = Mock()
        mock_generate_ast.return_value = mock_ast_module
        mock_unparse.return_value = "custom_urls_code"

        result = generate_urls_code([self.mock_table], "custom.views")

        # Verify AST generation was called with custom module
        mock_generate_ast.assert_called_once_with([self.mock_table], "custom.views")

        # Verify result
        self.assertEqual(result, "custom_urls_code")


class TestIntegrationScenarios(unittest.TestCase):
    """Integration test scenarios for complex table configurations."""

    def create_mock_table(self, name: str, pk_columns: List[str], is_m2m_through: bool = False) -> Mock:
        """Helper to create mock table with specified configuration."""
        mock_table = Mock(spec=TableInfo)
        mock_table.name = name
        mock_table.primary_key_columns = pk_columns
        mock_table.is_m2m_through_table = is_m2m_through
        return mock_table

    @patch('drf_auto_generator.ast_codegen.urls.logger')
    @patch('drf_auto_generator.ast_codegen.urls.create_import')
    @patch('drf_auto_generator.ast_codegen.urls.create_assign')
    @patch('drf_auto_generator.ast_codegen.urls.create_call')
    @patch('drf_auto_generator.ast_codegen.urls.create_attribute_call')
    @patch('drf_auto_generator.ast_codegen.urls.create_string_constant')
    @patch('drf_auto_generator.ast_codegen.urls.create_keyword')
    @patch('drf_auto_generator.ast_codegen.urls.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.urls.pluralize')
    @patch('drf_auto_generator.ast_codegen.urls.to_snake_case')
    def test_complex_table_mix_scenario(self, mock_to_snake, mock_pluralize, mock_to_pascal,
                                       mock_create_keyword, mock_create_string, mock_create_attr_call,
                                       mock_create_call, mock_create_assign, mock_create_import, mock_logger):
        """Test complex scenario with multiple table types."""
        # Setup various table types
        user_table = self.create_mock_table("user", ["id"], False)
        product_table = self.create_mock_table("product", ["id"], False)

        # M2M through table
        user_product_table = self.create_mock_table("user_product", ["user_id", "product_id"], True)

        # Table without PK
        stats_view = self.create_mock_table("stats_view", [])

        # Table with complex name requiring conversion
        order_item_table = self.create_mock_table("OrderItem", ["id"], False)

        # Setup mocks
        mock_pluralize.side_effect = lambda name: f"{name}s"
        mock_to_pascal.side_effect = lambda name: name.title()
        mock_to_snake.side_effect = lambda name: name.lower().replace(' ', '_')

        mock_create_import.return_value = Mock()
        mock_create_assign.return_value = Mock()
        mock_create_call.return_value = Mock()
        mock_create_attr_call.return_value = Mock()
        mock_create_string.return_value = Mock()
        mock_create_keyword.return_value = Mock()

        tables = [user_table, product_table, user_product_table, stats_view, order_item_table]

        result = generate_urls_ast(tables, ".views")

        # Verify correct number of router registrations (3 valid tables)
        # Should register: user, product, OrderItem
        # Should skip: user_product (M2M through), stats_view (no PK)
        self.assertEqual(mock_create_attr_call.call_count, 3)

        # Verify logger calls
        mock_logger.info.assert_called_once_with("Skipping URL registration for M2M through table: user_product")
        mock_logger.warning.assert_called_once_with("Table stats_view does not have a primary key, skipping URL registration...")

        # Verify name conversion calls for valid tables only
        # pluralize is called twice per table (viewset name + URL path)
        self.assertEqual(mock_pluralize.call_count, 6)  # 3 tables * 2 calls each
        self.assertEqual(mock_to_pascal.call_count, 3)
        self.assertEqual(mock_to_snake.call_count, 3)

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)

    @patch('drf_auto_generator.ast_codegen.urls.create_import')
    @patch('drf_auto_generator.ast_codegen.urls.create_assign')
    @patch('drf_auto_generator.ast_codegen.urls.create_call')
    def test_only_invalid_tables_scenario(self, mock_create_call, mock_create_assign, mock_create_import):
        """Test scenario with only invalid tables."""
        # Create only invalid tables
        no_pk_table = self.create_mock_table("view1", [])
        m2m_table = self.create_mock_table("junction", ["id1", "id2"], True)

        mock_create_import.return_value = Mock()
        mock_create_assign.return_value = Mock()
        mock_create_call.return_value = Mock()

        with patch('drf_auto_generator.ast_codegen.urls.logger') as mock_logger:
            result = generate_urls_ast([no_pk_table, m2m_table], ".views")

            # Verify both types of skip messages
            mock_logger.warning.assert_called_once_with("Table view1 does not have a primary key, skipping URL registration...")
            mock_logger.info.assert_called_once_with("Skipping URL registration for M2M through table: junction")

        # Verify basic structure still created (imports, router, urlpatterns)
        self.assertEqual(mock_create_import.call_count, 3)
        mock_create_assign.assert_called()
        mock_create_call.assert_called()

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)

    def test_url_pattern_generation_logic(self):
        """Test the URL pattern generation and structure."""
        # Create a simple table
        simple_table = self.create_mock_table("article", ["id"], False)

        with patch('drf_auto_generator.ast_codegen.urls.create_import') as mock_import, \
             patch('drf_auto_generator.ast_codegen.urls.create_assign') as mock_assign, \
             patch('drf_auto_generator.ast_codegen.urls.create_call') as mock_call, \
             patch('drf_auto_generator.ast_codegen.urls.create_attribute_call') as mock_attr_call, \
             patch('drf_auto_generator.ast_codegen.urls.create_string_constant') as mock_string, \
             patch('drf_auto_generator.ast_codegen.urls.create_keyword') as mock_keyword, \
             patch('drf_auto_generator.ast_codegen.urls.to_pascal_case') as mock_to_pascal, \
             patch('drf_auto_generator.ast_codegen.urls.pluralize') as mock_pluralize, \
             patch('drf_auto_generator.ast_codegen.urls.to_snake_case') as mock_to_snake:

            # Setup mocks
            mock_pluralize.return_value = "articles"
            mock_to_pascal.return_value = "Articles"
            mock_to_snake.return_value = "article"

            mock_import.return_value = Mock()
            mock_assign.return_value = Mock()
            mock_call.return_value = Mock()
            mock_attr_call.return_value = Mock()
            mock_string.return_value = Mock()
            mock_keyword.return_value = Mock()

            result = generate_urls_ast([simple_table], ".views")

            # Verify the registration call structure
            mock_attr_call.assert_called_once()
            call_args = mock_attr_call.call_args

            # Check that we have args and keywords parameters
            self.assertIn("args", call_args[1])
            self.assertIn("keywords", call_args[1])

            # Verify string constants were created for URL path and basename
            string_calls = mock_string.call_args_list
            # Should be called for URL path and basename
            self.assertGreaterEqual(len(string_calls), 2)

            # Verify keyword was created for basename
            mock_keyword.assert_called_once()
            keyword_args = mock_keyword.call_args
            self.assertEqual(keyword_args[0][0], "basename")

            # Verify AST module structure
            self.assertIsInstance(result, ast.Module)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def create_mock_table(self, name: str, pk_columns: List[str], is_m2m_through: bool = False) -> Mock:
        """Helper to create mock table with specified configuration."""
        mock_table = Mock(spec=TableInfo)
        mock_table.name = name
        mock_table.primary_key_columns = pk_columns
        mock_table.is_m2m_through_table = is_m2m_through
        return mock_table

    @patch('drf_auto_generator.ast_codegen.urls.logger')
    def test_table_with_empty_name(self, mock_logger):
        """Test handling of table with empty name."""
        empty_name_table = self.create_mock_table("", ["id"], False)

        with patch('drf_auto_generator.ast_codegen.urls.create_import') as mock_import, \
             patch('drf_auto_generator.ast_codegen.urls.create_assign') as mock_assign, \
             patch('drf_auto_generator.ast_codegen.urls.create_call') as mock_call, \
             patch('drf_auto_generator.ast_codegen.urls.to_pascal_case') as mock_to_pascal, \
             patch('drf_auto_generator.ast_codegen.urls.pluralize') as mock_pluralize, \
             patch('drf_auto_generator.ast_codegen.urls.to_snake_case') as mock_to_snake:

            mock_import.return_value = Mock()
            mock_assign.return_value = Mock()
            mock_call.return_value = Mock()
            mock_pluralize.return_value = "s"
            mock_to_pascal.return_value = "S"
            mock_to_snake.return_value = ""

            result = generate_urls_ast([empty_name_table], ".views")

            # Should still process the table since it has PK
            # pluralize is called twice: once for viewset name and once for URL path
            self.assertEqual(mock_pluralize.call_count, 2)
            mock_pluralize.assert_any_call("")  # For viewset name
            mock_pluralize.assert_any_call("")  # For URL path after to_snake_case
            mock_to_pascal.assert_called_once_with("s")
            mock_to_snake.assert_called_once_with("")

            # No warnings should be logged (table has PK and is not M2M through)
            mock_logger.warning.assert_not_called()
            mock_logger.info.assert_not_called()

            # Verify AST module structure
            self.assertIsInstance(result, ast.Module)

    def test_default_views_module_parameter(self):
        """Test that default views module parameter works correctly."""
        simple_table = self.create_mock_table("test", ["id"], False)

        with patch('drf_auto_generator.ast_codegen.urls.create_import') as mock_import, \
             patch('drf_auto_generator.ast_codegen.urls.create_assign') as mock_assign, \
             patch('drf_auto_generator.ast_codegen.urls.create_call') as mock_call:

            mock_import.return_value = Mock()
            mock_assign.return_value = Mock()
            mock_call.return_value = Mock()

            # Call without specifying views_module (should use default ".views")
            result = generate_urls_ast([simple_table])

            # Verify default views module was used
            import_calls = mock_import.call_args_list
            self.assertEqual(import_calls[2][0], (".views",))

            # Verify AST module structure
            self.assertIsInstance(result, ast.Module)


if __name__ == '__main__':
    unittest.main()
