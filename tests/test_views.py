import unittest
from unittest.mock import Mock, patch, MagicMock
import ast
from typing import List, Dict

from drf_auto_generator.ast_codegen.views import (
    _find_searchable_fields,
    _get_primary_key_field,
    _create_filterset_fields,
    create_viewset_class,
    generate_views_ast,
    generate_views_code
)
from drf_auto_generator.introspection_django import TableInfo, ColumnInfo


class TestFindSearchableFields(unittest.TestCase):
    """Test cases for _find_searchable_fields function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_table = Mock(spec=TableInfo)

    def test_find_searchable_fields_with_valid_fields(self):
        """Test finding searchable fields with valid field types."""
        self.mock_table.fields = [
            {
                "name": "title",
                "type": "CharField",
                "is_handled_by_relation": False
            },
            {
                "name": "description",
                "type": "TextField",
                "is_handled_by_relation": False
            },
            {
                "name": "email",
                "type": "EmailField",
                "is_handled_by_relation": False
            },
            {
                "name": "id",
                "type": "IntegerField",
                "is_handled_by_relation": False
            }
        ]

        result = _find_searchable_fields(self.mock_table)

        expected = ["title", "description", "email"]
        self.assertEqual(result, expected)

    def test_find_searchable_fields_with_limit(self):
        """Test finding searchable fields with custom limit."""
        self.mock_table.fields = [
            {"name": "title", "type": "CharField", "is_handled_by_relation": False},
            {"name": "description", "type": "TextField", "is_handled_by_relation": False},
            {"name": "email", "type": "EmailField", "is_handled_by_relation": False},
            {"name": "content", "type": "TextField", "is_handled_by_relation": False},
            {"name": "summary", "type": "CharField", "is_handled_by_relation": False}
        ]

        result = _find_searchable_fields(self.mock_table, limit=2)

        expected = ["title", "description"]
        self.assertEqual(result, expected)

    def test_find_searchable_fields_exclude_handled_by_relation(self):
        """Test excluding fields handled by relationships."""
        self.mock_table.fields = [
            {
                "name": "title",
                "type": "CharField",
                "is_handled_by_relation": False
            },
            {
                "name": "author",
                "type": "CharField",
                "is_handled_by_relation": True
            }
        ]

        result = _find_searchable_fields(self.mock_table)

        expected = ["title"]
        self.assertEqual(result, expected)

    def test_find_searchable_fields_exclude_short_names(self):
        """Test excluding fields with short names."""
        self.mock_table.fields = [
            {
                "name": "title",
                "type": "CharField",
                "is_handled_by_relation": False
            },
            {
                "name": "id",
                "type": "CharField",
                "is_handled_by_relation": False
            },
            {
                "name": "x",
                "type": "CharField",
                "is_handled_by_relation": False
            }
        ]

        result = _find_searchable_fields(self.mock_table)

        expected = ["title"]
        self.assertEqual(result, expected)

    def test_find_searchable_fields_no_valid_fields(self):
        """Test when no valid searchable fields are found."""
        self.mock_table.fields = [
            {
                "name": "id",
                "type": "IntegerField",
                "is_handled_by_relation": False
            },
            {
                "name": "count",
                "type": "IntegerField",
                "is_handled_by_relation": False
            }
        ]

        result = _find_searchable_fields(self.mock_table)

        expected = []
        self.assertEqual(result, expected)

    def test_find_searchable_fields_missing_name_or_type(self):
        """Test handling fields with missing name or type."""
        self.mock_table.fields = [
            {
                "name": "title",
                "type": "CharField",
                "is_handled_by_relation": False
            },
            {
                "type": "CharField",
                "is_handled_by_relation": False
            },
            {
                "name": "description",
                "is_handled_by_relation": False
            }
        ]

        result = _find_searchable_fields(self.mock_table)

        expected = ["title"]
        self.assertEqual(result, expected)


class TestGetPrimaryKeyField(unittest.TestCase):
    """Test cases for _get_primary_key_field function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_table = Mock(spec=TableInfo)
        self.mock_table.name = "test_table"

    @patch('drf_auto_generator.ast_codegen.views.logger')
    def test_get_primary_key_field_m2m_through_table(self, mock_logger):
        """Test getting primary key for M2M through table."""
        self.mock_table.primary_key_columns = ["user_id", "role_id"]
        self.mock_table.is_m2m_through_table = True

        result = _get_primary_key_field(self.mock_table)

        self.assertEqual(result, "id")
        mock_logger.debug.assert_called()

    @patch('drf_auto_generator.ast_codegen.views.logger')
    def test_get_primary_key_field_composite_pk(self, mock_logger):
        """Test getting primary key for composite primary key."""
        self.mock_table.primary_key_columns = ["user_id", "role_id"]
        self.mock_table.is_m2m_through_table = False

        result = _get_primary_key_field(self.mock_table)

        self.assertEqual(result, "pk")
        mock_logger.debug.assert_called()

    @patch('drf_auto_generator.ast_codegen.views.logger')
    def test_get_primary_key_field_single_pk(self, mock_logger):
        """Test getting primary key for single primary key."""
        self.mock_table.primary_key_columns = ["id"]
        self.mock_table.is_m2m_through_table = False
        self.mock_table.fields = [
            {
                "name": "id",
                "original_column_name": "id",
                "is_pk": True,
                "is_handled_by_relation": False
            }
        ]

        result = _get_primary_key_field(self.mock_table)

        self.assertEqual(result, "id")
        mock_logger.debug.assert_called()

    @patch('drf_auto_generator.ast_codegen.views.logger')
    def test_get_primary_key_field_single_pk_field_not_found(self, mock_logger):
        """Test fallback when single PK field mapping not found."""
        self.mock_table.primary_key_columns = ["id"]
        self.mock_table.is_m2m_through_table = False
        self.mock_table.fields = [
            {
                "name": "other_field",
                "original_column_name": "other_column",
                "is_pk": False,
                "is_handled_by_relation": False
            }
        ]

        result = _get_primary_key_field(self.mock_table)

        self.assertEqual(result, "pk")
        mock_logger.warning.assert_called()

    @patch('drf_auto_generator.ast_codegen.views.logger')
    def test_get_primary_key_field_no_pk(self, mock_logger):
        """Test fallback when no primary key found."""
        self.mock_table.primary_key_columns = []
        self.mock_table.is_m2m_through_table = False

        result = _get_primary_key_field(self.mock_table)

        self.assertEqual(result, "pk")
        mock_logger.warning.assert_called()

    @patch('drf_auto_generator.ast_codegen.views.logger')
    def test_get_primary_key_field_single_pk_custom_name(self, mock_logger):
        """Test single PK with custom field name."""
        self.mock_table.primary_key_columns = ["user_id"]
        self.mock_table.is_m2m_through_table = False
        self.mock_table.fields = [
            {
                "name": "user_id",
                "original_column_name": "user_id",
                "is_pk": True,
                "is_handled_by_relation": False
            }
        ]

        result = _get_primary_key_field(self.mock_table)

        self.assertEqual(result, "user_id")
        mock_logger.debug.assert_called()


class TestCreateFiltersetFields(unittest.TestCase):
    """Test cases for _create_filterset_fields function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_table = Mock(spec=TableInfo)
        self.mock_table.relationships = []
        self.mock_table.meta_indexes = []
        self.mock_table.fields = []

    def test_create_filterset_fields_with_foreign_keys(self):
        """Test creating filterset fields with foreign key relationships."""
        self.mock_table.relationships = [
            {
                "type": "many-to-one",
                "name": "author"
            },
            {
                "type": "many-to-many",
                "name": "tags"
            }
        ]

        result = _create_filterset_fields(self.mock_table)

        expected = {"author": ["exact"]}
        self.assertEqual(result, expected)

    def test_create_filterset_fields_with_indexes(self):
        """Test creating filterset fields with indexed fields."""
        self.mock_table.meta_indexes = [
            {
                "fields": ["title", "created_at"]
            }
        ]
        self.mock_table.fields = [
            {
                "name": "title",
                "type": "CharField",
                "is_pk": False,
                "is_handled_by_relation": False
            },
            {
                "name": "created_at",
                "type": "DateTimeField",
                "is_pk": False,
                "is_handled_by_relation": False
            }
        ]

        result = _create_filterset_fields(self.mock_table)

        expected = {
            "title": ["exact", "icontains"],
            "created_at": ["exact", "gte", "lte", "date"]
        }
        self.assertEqual(result, expected)

    def test_create_filterset_fields_with_unique_fields(self):
        """Test creating filterset fields with unique fields."""
        self.mock_table.fields = [
            {
                "name": "email",
                "type": "EmailField",
                "is_pk": False,
                "is_handled_by_relation": False,
                "options": {"unique": True}
            }
        ]

        result = _create_filterset_fields(self.mock_table)

        expected = {"email": ["exact"]}
        self.assertEqual(result, expected)

    def test_create_filterset_fields_field_type_mapping(self):
        """Test different field type mappings for filterset fields."""
        self.mock_table.meta_indexes = [
            {
                "fields": ["title", "count", "published", "created_at", "other"]
            }
        ]
        self.mock_table.fields = [
            {
                "name": "title",
                "type": "CharField",
                "is_pk": False,
                "is_handled_by_relation": False
            },
            {
                "name": "count",
                "type": "IntegerField",
                "is_pk": False,
                "is_handled_by_relation": False
            },
            {
                "name": "published",
                "type": "BooleanField",
                "is_pk": False,
                "is_handled_by_relation": False
            },
            {
                "name": "created_at",
                "type": "DateField",
                "is_pk": False,
                "is_handled_by_relation": False
            },
            {
                "name": "other",
                "type": "UnknownField",
                "is_pk": False,
                "is_handled_by_relation": False
            }
        ]

        result = _create_filterset_fields(self.mock_table)

        expected = {
            "title": ["exact", "icontains"],
            "count": ["exact", "gte", "lte"],
            "published": ["exact"],
            "created_at": ["exact", "gte", "lte", "date"],
            "other": ["exact"]
        }
        self.assertEqual(result, expected)

    def test_create_filterset_fields_skip_pk_and_relations(self):
        """Test skipping primary key and relationship fields."""
        self.mock_table.meta_indexes = [
            {
                "fields": ["id", "author_id", "title"]
            }
        ]
        self.mock_table.fields = [
            {
                "name": "id",
                "type": "IntegerField",
                "is_pk": True,
                "is_handled_by_relation": False
            },
            {
                "name": "author_id",
                "type": "IntegerField",
                "is_pk": False,
                "is_handled_by_relation": True
            },
            {
                "name": "title",
                "type": "CharField",
                "is_pk": False,
                "is_handled_by_relation": False
            }
        ]

        result = _create_filterset_fields(self.mock_table)

        expected = {"title": ["exact", "icontains"]}
        self.assertEqual(result, expected)

    def test_create_filterset_fields_no_duplicate_from_relationships(self):
        """Test not duplicating fields already added from relationships."""
        self.mock_table.relationships = [
            {
                "type": "many-to-one",
                "name": "author"
            }
        ]
        self.mock_table.meta_indexes = [
            {
                "fields": ["author"]
            }
        ]
        self.mock_table.fields = [
            {
                "name": "author",
                "type": "CharField",
                "is_pk": False,
                "is_handled_by_relation": False
            }
        ]

        result = _create_filterset_fields(self.mock_table)

        expected = {"author": ["exact"]}
        self.assertEqual(result, expected)

    def test_create_filterset_fields_complex_scenario(self):
        """Test complex scenario with multiple field types."""
        self.mock_table.relationships = [
            {
                "type": "many-to-one",
                "name": "category"
            }
        ]
        self.mock_table.meta_indexes = [
            {
                "fields": ["title", "views"]
            }
        ]
        self.mock_table.fields = [
            {
                "name": "title",
                "type": "CharField",
                "is_pk": False,
                "is_handled_by_relation": False
            },
            {
                "name": "views",
                "type": "PositiveIntegerField",
                "is_pk": False,
                "is_handled_by_relation": False
            },
            {
                "name": "email",
                "type": "EmailField",
                "is_pk": False,
                "is_handled_by_relation": False,
                "options": {"unique": True}
            }
        ]

        result = _create_filterset_fields(self.mock_table)

        expected = {
            "category": ["exact"],
            "title": ["exact", "icontains"],
            "views": ["exact", "gte", "lte"],
            "email": ["exact"]
        }
        self.assertEqual(result, expected)

    def test_create_filterset_fields_text_field_types(self):
        """Test different text field types get correct lookups."""
        self.mock_table.meta_indexes = [
            {
                "fields": ["title", "content", "email"]
            }
        ]
        self.mock_table.fields = [
            {
                "name": "title",
                "type": "CharField",
                "is_pk": False,
                "is_handled_by_relation": False
            },
            {
                "name": "content",
                "type": "TextField",
                "is_pk": False,
                "is_handled_by_relation": False
            },
            {
                "name": "email",
                "type": "EmailField",
                "is_pk": False,
                "is_handled_by_relation": False
            }
        ]

        result = _create_filterset_fields(self.mock_table)

        expected = {
            "title": ["exact", "icontains"],
            "content": ["exact", "icontains"],
            "email": ["exact", "icontains"]
        }
        self.assertEqual(result, expected)

    def test_create_filterset_fields_integer_field_types(self):
        """Test different integer field types get correct lookups."""
        self.mock_table.meta_indexes = [
            {
                "fields": ["count1", "count2", "count3", "count4", "count5", "count6"]
            }
        ]
        self.mock_table.fields = [
            {"name": "count1", "type": "IntegerField", "is_pk": False, "is_handled_by_relation": False},
            {"name": "count2", "type": "BigIntegerField", "is_pk": False, "is_handled_by_relation": False},
            {"name": "count3", "type": "SmallIntegerField", "is_pk": False, "is_handled_by_relation": False},
            {"name": "count4", "type": "PositiveIntegerField", "is_pk": False, "is_handled_by_relation": False},
            {"name": "count5", "type": "PositiveBigIntegerField", "is_pk": False, "is_handled_by_relation": False},
            {"name": "count6", "type": "PositiveSmallIntegerField", "is_pk": False, "is_handled_by_relation": False}
        ]

        result = _create_filterset_fields(self.mock_table)

        expected = {
            "count1": ["exact", "gte", "lte"],
            "count2": ["exact", "gte", "lte"],
            "count3": ["exact", "gte", "lte"],
            "count4": ["exact", "gte", "lte"],
            "count5": ["exact", "gte", "lte"],
            "count6": ["exact", "gte", "lte"]
        }
        self.assertEqual(result, expected)


class TestCreateViewsetClass(unittest.TestCase):
    """Test cases for create_viewset_class function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_table = Mock(spec=TableInfo)
        self.mock_table.name = "user"
        self.mock_table.primary_key_columns = ["id"]
        self.mock_table.is_m2m_through_table = False
        self.mock_table.fields = [
            {
                "name": "id",
                "type": "IntegerField",
                "is_pk": True,
                "is_handled_by_relation": False,
                "original_column_name": "id"
            },
            {
                "name": "name",
                "type": "CharField",
                "is_pk": False,
                "is_handled_by_relation": False
            }
        ]
        self.mock_table.relationships = []
        self.mock_table.meta_indexes = []

    @patch('drf_auto_generator.ast_codegen.views._create_filterset_fields')
    @patch('drf_auto_generator.ast_codegen.views._get_primary_key_field')
    @patch('drf_auto_generator.ast_codegen.views._find_searchable_fields')
    @patch('drf_auto_generator.ast_codegen.views.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.views.pluralize')
    def test_create_viewset_class_basic(self, mock_pluralize, mock_to_pascal, mock_find_searchable,
                                       mock_get_pk, mock_create_filterset):
        """Test basic viewset class creation."""
        mock_pluralize.return_value = "users"
        mock_to_pascal.return_value = "Users"
        mock_find_searchable.return_value = ["name"]
        mock_get_pk.return_value = "id"
        mock_create_filterset.return_value = {"name": ["exact", "icontains"]}

        result = create_viewset_class(self.mock_table)

        # Verify it's a class definition
        self.assertIsInstance(result, ast.ClassDef)

        # Verify function calls
        mock_pluralize.assert_called_once_with("user")
        mock_to_pascal.assert_called_once_with("users")
        mock_find_searchable.assert_called_once_with(self.mock_table)
        mock_get_pk.assert_called_once_with(self.mock_table)
        mock_create_filterset.assert_called_once_with(self.mock_table)

    @patch('drf_auto_generator.ast_codegen.views._create_filterset_fields')
    @patch('drf_auto_generator.ast_codegen.views._get_primary_key_field')
    @patch('drf_auto_generator.ast_codegen.views._find_searchable_fields')
    @patch('drf_auto_generator.ast_codegen.views.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.views.pluralize')
    def test_create_viewset_class_no_filterset_fields(self, mock_pluralize, mock_to_pascal,
                                                     mock_find_searchable, mock_get_pk, mock_create_filterset):
        """Test viewset class creation without filterset fields."""
        mock_pluralize.return_value = "users"
        mock_to_pascal.return_value = "Users"
        mock_find_searchable.return_value = ["name"]
        mock_get_pk.return_value = "id"
        mock_create_filterset.return_value = {}  # No filterset fields

        result = create_viewset_class(self.mock_table)

        # Verify it's a class definition
        self.assertIsInstance(result, ast.ClassDef)

        # Verify function calls
        mock_create_filterset.assert_called_once_with(self.mock_table)

    @patch('drf_auto_generator.ast_codegen.views._create_filterset_fields')
    @patch('drf_auto_generator.ast_codegen.views._get_primary_key_field')
    @patch('drf_auto_generator.ast_codegen.views._find_searchable_fields')
    @patch('drf_auto_generator.ast_codegen.views.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.views.pluralize')
    def test_create_viewset_class_with_ordering_fields(self, mock_pluralize, mock_to_pascal,
                                                      mock_find_searchable, mock_get_pk, mock_create_filterset):
        """Test viewset class creation with ordering fields."""
        mock_pluralize.return_value = "users"
        mock_to_pascal.return_value = "Users"
        mock_find_searchable.return_value = ["name"]
        mock_get_pk.return_value = "id"
        mock_create_filterset.return_value = {}

        # Add fields suitable for ordering
        self.mock_table.fields = [
            {
                "name": "id",
                "type": "IntegerField",
                "is_pk": True,
                "is_handled_by_relation": False,
                "original_column_name": "id"
            },
            {
                "name": "name",
                "type": "CharField",
                "is_pk": False,
                "is_handled_by_relation": False
            },
            {
                "name": "created_at",
                "type": "DateTimeField",
                "is_pk": False,
                "is_handled_by_relation": False
            },
            {
                "name": "author",
                "type": "CharField",
                "is_pk": False,
                "is_handled_by_relation": True  # Should be excluded
            }
        ]

        result = create_viewset_class(self.mock_table)

        # Verify it's a class definition
        self.assertIsInstance(result, ast.ClassDef)


class TestGenerateViewsAst(unittest.TestCase):
    """Test cases for generate_views_ast function."""

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

    @patch('drf_auto_generator.ast_codegen.views.logger')
    @patch('drf_auto_generator.ast_codegen.views.create_viewset_class')
    @patch('drf_auto_generator.ast_codegen.views.create_import')
    @patch('drf_auto_generator.ast_codegen.views.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.views.pluralize')
    def test_generate_views_ast_with_mixed_tables(self, mock_pluralize, mock_to_pascal, mock_create_import,
                                                 mock_create_viewset, mock_logger):
        """Test generating views AST with mixed table types."""
        # Setup mocks
        mock_pluralize.side_effect = lambda name: f"{name}s"
        mock_to_pascal.side_effect = lambda name: name.title()
        mock_create_import.return_value = Mock()
        mock_create_viewset.return_value = Mock()

        tables = [self.mock_table1, self.mock_table2, self.mock_table3, self.mock_table4]

        result = generate_views_ast(tables, ".models", ".serializers")

        # Verify imports were created
        self.assertEqual(mock_create_import.call_count, 4)

        # Verify import calls
        import_calls = mock_create_import.call_args_list
        self.assertEqual(import_calls[0][0], ("rest_framework", ["viewsets", "permissions", "filters"]))
        self.assertEqual(import_calls[1][0], ("django_filters.rest_framework", ["DjangoFilterBackend"]))
        self.assertEqual(import_calls[2][0], (".models", ["Users", "Products"]))  # Excluding M2M through and no PK
        self.assertEqual(import_calls[3][0], (".serializers", ["UsersSerializer", "ProductsSerializer"]))

        # Verify viewset classes were created for valid tables only
        self.assertEqual(mock_create_viewset.call_count, 2)
        mock_create_viewset.assert_any_call(self.mock_table1)
        mock_create_viewset.assert_any_call(self.mock_table4)

        # Verify logger messages
        mock_logger.info.assert_called_once_with("Skipping ViewSet generation for M2M through table: user_role")
        mock_logger.warning.assert_called_once_with("Table view_table does not have a primary key, skipping viewset generation...")

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)
        self.assertEqual(result.type_ignores, [])

    @patch('drf_auto_generator.ast_codegen.views.create_import')
    @patch('drf_auto_generator.ast_codegen.views.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.views.pluralize')
    def test_generate_views_ast_empty_tables(self, mock_pluralize, mock_to_pascal, mock_create_import):
        """Test generating views AST with empty table list."""
        mock_pluralize.return_value = ""
        mock_to_pascal.return_value = ""
        mock_create_import.return_value = Mock()

        result = generate_views_ast([], ".models", ".serializers")

        # Verify imports were still created
        self.assertEqual(mock_create_import.call_count, 4)

        # Verify empty model and serializer imports
        import_calls = mock_create_import.call_args_list
        self.assertEqual(import_calls[2][0], (".models", []))
        self.assertEqual(import_calls[3][0], (".serializers", []))

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)

    @patch('drf_auto_generator.ast_codegen.views.create_viewset_class')
    @patch('drf_auto_generator.ast_codegen.views.create_import')
    @patch('drf_auto_generator.ast_codegen.views.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.views.pluralize')
    def test_generate_views_ast_custom_modules(self, mock_pluralize, mock_to_pascal, mock_create_import,
                                              mock_create_viewset):
        """Test generating views AST with custom module names."""
        mock_pluralize.return_value = "users"
        mock_to_pascal.return_value = "Users"
        mock_create_import.return_value = Mock()
        mock_create_viewset.return_value = Mock()

        result = generate_views_ast([self.mock_table1], "myapp.models", "myapp.serializers")

        # Verify custom module imports
        import_calls = mock_create_import.call_args_list
        self.assertEqual(import_calls[2][0], ("myapp.models", ["Users"]))
        self.assertEqual(import_calls[3][0], ("myapp.serializers", ["UsersSerializer"]))

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)

    @patch('drf_auto_generator.ast_codegen.views.logger')
    @patch('drf_auto_generator.ast_codegen.views.create_import')
    @patch('drf_auto_generator.ast_codegen.views.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.views.pluralize')
    def test_generate_views_ast_only_invalid_tables(self, mock_pluralize, mock_to_pascal, mock_create_import,
                                                   mock_logger):
        """Test generating views AST with only invalid tables."""
        mock_pluralize.return_value = "users"
        mock_to_pascal.return_value = "Users"
        mock_create_import.return_value = Mock()

        tables = [self.mock_table2, self.mock_table3]  # No PK and M2M through

        result = generate_views_ast(tables, ".models", ".serializers")

        # Verify logger calls
        mock_logger.info.assert_called_once_with("Skipping ViewSet generation for M2M through table: user_role")
        mock_logger.warning.assert_called_once_with("Table view_table does not have a primary key, skipping viewset generation...")

        # Verify empty model and serializer imports
        import_calls = mock_create_import.call_args_list
        self.assertEqual(import_calls[2][0], (".models", []))
        self.assertEqual(import_calls[3][0], (".serializers", []))

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)


class TestGenerateViewsCode(unittest.TestCase):
    """Test cases for generate_views_code function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_table = Mock(spec=TableInfo)
        self.mock_table.name = "user"
        self.mock_table.primary_key_columns = ["id"]
        self.mock_table.is_m2m_through_table = False

    @patch('drf_auto_generator.ast_codegen.views.generate_views_ast')
    @patch('ast.unparse')
    def test_generate_views_code(self, mock_unparse, mock_generate_ast):
        """Test generating views code."""
        mock_ast_module = Mock()
        mock_generate_ast.return_value = mock_ast_module
        mock_unparse.return_value = "generated_views_code"

        result = generate_views_code([self.mock_table], ".models", ".serializers")

        # Verify AST generation was called
        mock_generate_ast.assert_called_once_with([self.mock_table], ".models", ".serializers")

        # Verify unparse was called with the AST
        mock_unparse.assert_called_once_with(mock_ast_module)

        # Verify result
        self.assertEqual(result, "generated_views_code")

    @patch('drf_auto_generator.ast_codegen.views.generate_views_ast')
    @patch('ast.unparse')
    def test_generate_views_code_custom_modules(self, mock_unparse, mock_generate_ast):
        """Test generating views code with custom module names."""
        mock_ast_module = Mock()
        mock_generate_ast.return_value = mock_ast_module
        mock_unparse.return_value = "custom_views_code"

        result = generate_views_code([self.mock_table], "custom.models", "custom.serializers")

        # Verify AST generation was called with custom modules
        mock_generate_ast.assert_called_once_with([self.mock_table], "custom.models", "custom.serializers")

        # Verify result
        self.assertEqual(result, "custom_views_code")


class TestIntegrationScenarios(unittest.TestCase):
    """Integration test scenarios for complex table configurations."""

    def create_mock_table(self, name: str, pk_columns: List[str], is_m2m_through: bool = False,
                         fields: List[Dict] = None, relationships: List[Dict] = None,
                         indexes: List[Dict] = None) -> Mock:
        """Helper to create mock table with specified configuration."""
        mock_table = Mock(spec=TableInfo)
        mock_table.name = name
        mock_table.primary_key_columns = pk_columns
        mock_table.is_m2m_through_table = is_m2m_through
        mock_table.fields = fields or []
        mock_table.relationships = relationships or []
        mock_table.meta_indexes = indexes or []
        return mock_table

    @patch('drf_auto_generator.ast_codegen.views.logger')
    @patch('drf_auto_generator.ast_codegen.views.create_viewset_class')
    @patch('drf_auto_generator.ast_codegen.views.create_import')
    @patch('drf_auto_generator.ast_codegen.views.to_pascal_case')
    @patch('drf_auto_generator.ast_codegen.views.pluralize')
    def test_complex_table_mix_scenario(self, mock_pluralize, mock_to_pascal, mock_create_import,
                                       mock_create_viewset, mock_logger):
        """Test complex scenario with multiple table types."""
        # Setup various table types
        user_table = self.create_mock_table(
            "user", ["id"], False,
            fields=[
                {
                    "name": "id",
                    "type": "IntegerField",
                    "is_pk": True,
                    "is_handled_by_relation": False,
                    "original_column_name": "id"
                },
                {
                    "name": "name",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                }
            ]
        )

        product_table = self.create_mock_table(
            "product", ["id"], False,
            fields=[
                {
                    "name": "id",
                    "type": "IntegerField",
                    "is_pk": True,
                    "is_handled_by_relation": False,
                    "original_column_name": "id"
                }
            ]
        )

        # M2M through table
        user_product_table = self.create_mock_table(
            "user_product", ["user_id", "product_id"], True
        )

        # Table without PK
        stats_view = self.create_mock_table("stats_view", [])

        # Setup mocks
        mock_pluralize.side_effect = lambda name: f"{name}s"
        mock_to_pascal.side_effect = lambda name: name.title()
        mock_create_import.return_value = Mock()
        mock_create_viewset.return_value = Mock()

        tables = [user_table, product_table, user_product_table, stats_view]

        result = generate_views_ast(tables)

        # Verify correct number of viewset classes created
        # Should create for: user, product (2 tables)
        # Should skip: user_product (M2M through), stats_view (no PK)
        self.assertEqual(mock_create_viewset.call_count, 2)

        # Verify logger calls
        mock_logger.info.assert_called_once_with("Skipping ViewSet generation for M2M through table: user_product")
        mock_logger.warning.assert_called_once_with("Table stats_view does not have a primary key, skipping viewset generation...")

        # Verify AST module structure
        self.assertIsInstance(result, ast.Module)

    def test_comprehensive_filterset_fields_scenario(self):
        """Test comprehensive scenario for filterset fields creation."""
        # Create a table with various field types and configurations
        complex_table = self.create_mock_table(
            "article", ["id"], False,
            fields=[
                {
                    "name": "id",
                    "type": "IntegerField",
                    "is_pk": True,
                    "is_handled_by_relation": False,
                    "original_column_name": "id"
                },
                {
                    "name": "title",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "content",
                    "type": "TextField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "views",
                    "type": "IntegerField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "published",
                    "type": "BooleanField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "created_at",
                    "type": "DateTimeField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "email",
                    "type": "EmailField",
                    "is_pk": False,
                    "is_handled_by_relation": False,
                    "options": {"unique": True}
                }
            ],
            relationships=[
                {
                    "type": "many-to-one",
                    "name": "author"
                }
            ],
            indexes=[
                {
                    "fields": ["title", "views", "created_at"]
                }
            ]
        )

        result = _create_filterset_fields(complex_table)

        expected = {
            "author": ["exact"],
            "title": ["exact", "icontains"],
            "views": ["exact", "gte", "lte"],
            "created_at": ["exact", "gte", "lte", "date"],
            "email": ["exact"]
        }

        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
