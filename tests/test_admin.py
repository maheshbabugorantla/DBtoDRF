"""
Tests for Django Admin Code Generator

This module tests the admin.py AST code generator with comprehensive coverage.
"""

import ast
from unittest import TestCase
from unittest.mock import patch

from drf_auto_generator.ast_codegen.admin import (
    _has_composite_primary_key,
    _should_skip_admin_registration,
    create_admin_class,
    generate_admin_code,
)
from drf_auto_generator.introspection_django import TableInfo


class TestHasCompositePrimaryKey(TestCase):
    """Test cases for _has_composite_primary_key function"""

    def test_no_primary_key(self):
        """Test table with no primary key"""
        table_info = TableInfo(
            name="test_table",
            primary_key_columns=[],
            is_m2m_through_table=False
        )
        assert _has_composite_primary_key(table_info) is False

    def test_single_primary_key(self):
        """Test table with single primary key"""
        table_info = TableInfo(
            name="test_table",
            primary_key_columns=["id"],
            is_m2m_through_table=False
        )
        assert _has_composite_primary_key(table_info) is False

    def test_composite_primary_key_not_m2m(self):
        """Test table with composite primary key that is not M2M through table"""
        table_info = TableInfo(
            name="test_table",
            primary_key_columns=["id1", "id2"],
            is_m2m_through_table=False
        )
        assert _has_composite_primary_key(table_info) is True

    def test_composite_primary_key_m2m_through(self):
        """Test table with composite primary key that is M2M through table"""
        table_info = TableInfo(
            name="test_table",
            primary_key_columns=["id1", "id2"],
            is_m2m_through_table=True
        )
        assert _has_composite_primary_key(table_info) is False

    def test_multiple_primary_keys(self):
        """Test table with multiple primary keys"""
        table_info = TableInfo(
            name="test_table",
            primary_key_columns=["id1", "id2", "id3"],
            is_m2m_through_table=False
        )
        assert _has_composite_primary_key(table_info) is True


class TestShouldSkipAdminRegistration(TestCase):
    """Test cases for _should_skip_admin_registration function"""

    def test_skip_m2m_through_table(self):
        """Test skipping M2M through table"""
        table_info = TableInfo(
            name="test_table",
            primary_key_columns=["id1", "id2"],
            is_m2m_through_table=True
        )
        assert _should_skip_admin_registration(table_info) is True

    def test_skip_composite_primary_key(self):
        """Test skipping composite primary key table"""
        table_info = TableInfo(
            name="test_table",
            primary_key_columns=["id1", "id2"],
            is_m2m_through_table=False
        )
        assert _should_skip_admin_registration(table_info) is True

    def test_do_not_skip_normal_table(self):
        """Test not skipping normal table"""
        table_info = TableInfo(
            name="test_table",
            primary_key_columns=["id"],
            is_m2m_through_table=False
        )
        assert _should_skip_admin_registration(table_info) is False

    def test_do_not_skip_empty_pk(self):
        """Test not skipping table with empty primary key"""
        table_info = TableInfo(
            name="test_table",
            primary_key_columns=[],
            is_m2m_through_table=False
        )
        assert _should_skip_admin_registration(table_info) is False


class TestCreateAdminClass(TestCase):
    """Test cases for create_admin_class function"""

    def test_basic_admin_class(self):
        """Test creating basic admin class"""
        table_info = TableInfo(
            name="user",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                },
                {
                    "name": "username",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "email",
                    "type": "EmailField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        admin_class = create_admin_class(table_info)

        assert isinstance(admin_class, ast.ClassDef)
        assert admin_class.name == "UserAdmin"
        assert len(admin_class.bases) == 1
        assert admin_class.bases[0].id == "admin.ModelAdmin"
        assert len(admin_class.body) >= 1  # Should have at least list_display

    def test_admin_class_with_relationships(self):
        """Test creating admin class with relationships"""
        table_info = TableInfo(
            name="order",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                },
                {
                    "name": "total",
                    "type": "DecimalField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "created_at",
                    "type": "DateTimeField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[
                {
                    "name": "customer",
                    "type": "many-to-one",
                    "target_table": "customer",
                    "target_model_name": "Customer"
                }
            ],
            is_m2m_through_table=False
        )

        admin_class = create_admin_class(table_info)

        assert isinstance(admin_class, ast.ClassDef)
        assert admin_class.name == "OrderAdmin"
        assert len(admin_class.body) >= 1

    def test_admin_class_with_search_fields(self):
        """Test creating admin class with search fields"""
        table_info = TableInfo(
            name="product",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                },
                {
                    "name": "name",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "description",
                    "type": "TextField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        admin_class = create_admin_class(table_info)

        assert isinstance(admin_class, ast.ClassDef)
        assert admin_class.name == "ProductAdmin"

    def test_admin_class_with_filter_fields(self):
        """Test creating admin class with filter fields"""
        table_info = TableInfo(
            name="article",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                },
                {
                    "name": "title",
                    "type": "CharField",
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
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        admin_class = create_admin_class(table_info)

        assert isinstance(admin_class, ast.ClassDef)
        assert admin_class.name == "ArticleAdmin"

    def test_admin_class_with_handled_by_relation_fields(self):
        """Test creating admin class with fields handled by relations"""
        table_info = TableInfo(
            name="comment",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                },
                {
                    "name": "content",
                    "type": "TextField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "author_id",
                    "type": "IntegerField",
                    "is_pk": False,
                    "is_handled_by_relation": True
                }
            ],
            relationships=[
                {
                    "name": "author",
                    "type": "many-to-one",
                    "target_table": "user",
                    "target_model_name": "User"
                }
            ],
            is_m2m_through_table=False
        )

        admin_class = create_admin_class(table_info)

        assert isinstance(admin_class, ast.ClassDef)
        assert admin_class.name == "CommentAdmin"

    def test_admin_class_no_pk_field(self):
        """Test creating admin class with no primary key field"""
        table_info = TableInfo(
            name="log",
            primary_key_columns=[],
            fields=[
                {
                    "name": "message",
                    "type": "TextField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "level",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        admin_class = create_admin_class(table_info)

        assert isinstance(admin_class, ast.ClassDef)
        assert admin_class.name == "LogAdmin"

    def test_admin_class_with_many_fields(self):
        """Test creating admin class with many fields (should limit to 5)"""
        table_info = TableInfo(
            name="detailed_record",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                },
                {
                    "name": "field1",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "field2",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "field3",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "field4",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "field5",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "field6",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        admin_class = create_admin_class(table_info)

        assert isinstance(admin_class, ast.ClassDef)
        assert admin_class.name == "DetailedRecordAdmin"

    def test_admin_class_with_many_relationships_break_limit(self):
        """Test creating admin class with many relationships that triggers break limit"""
        table_info = TableInfo(
            name="order_item",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                },
                {
                    "name": "quantity",
                    "type": "IntegerField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "price",
                    "type": "DecimalField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "discount",
                    "type": "DecimalField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "tax",
                    "type": "DecimalField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[
                {
                    "name": "order",
                    "type": "many-to-one",
                    "target_table": "order",
                    "target_model_name": "Order"
                },
                {
                    "name": "product",
                    "type": "many-to-one",
                    "target_table": "product",
                    "target_model_name": "Product"
                },
                {
                    "name": "supplier",
                    "type": "many-to-one",
                    "target_table": "supplier",
                    "target_model_name": "Supplier"
                },
                {
                    "name": "warehouse",
                    "type": "many-to-one",
                    "target_table": "warehouse",
                    "target_model_name": "Warehouse"
                }
            ],
            is_m2m_through_table=False
        )

        admin_class = create_admin_class(table_info)

        assert isinstance(admin_class, ast.ClassDef)
        assert admin_class.name == "OrderItemAdmin"


class TestGenerateAdminCode(TestCase):
    """Test cases for generate_admin_code function"""

    def test_generate_admin_code_basic(self):
        """Test generating admin code for basic tables"""
        table_info = TableInfo(
            name="user",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                },
                {
                    "name": "username",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        code = generate_admin_code([table_info])

        assert isinstance(code, str)
        assert "from django.contrib import admin" in code
        assert "from .models import User" in code
        assert "class UserAdmin(admin.ModelAdmin):" in code
        assert "admin.site.register(User, UserAdmin)" in code

    def test_generate_admin_code_custom_models_module(self):
        """Test generating admin code with custom models module"""
        table_info = TableInfo(
            name="product",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        code = generate_admin_code([table_info], models_module="custom_models")

        assert isinstance(code, str)
        assert "from custom_models import Product" in code

    def test_generate_admin_code_skip_m2m_through(self):
        """Test generating admin code skipping M2M through tables"""
        regular_table = TableInfo(
            name="user",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        m2m_table = TableInfo(
            name="user_group",
            primary_key_columns=["user_id", "group_id"],
            fields=[
                {
                    "name": "user_id",
                    "type": "IntegerField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                },
                {
                    "name": "group_id",
                    "type": "IntegerField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=True
        )

        with patch('drf_auto_generator.ast_codegen.admin.logger') as mock_logger:
            code = generate_admin_code([regular_table, m2m_table])

            assert isinstance(code, str)
            assert "User" in code
            assert "UserGroup" not in code
            mock_logger.info.assert_called_with("Skipping admin registration for M2M through table: user_group")

    def test_generate_admin_code_skip_composite_pk(self):
        """Test generating admin code skipping composite primary key tables"""
        regular_table = TableInfo(
            name="user",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        composite_pk_table = TableInfo(
            name="composite_table",
            primary_key_columns=["id1", "id2"],
            fields=[
                {
                    "name": "id1",
                    "type": "IntegerField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                },
                {
                    "name": "id2",
                    "type": "IntegerField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        with patch('drf_auto_generator.ast_codegen.admin.logger') as mock_logger:
            code = generate_admin_code([regular_table, composite_pk_table])

            assert isinstance(code, str)
            assert "User" in code
            assert "CompositeTable" not in code
            mock_logger.info.assert_called_with("Skipping admin registration for composite primary key table: composite_table")

    def test_generate_admin_code_no_primary_key(self):
        """Test generating admin code for table without primary key"""
        table_info = TableInfo(
            name="log",
            primary_key_columns=[],
            fields=[
                {
                    "name": "message",
                    "type": "TextField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        with patch('drf_auto_generator.ast_codegen.admin.logger') as mock_logger:
            code = generate_admin_code([table_info])

            assert isinstance(code, str)
            mock_logger.warning.assert_called_with("Table log does not have a primary key, skipping admin generation...")

    def test_generate_admin_code_empty_tables(self):
        """Test generating admin code for empty tables list"""
        code = generate_admin_code([])

        assert isinstance(code, str)
        assert "from django.contrib import admin" in code
        # Should not have any model imports since no tables
        assert "from .models import" not in code

    def test_generate_admin_code_no_models_to_include(self):
        """Test generating admin code when no models should be included"""
        # All tables are skipped (M2M through tables)
        m2m_table = TableInfo(
            name="user_group",
            primary_key_columns=["user_id", "group_id"],
            fields=[],
            relationships=[],
            is_m2m_through_table=True
        )

        code = generate_admin_code([m2m_table])

        assert isinstance(code, str)
        assert "from django.contrib import admin" in code
        # Should not have any model imports
        assert "from .models import" not in code

    def test_generate_admin_code_multiple_tables(self):
        """Test generating admin code for multiple tables"""
        table1 = TableInfo(
            name="user",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        table2 = TableInfo(
            name="product",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        code = generate_admin_code([table1, table2])

        assert isinstance(code, str)
        assert "from django.contrib import admin" in code
        assert "from .models import User, Product" in code
        assert "class UserAdmin(admin.ModelAdmin):" in code
        assert "class ProductAdmin(admin.ModelAdmin):" in code
        assert "admin.site.register(User, UserAdmin)" in code
        assert "admin.site.register(Product, ProductAdmin)" in code

    def test_generate_admin_code_with_special_field_names(self):
        """Test generating admin code with special field names"""
        table_info = TableInfo(
            name="user",
            primary_key_columns=["id"],
            fields=[
                {
                    "name": "id",
                    "type": "AutoField",
                    "is_pk": True,
                    "is_handled_by_relation": False
                },
                {
                    "name": "name",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "title",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "email",
                    "type": "EmailField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "username",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "code",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                },
                {
                    "name": "status",
                    "type": "CharField",
                    "is_pk": False,
                    "is_handled_by_relation": False
                }
            ],
            relationships=[],
            is_m2m_through_table=False
        )

        code = generate_admin_code([table_info])

        assert isinstance(code, str)
        assert "UserAdmin" in code
