"""
Tests for Django Models Code Generator

This module tests the models.py AST code generator with comprehensive coverage.
"""

import ast
from unittest import TestCase
from unittest.mock import patch

from drf_auto_generator.ast_codegen.models import (
    create_model_field,
    _create_additional_field_options,
    create_relationship_field,
    create_model_meta,
    create_str_method,
    create_model_class,
    generate_models_ast,
    generate_models_code,
    BOOLEAN_OPTIONS,
    NUMERIC_OPTIONS,
)
from drf_auto_generator.introspection_django import TableInfo, ColumnInfo


class TestCreateModelField(TestCase):
    """Test cases for create_model_field function"""

    def test_basic_field_creation(self):
        """Test creating a basic model field"""
        col_info = ColumnInfo(
            name="username",
            db_type_string="CharField",
            internal_size=100,
            precision=None,
            scale=None,
            nullable=False,
            default=None,
            collation=None,
            is_pk=False,
            is_unique=False,
            is_foreign_key=False
        )

        with patch('drf_auto_generator.ast_codegen.models.map_db_type_to_django') as mock_map:
            mock_map.return_value = ("CharField", {"max_length": 100, "null": False})

            field_node = create_model_field(col_info)

            assert isinstance(field_node, ast.Assign)
            assert field_node.targets[0].id == "username"
            mock_map.assert_called_once_with(col_info, None)

    def test_field_with_table_info(self):
        """Test creating field with table info"""
        col_info = ColumnInfo(
            name="id",
            db_type_string="IntegerField",
            internal_size=None,
            precision=None,
            scale=None,
            nullable=False,
            default=None,
            collation=None,
            is_pk=True,
            is_unique=False,
            is_foreign_key=False
        )

        table_info = TableInfo(
            name="user",
            primary_key_columns=["id"],
            columns=[col_info]
        )

        with patch('drf_auto_generator.ast_codegen.models.map_db_type_to_django') as mock_map:
            mock_map.return_value = ("AutoField", {})

            field_node = create_model_field(col_info, table_info)

            assert isinstance(field_node, ast.Assign)
            mock_map.assert_called_once_with(col_info, table_info)

    def test_field_with_boolean_options(self):
        """Test creating field with boolean options"""
        col_info = ColumnInfo(
            name="is_active",
            db_type_string="BooleanField",
            internal_size=None,
            precision=None,
            scale=None,
            nullable=True,
            default=None,
            collation=None,
            is_pk=False,
            is_unique=True,
            is_foreign_key=False
        )

        with patch('drf_auto_generator.ast_codegen.models.map_db_type_to_django') as mock_map:
            mock_map.return_value = ("BooleanField", {"null": True, "unique": True})

            field_node = create_model_field(col_info)

            assert isinstance(field_node, ast.Assign)

    def test_field_with_numeric_options(self):
        """Test creating field with numeric options"""
        col_info = ColumnInfo(
            name="price",
            db_type_string="DecimalField",
            internal_size=None,
            precision=10,
            scale=2,
            nullable=False,
            default=None,
            collation=None,
            is_pk=False,
            is_unique=False,
            is_foreign_key=False
        )

        with patch('drf_auto_generator.ast_codegen.models.map_db_type_to_django') as mock_map:
            mock_map.return_value = ("DecimalField", {"max_digits": 10, "decimal_places": 2})

            field_node = create_model_field(col_info)

            assert isinstance(field_node, ast.Assign)

    def test_field_with_string_options(self):
        """Test creating field with string options"""
        col_info = ColumnInfo(
            name="name",
            db_type_string="CharField",
            internal_size=100,
            precision=None,
            scale=None,
            nullable=False,
            default="test",
            collation=None,
            is_pk=False,
            is_unique=False,
            is_foreign_key=False
        )

        with patch('drf_auto_generator.ast_codegen.models.map_db_type_to_django') as mock_map:
            mock_map.return_value = ("CharField", {"max_length": 100, "default": "test"})

            field_node = create_model_field(col_info)

            assert isinstance(field_node, ast.Assign)


class TestCreateAdditionalFieldOptions(TestCase):
    """Test cases for _create_additional_field_options function"""

    def test_no_additional_options(self):
        """Test when no additional options are needed"""
        col_info = ColumnInfo(
            name="username",
            db_type_string="CharField",
            internal_size=100,
            precision=None,
            scale=None,
            nullable=False,
            default=None,
            collation=None,
            is_pk=False,
            is_unique=False,
            is_foreign_key=False,
            enum_values=None
        )

        options = _create_additional_field_options(col_info, "CharField")

        assert options == []

    def test_enum_field_options(self):
        """Test creating options for enum fields"""
        col_info = ColumnInfo(
            name="status",
            db_type_string="CharField",
            internal_size=None,
            precision=None,
            scale=None,
            nullable=False,
            default=None,
            collation=None,
            is_pk=False,
            is_unique=False,
            is_foreign_key=False,
            enum_values=["active", "inactive", "pending"]
        )

        options = _create_additional_field_options(col_info, "CharField")

        assert len(options) == 2  # choices and max_length
        assert options[0].arg == "choices"
        assert options[1].arg == "max_length"

    def test_enum_field_with_empty_values(self):
        """Test enum field with empty values"""
        col_info = ColumnInfo(
            name="status",
            db_type_string="CharField",
            internal_size=None,
            precision=None,
            scale=None,
            nullable=False,
            default=None,
            collation=None,
            is_pk=False,
            is_unique=False,
            is_foreign_key=False,
            enum_values=[]
        )

        options = _create_additional_field_options(col_info, "CharField")

        assert len(options) == 0  # no options for empty enum_values

    def test_enum_field_non_charfield(self):
        """Test enum field with non-CharField type"""
        col_info = ColumnInfo(
            name="status",
            db_type_string="IntegerField",
            internal_size=None,
            precision=None,
            scale=None,
            nullable=False,
            default=None,
            collation=None,
            is_pk=False,
            is_unique=False,
            is_foreign_key=False,
            enum_values=["1", "2", "3"]
        )

        options = _create_additional_field_options(col_info, "IntegerField")

        assert len(options) == 1  # only choices, no max_length
        assert options[0].arg == "choices"


class TestCreateRelationshipField(TestCase):
    """Test cases for create_relationship_field function"""

    def test_many_to_one_relationship(self):
        """Test creating many-to-one relationship field"""
        rel_info = {
            "name": "author",
            "type": "many-to-one",
            "target_table": "user",
            "target_model_name": "User",
            "related_name": "books",
            "django_field_options": {
                "on_delete": "CASCADE",
                "db_column": "author_id",
                "null": True,
                "blank": True
            }
        }

        field_node = create_relationship_field(rel_info)

        assert isinstance(field_node, ast.Assign)
        assert field_node.targets[0].id == "author"

    def test_many_to_many_relationship(self):
        """Test creating many-to-many relationship field"""
        rel_info = {
            "name": "categories",
            "type": "many-to-many",
            "target_table": "category",
            "target_model_name": "Category",
            "related_name": "products",
            "django_field_options": {
                "through": "ProductCategory",
                "through_fields": ("product", "category"),
                "blank": True
            }
        }

        field_node = create_relationship_field(rel_info)

        assert isinstance(field_node, ast.Assign)
        assert field_node.targets[0].id == "categories"

    def test_many_to_many_with_symmetrical(self):
        """Test creating many-to-many with symmetrical option"""
        rel_info = {
            "name": "friends",
            "type": "many-to-many",
            "target_table": "user",
            "target_model_name": "User",
            "related_name": "friends_rel",
            "django_field_options": {
                "symmetrical": False,
                "blank": True
            }
        }

        field_node = create_relationship_field(rel_info)

        assert isinstance(field_node, ast.Assign)
        assert field_node.targets[0].id == "friends"

    def test_unsupported_relationship_type(self):
        """Test error for unsupported relationship type"""
        rel_info = {
            "name": "invalid",
            "type": "one-to-one",
            "target_table": "profile",
            "target_model_name": "Profile"
        }

        with self.assertRaises(ValueError) as context:
            create_relationship_field(rel_info)

        assert "Unsupported relationship type: one-to-one" in str(context.exception)

    def test_many_to_one_minimal_options(self):
        """Test many-to-one with minimal options"""
        rel_info = {
            "name": "category",
            "type": "many-to-one",
            "target_table": "category",
            "target_model_name": "Category",
            "django_field_options": {}
        }

        field_node = create_relationship_field(rel_info)

        assert isinstance(field_node, ast.Assign)
        assert field_node.targets[0].id == "category"

    def test_many_to_many_minimal_options(self):
        """Test many-to-many with minimal options"""
        rel_info = {
            "name": "tags",
            "type": "many-to-many",
            "target_table": "tag",
            "target_model_name": "Tag",
            "django_field_options": {}
        }

        field_node = create_relationship_field(rel_info)

        assert isinstance(field_node, ast.Assign)
        assert field_node.targets[0].id == "tags"


class TestCreateModelMeta(TestCase):
    """Test cases for create_model_meta function"""

    def test_basic_meta_class(self):
        """Test creating basic Meta class"""
        table_info = TableInfo(
            name="user",
            model_name="User",
            primary_key_columns=["id"],
            meta_indexes=[],
            meta_constraints=[],
            relationships=[],
            fields=[]
        )

        meta_class = create_model_meta(table_info)

        assert isinstance(meta_class, ast.ClassDef)
        assert meta_class.name == "Meta"
        assert len(meta_class.body) >= 3  # db_table, verbose_name, verbose_name_plural

    def test_meta_with_indexes(self):
        """Test Meta class with indexes"""
        table_info = TableInfo(
            name="user",
            model_name="User",
            primary_key_columns=["id"],
            meta_indexes=[
                {"fields": ["username"], "name": "idx_username"},
                {"fields": ["email", "username"], "name": "idx_email_username"}
            ],
            meta_constraints=[],
            relationships=[],
            fields=[]
        )

        meta_class = create_model_meta(table_info)

        assert isinstance(meta_class, ast.ClassDef)
        assert meta_class.name == "Meta"

    def test_meta_with_constraints(self):
        """Test Meta class with unique constraints"""
        table_info = TableInfo(
            name="user",
            model_name="User",
            primary_key_columns=["id"],
            meta_indexes=[],
            meta_constraints=[
                {"type": "unique", "fields": ["username", "email"], "name": "unique_user"}
            ],
            relationships=[],
            fields=[]
        )

        meta_class = create_model_meta(table_info)

        assert isinstance(meta_class, ast.ClassDef)
        assert meta_class.name == "Meta"

    def test_meta_with_composite_pk_m2m_through(self):
        """Test Meta class with composite PK for M2M through table"""
        table_info = TableInfo(
            name="user_group",
            model_name="UserGroup",
            primary_key_columns=["user_id", "group_id"],
            meta_indexes=[],
            meta_constraints=[],
            relationships=[
                {
                    "name": "user",
                    "type": "many-to-one",
                    "source_columns": ["user_id"]
                },
                {
                    "name": "group",
                    "type": "many-to-one",
                    "source_columns": ["group_id"]
                }
            ],
            fields=[
                {
                    "name": "user_id",
                    "original_column_name": "user_id",
                    "is_handled_by_relation": False
                },
                {
                    "name": "group_id",
                    "original_column_name": "group_id",
                    "is_handled_by_relation": False
                }
            ]
        )

        with patch('drf_auto_generator.ast_codegen.models.logger') as mock_logger:
            meta_class = create_model_meta(table_info)

            assert isinstance(meta_class, ast.ClassDef)
            mock_logger.debug.assert_called()

    def test_meta_with_composite_pk_non_m2m(self):
        """Test Meta class with composite PK for non-M2M table"""
        table_info = TableInfo(
            name="order_item",
            model_name="OrderItem",
            primary_key_columns=["order_id", "product_id"],
            meta_indexes=[],
            meta_constraints=[],
            relationships=[
                {
                    "name": "order",
                    "type": "many-to-one",
                    "source_columns": ["order_id"]
                }
            ],
            fields=[
                {
                    "name": "order_id",
                    "original_column_name": "order_id",
                    "is_handled_by_relation": False
                },
                {
                    "name": "product_id",
                    "original_column_name": "product_id",
                    "is_handled_by_relation": False
                }
            ]
        )

        with patch('drf_auto_generator.ast_codegen.models.logger') as mock_logger:
            meta_class = create_model_meta(table_info)

            assert isinstance(meta_class, ast.ClassDef)
            mock_logger.debug.assert_called()

    def test_meta_with_composite_pk_fallback_to_column_name(self):
        """Test Meta class with composite PK fallback to column name"""
        table_info = TableInfo(
            name="user_group",
            model_name="UserGroup",
            primary_key_columns=["user_id", "group_id"],
            meta_indexes=[],
            meta_constraints=[],
            relationships=[
                {
                    "name": "user",
                    "type": "many-to-one",
                    "source_columns": ["user_id"]
                },
                {
                    "name": "group",
                    "type": "many-to-one",
                    "source_columns": ["group_id"]
                }
            ],
            fields=[]  # Empty fields to trigger fallback to column name
        )

        with patch('drf_auto_generator.ast_codegen.models.logger') as mock_logger:
            meta_class = create_model_meta(table_info)

            assert isinstance(meta_class, ast.ClassDef)
            mock_logger.debug.assert_called()

    def test_meta_with_constraint_no_name(self):
        """Test Meta class with constraint without name"""
        table_info = TableInfo(
            name="user",
            model_name="User",
            primary_key_columns=["id"],
            meta_indexes=[],
            meta_constraints=[
                {"type": "unique", "fields": ["username", "email"]}
            ],
            relationships=[],
            fields=[]
        )

        meta_class = create_model_meta(table_info)

        assert isinstance(meta_class, ast.ClassDef)
        assert meta_class.name == "Meta"

    def test_meta_with_non_unique_constraint(self):
        """Test Meta class with non-unique constraint (should be ignored)"""
        table_info = TableInfo(
            name="user",
            model_name="User",
            primary_key_columns=["id"],
            meta_indexes=[],
            meta_constraints=[
                {"type": "check", "fields": ["age"], "name": "check_age"}
            ],
            relationships=[],
            fields=[]
        )

        meta_class = create_model_meta(table_info)

        assert isinstance(meta_class, ast.ClassDef)
        assert meta_class.name == "Meta"


class TestCreateStrMethod(TestCase):
    """Test cases for create_str_method function"""

    def test_str_method_with_name_field(self):
        """Test __str__ method with name field"""
        table_info = TableInfo(
            name="user",
            model_name="User",
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="name", db_type_string="CharField", is_pk=False,
                          internal_size=100, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ]
        )

        str_method = create_str_method(table_info)

        assert isinstance(str_method, ast.FunctionDef)
        assert str_method.name == "__str__"
        assert len(str_method.body) >= 1

    def test_str_method_with_title_field(self):
        """Test __str__ method with title field"""
        table_info = TableInfo(
            name="post",
            model_name="Post",
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="title", db_type_string="CharField", is_pk=False,
                          internal_size=200, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ]
        )

        str_method = create_str_method(table_info)

        assert isinstance(str_method, ast.FunctionDef)
        assert str_method.name == "__str__"

    def test_str_method_with_email_field(self):
        """Test __str__ method with email field"""
        table_info = TableInfo(
            name="user",
            model_name="User",
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="email", db_type_string="EmailField", is_pk=False,
                          internal_size=254, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ]
        )

        str_method = create_str_method(table_info)

        assert isinstance(str_method, ast.FunctionDef)
        assert str_method.name == "__str__"

    def test_str_method_fallback_to_pk(self):
        """Test __str__ method fallback to primary key"""
        table_info = TableInfo(
            name="log",
            model_name="Log",
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="message", db_type_string="TextField", is_pk=False,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ]
        )

        str_method = create_str_method(table_info)

        assert isinstance(str_method, ast.FunctionDef)
        assert str_method.name == "__str__"

    def test_str_method_no_pk_field(self):
        """Test __str__ method with no primary key field"""
        table_info = TableInfo(
            name="temp_table",
            model_name="TempTable",
            columns=[
                ColumnInfo(name="message", db_type_string="TextField", is_pk=False,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ]
        )

        str_method = create_str_method(table_info)

        assert isinstance(str_method, ast.FunctionDef)
        assert str_method.name == "__str__"

    def test_str_method_with_multiple_descriptive_fields(self):
        """Test __str__ method with multiple descriptive fields (should pick first)"""
        table_info = TableInfo(
            name="user",
            model_name="User",
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="name", db_type_string="CharField", is_pk=False,
                          internal_size=100, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="username", db_type_string="CharField", is_pk=False,
                          internal_size=50, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ]
        )

        str_method = create_str_method(table_info)

        assert isinstance(str_method, ast.FunctionDef)
        assert str_method.name == "__str__"


class TestCreateModelClass(TestCase):
    """Test cases for create_model_class function"""

    def test_basic_model_class(self):
        """Test creating basic model class"""
        table_info = TableInfo(
            name="user",
            model_name="User",
            primary_key_columns=["id"],
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="username", db_type_string="CharField", is_pk=False,
                          internal_size=100, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[
                {"name": "id", "original_column_name": "id", "is_handled_by_relation": False},
                {"name": "username", "original_column_name": "username", "is_handled_by_relation": False}
            ],
            relationships=[],
            meta_indexes=[],
            meta_constraints=[]
        )

        model_class = create_model_class(table_info)

        assert isinstance(model_class, ast.ClassDef)
        assert model_class.name == "User"
        assert len(model_class.bases) == 1
        assert model_class.bases[0].id == "models.Model"

    def test_model_class_with_composite_pk_m2m_through(self):
        """Test model class with composite PK for M2M through table"""
        table_info = TableInfo(
            name="user_group",
            model_name="UserGroup",
            primary_key_columns=["user_id", "group_id"],
            columns=[
                ColumnInfo(name="user_id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="group_id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[
                {"name": "user_id", "original_column_name": "user_id", "is_handled_by_relation": False},
                {"name": "group_id", "original_column_name": "group_id", "is_handled_by_relation": False}
            ],
            relationships=[
                {
                    "name": "user",
                    "type": "many-to-one",
                    "target_table": "user",
                    "target_model_name": "User",
                    "source_columns": ["user_id"],
                    "django_field_options": {}
                },
                {
                    "name": "group",
                    "type": "many-to-one",
                    "target_table": "group",
                    "target_model_name": "Group",
                    "source_columns": ["group_id"],
                    "django_field_options": {}
                }
            ],
            meta_indexes=[],
            meta_constraints=[]
        )

        with patch('drf_auto_generator.ast_codegen.models.logger') as mock_logger:
            model_class = create_model_class(table_info)

            assert isinstance(model_class, ast.ClassDef)
            mock_logger.debug.assert_called()

    def test_model_class_with_composite_pk_non_m2m(self):
        """Test model class with composite PK for non-M2M table"""
        table_info = TableInfo(
            name="order_item",
            model_name="OrderItem",
            primary_key_columns=["order_id", "product_id"],
            columns=[
                ColumnInfo(name="order_id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="product_id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[
                {"name": "order_id", "original_column_name": "order_id", "is_handled_by_relation": False},
                {"name": "product_id", "original_column_name": "product_id", "is_handled_by_relation": False}
            ],
            relationships=[
                {
                    "name": "order",
                    "type": "many-to-one",
                    "target_table": "order",
                    "target_model_name": "Order",
                    "source_columns": ["order_id"],
                    "django_field_options": {}
                }
            ],
            meta_indexes=[],
            meta_constraints=[]
        )

        with patch('drf_auto_generator.ast_codegen.models.logger') as mock_logger:
            model_class = create_model_class(table_info)

            assert isinstance(model_class, ast.ClassDef)
            mock_logger.info.assert_called()

    def test_model_class_with_handled_by_relation_fields(self):
        """Test model class with fields handled by relationships"""
        table_info = TableInfo(
            name="post",
            model_name="Post",
            primary_key_columns=["id"],
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="title", db_type_string="CharField", is_pk=False,
                          internal_size=200, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="author_id", db_type_string="IntegerField", is_pk=False,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[
                {"name": "id", "original_column_name": "id", "is_handled_by_relation": False},
                {"name": "title", "original_column_name": "title", "is_handled_by_relation": False},
                {"name": "author_id", "original_column_name": "author_id", "is_handled_by_relation": True}
            ],
            relationships=[
                {
                    "name": "author",
                    "type": "many-to-one",
                    "target_table": "user",
                    "target_model_name": "User",
                    "django_field_options": {"on_delete": "CASCADE"}
                }
            ],
            meta_indexes=[],
            meta_constraints=[]
        )

        model_class = create_model_class(table_info)

        assert isinstance(model_class, ast.ClassDef)
        assert model_class.name == "Post"

    def test_model_class_with_composite_pk_field_name_lookup(self):
        """Test model class with composite PK field name lookup"""
        table_info = TableInfo(
            name="complex_key",
            model_name="ComplexKey",
            primary_key_columns=["key1", "key2"],
            columns=[
                ColumnInfo(name="key1", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="key2", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[
                {"name": "key1", "original_column_name": "key1", "is_handled_by_relation": False},
                {"name": "key2", "original_column_name": "key2", "is_handled_by_relation": False}
            ],
            relationships=[],
            meta_indexes=[],
            meta_constraints=[]
        )

        with patch('drf_auto_generator.ast_codegen.models.logger') as mock_logger:
            model_class = create_model_class(table_info)

            assert isinstance(model_class, ast.ClassDef)
            mock_logger.info.assert_called()

    def test_model_class_with_composite_pk_fallback_column_name(self):
        """Test model class with composite PK fallback to column name"""
        table_info = TableInfo(
            name="complex_key",
            model_name="ComplexKey",
            primary_key_columns=["key1", "key2"],
            columns=[
                ColumnInfo(name="key1", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None),
                ColumnInfo(name="key2", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[],  # Empty fields to trigger fallback
            relationships=[],
            meta_indexes=[],
            meta_constraints=[]
        )

        with patch('drf_auto_generator.ast_codegen.models.logger') as mock_logger:
            model_class = create_model_class(table_info)

            assert isinstance(model_class, ast.ClassDef)
            mock_logger.info.assert_called()


class TestGenerateModelsAst(TestCase):
    """Test cases for generate_models_ast function"""

    def test_generate_empty_ast(self):
        """Test generating AST with empty tables list"""
        tables_info = []

        module_ast = generate_models_ast(tables_info)

        assert isinstance(module_ast, ast.Module)
        assert len(module_ast.body) == 1  # Only import statement

    def test_generate_ast_with_tables(self):
        """Test generating AST with tables"""
        table_info = TableInfo(
            name="user",
            model_name="User",
            primary_key_columns=["id"],
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[
                {"name": "id", "original_column_name": "id", "is_handled_by_relation": False}
            ],
            relationships=[],
            meta_indexes=[],
            meta_constraints=[]
        )

        module_ast = generate_models_ast([table_info])

        assert isinstance(module_ast, ast.Module)
        assert len(module_ast.body) == 2  # Import + model class

    def test_generate_ast_skip_table_without_pk(self):
        """Test generating AST skipping table without primary key"""
        table_info = TableInfo(
            name="log",
            model_name="Log",
            primary_key_columns=[],
            columns=[
                ColumnInfo(name="message", db_type_string="TextField", is_pk=False,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[],
            relationships=[],
            meta_indexes=[],
            meta_constraints=[]
        )

        with patch('drf_auto_generator.ast_codegen.models.logger') as mock_logger:
            module_ast = generate_models_ast([table_info])

            assert isinstance(module_ast, ast.Module)
            assert len(module_ast.body) == 1  # Only import statement
            mock_logger.warning.assert_called_with("Table log does not have a primary key, skipping...")

    def test_generate_ast_multiple_tables(self):
        """Test generating AST with multiple tables"""
        table1 = TableInfo(
            name="user",
            model_name="User",
            primary_key_columns=["id"],
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[
                {"name": "id", "original_column_name": "id", "is_handled_by_relation": False}
            ],
            relationships=[],
            meta_indexes=[],
            meta_constraints=[]
        )

        table2 = TableInfo(
            name="post",
            model_name="Post",
            primary_key_columns=["id"],
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[
                {"name": "id", "original_column_name": "id", "is_handled_by_relation": False}
            ],
            relationships=[],
            meta_indexes=[],
            meta_constraints=[]
        )

        module_ast = generate_models_ast([table1, table2])

        assert isinstance(module_ast, ast.Module)
        assert len(module_ast.body) == 3  # Import + 2 model classes


class TestGenerateModelsCode(TestCase):
    """Test cases for generate_models_code function"""

    def test_generate_code_basic(self):
        """Test generating code for basic table"""
        table_info = TableInfo(
            name="user",
            model_name="User",
            primary_key_columns=["id"],
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[
                {"name": "id", "original_column_name": "id", "is_handled_by_relation": False}
            ],
            relationships=[],
            meta_indexes=[],
            meta_constraints=[]
        )

        code = generate_models_code([table_info])

        assert isinstance(code, str)
        assert "from django.db import models" in code
        assert "class User(models.Model):" in code

    def test_generate_code_empty_tables(self):
        """Test generating code for empty tables"""
        code = generate_models_code([])

        assert isinstance(code, str)
        assert "from django.db import models" in code
        assert "class" not in code  # No model classes

    def test_generate_code_multiple_tables(self):
        """Test generating code for multiple tables"""
        table1 = TableInfo(
            name="user",
            model_name="User",
            primary_key_columns=["id"],
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[
                {"name": "id", "original_column_name": "id", "is_handled_by_relation": False}
            ],
            relationships=[],
            meta_indexes=[],
            meta_constraints=[]
        )

        table2 = TableInfo(
            name="post",
            model_name="Post",
            primary_key_columns=["id"],
            columns=[
                ColumnInfo(name="id", db_type_string="IntegerField", is_pk=True,
                          internal_size=None, precision=None, scale=None,
                          nullable=False, default=None, collation=None)
            ],
            fields=[
                {"name": "id", "original_column_name": "id", "is_handled_by_relation": False}
            ],
            relationships=[],
            meta_indexes=[],
            meta_constraints=[]
        )

        code = generate_models_code([table1, table2])

        assert isinstance(code, str)
        assert "from django.db import models" in code
        assert "class User(models.Model):" in code
        assert "class Post(models.Model):" in code


class TestConstants(TestCase):
    """Test cases for module constants"""

    def test_boolean_options_constant(self):
        """Test BOOLEAN_OPTIONS constant"""
        expected_options = {"primary_key", "unique", "null", "blank"}
        assert BOOLEAN_OPTIONS == expected_options

    def test_numeric_options_constant(self):
        """Test NUMERIC_OPTIONS constant"""
        expected_options = {"max_length", "max_digits", "decimal_places"}
        assert NUMERIC_OPTIONS == expected_options
