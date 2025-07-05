"""
Unit tests for openapi_gen.py helper functions and core functionality.
"""
import unittest
from unittest.mock import Mock, patch

from drf_auto_generator.openapi_gen import (
    _create_path_parameter,
    _create_standard_responses,
    _create_pagination_schema,
    _build_query_parameters,
    _filter_db_fields,
    _create_field_parameter,
    generate_openapi_schema_object,
    generate_openapi_input_schema,
    _generate_list_endpoint,
    _generate_create_endpoint,
    _generate_detail_endpoint,
    _generate_update_endpoint,
    _generate_patch_endpoint,
    _generate_delete_endpoint
)


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions that create OpenAPI components."""

    def test_create_path_parameter_basic(self):
        """Test basic path parameter creation."""
        result = _create_path_parameter("id", "User ID", {"type": "integer"})

        expected = {
            "name": "id",
            "in": "path",
            "required": True,
            "description": "User ID",
            "schema": {"type": "integer"}
        }

        self.assertEqual(result, expected)

    def test_create_path_parameter_complex_schema(self):
        """Test path parameter with complex schema."""
        complex_schema = {
            "type": "string",
            "format": "uuid",
            "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        }

        result = _create_path_parameter("uuid", "UUID identifier", complex_schema)

        self.assertEqual(result["schema"], complex_schema)
        self.assertEqual(result["name"], "uuid")

    def test_create_path_parameter_empty_description(self):
        """Test path parameter with empty description."""
        result = _create_path_parameter("test", "", {"type": "string"})

        self.assertEqual(result["description"], "")
        self.assertEqual(result["name"], "test")

    def test_create_standard_responses_basic(self):
        """Test standard response creation."""
        model_name = "User"
        schema_ref = "#/components/schemas/User"

        responses = _create_standard_responses(model_name, schema_ref)

        # Check all required response types exist
        self.assertIn("retrieve", responses)
        self.assertIn("create", responses)
        self.assertIn("update", responses)
        self.assertIn("delete", responses)

        # Check retrieve response structure
        retrieve_resp = responses["retrieve"]
        self.assertIn("200", retrieve_resp)
        self.assertIn("404", retrieve_resp)
        self.assertIn("default", retrieve_resp)

        # Check 200 response has correct schema reference
        self.assertEqual(
            retrieve_resp["200"]["content"]["application/json"]["schema"]["$ref"],
            schema_ref
        )

    def test_create_pagination_schema_structure(self):
        """Test pagination schema creation."""
        schema_ref = "#/components/schemas/User"
        model_name = "User"

        result = _create_pagination_schema(schema_ref, model_name)

        # Check required pagination fields
        expected_props = ["count", "next", "previous", "results"]
        for prop in expected_props:
            self.assertIn(prop, result["properties"])

        # Check results array structure
        results_prop = result["properties"]["results"]
        self.assertEqual(results_prop["type"], "array")
        self.assertEqual(results_prop["items"]["$ref"], schema_ref)

        # Check nullable fields
        self.assertTrue(result["properties"]["next"]["nullable"])
        self.assertTrue(result["properties"]["previous"]["nullable"])

    def test_filter_db_fields_basic(self):
        """Test filtering of database fields."""
        mock_table = Mock()
        mock_table.fields = [
            {"name": "id", "is_handled_by_relation": False},
            {"name": "username", "is_handled_by_relation": False},
            {"name": "author_rel", "is_handled_by_relation": True},  # Should be filtered
            {"name": "category_id", "is_handled_by_relation": True}  # Should be filtered
        ]

        field_names = ["id", "username", "author_rel", "category_id"]
        result = _filter_db_fields(mock_table, field_names)

        self.assertEqual(result, ["id", "username"])

    def test_filter_db_fields_with_rel_suffix(self):
        """Test filtering fields ending with '_rel'."""
        mock_table = Mock()
        mock_table.fields = [
            {"name": "id", "is_handled_by_relation": False},
            {"name": "title", "is_handled_by_relation": False},
            {"name": "author_rel", "is_handled_by_relation": False}  # Should be filtered due to suffix
        ]

        field_names = ["id", "title", "author_rel"]
        result = _filter_db_fields(mock_table, field_names)

        self.assertEqual(result, ["id", "title"])

    def test_filter_db_fields_empty_input(self):
        """Test filtering with empty field list."""
        mock_table = Mock()
        mock_table.fields = []

        result = _filter_db_fields(mock_table, [])

        self.assertEqual(result, [])

    def test_create_field_parameter_query_type(self):
        """Test field parameter creation for query parameters."""
        field_schema = {"type": "string", "maxLength": 100}

        result = _create_field_parameter("username", field_schema, "query", True)

        expected = {
            "name": "username",
            "in": "query",
            "required": True,
            "description": "The username to filter by",
            "schema": field_schema
        }

        self.assertEqual(result, expected)

    def test_create_field_parameter_path_type(self):
        """Test field parameter creation for path parameters."""
        field_schema = {"type": "integer"}

        result = _create_field_parameter("user_id", field_schema, "path", True)

        expected = {
            "name": "value",  # Path params use 'value' as name
            "in": "path",
            "required": True,
            "description": "The user_id value to look up",
            "schema": field_schema
        }

        self.assertEqual(result, expected)

    def test_create_field_parameter_optional(self):
        """Test optional field parameter creation."""
        field_schema = {"type": "string"}

        result = _create_field_parameter("search", field_schema, "query", False)

        self.assertEqual(result["required"], False)
        self.assertEqual(result["name"], "search")


class TestBuildQueryParameters(unittest.TestCase):
    """Test the _build_query_parameters function."""

    def setUp(self):
        """Set up mock table for testing."""
        self.mock_table = Mock()
        self.mock_table.relationships = []
        self.mock_table.meta_indexes = []
        self.mock_table.fields = []

    def test_standard_pagination_parameters(self):
        """Test that standard pagination parameters are included."""
        result = _build_query_parameters(self.mock_table)

        param_names = [p["name"] for p in result]

        # Check standard pagination/search params
        self.assertIn("page", param_names)
        self.assertIn("page_size", param_names)
        self.assertIn("ordering", param_names)
        self.assertIn("search", param_names)

        # Check page parameter details
        page_param = next(p for p in result if p["name"] == "page")
        self.assertEqual(page_param["schema"]["default"], 1)
        self.assertEqual(page_param["schema"]["type"], "integer")

    def test_relationship_filter_parameters(self):
        """Test that relationship filter parameters are added."""
        self.mock_table.relationships = [
            {"type": "many-to-one", "name": "author"},
            {"type": "one-to-many", "name": "comments"},  # Should be skipped
            {"type": "many-to-one", "name": "category"}
        ]

        result = _build_query_parameters(self.mock_table)
        param_names = [p["name"] for p in result]

        # Should include many-to-one relationships
        self.assertIn("author", param_names)
        self.assertIn("category", param_names)

        # Should not include one-to-many relationships
        self.assertNotIn("comments", param_names)

    def test_indexed_field_parameters(self):
        """Test that indexed field parameters are added."""
        self.mock_table.meta_indexes = [
            {"fields": ["title", "status"]},
            {"fields": ["created_at"]}
        ]
        self.mock_table.fields = [
            {"name": "title", "is_pk": False, "openapi_schema": {"type": "string"}},
            {"name": "status", "is_pk": False, "openapi_schema": {"type": "string"}},
            {"name": "created_at", "is_pk": False, "openapi_schema": {"type": "string", "format": "date-time"}}
        ]

        result = _build_query_parameters(self.mock_table)
        param_names = [p["name"] for p in result]

        self.assertIn("title", param_names)
        self.assertIn("status", param_names)
        self.assertIn("created_at", param_names)

    def test_unique_field_parameters(self):
        """Test that unique field parameters are added."""
        self.mock_table.fields = [
            {"name": "id", "is_pk": True, "options": {"unique": True}},  # Should be skipped (PK)
            {"name": "username", "is_pk": False, "options": {"unique": True}, "openapi_schema": {"type": "string"}},
            {"name": "email", "is_pk": False, "options": {"unique": True}, "openapi_schema": {"type": "string", "format": "email"}}
        ]

        result = _build_query_parameters(self.mock_table)
        param_names = [p["name"] for p in result]

        # Should include unique fields but not primary key
        self.assertIn("username", param_names)
        self.assertIn("email", param_names)
        self.assertNotIn("id", param_names)

    def test_no_duplicate_parameters(self):
        """Test that duplicate parameters are not added."""
        self.mock_table.relationships = [
            {"type": "many-to-one", "name": "author"}
        ]
        self.mock_table.meta_indexes = [
            {"fields": ["author"]}  # Same field as relationship
        ]
        self.mock_table.fields = [
            {"name": "author", "is_pk": False, "openapi_schema": {"type": "integer"}}
        ]

        result = _build_query_parameters(self.mock_table)
        param_names = [p["name"] for p in result]

        # Should only appear once
        self.assertEqual(param_names.count("author"), 1)


class TestSchemaGeneration(unittest.TestCase):
    """Test schema generation functions."""

    def setUp(self):
        """Set up mock table and config for testing."""
        self.mock_table = Mock()
        self.mock_table.fields = [
            {
                "name": "id",
                "is_pk": True,
                "is_handled_by_relation": False,
                "original_column_name": "id",
                "openapi_schema": {"type": "integer", "nullable": False}
            },
            {
                "name": "username",
                "is_pk": False,
                "is_handled_by_relation": False,
                "original_column_name": "username",
                "openapi_schema": {"type": "string", "nullable": False}
            }
        ]
        self.mock_table.columns = [
            Mock(name="id", nullable=False, default=None),
            Mock(name="username", nullable=False, default=None)
        ]
        self.mock_table.relationships = []

        self.config = {"relation_style": "pk"}

    def test_generate_openapi_schema_object_basic(self):
        """Test basic schema object generation."""
        result = generate_openapi_schema_object(self.mock_table, self.config)

        self.assertEqual(result["type"], "object")
        self.assertIn("properties", result)

        # Check that fields are included
        self.assertIn("id", result["properties"])
        self.assertIn("username", result["properties"])

        # Check field schemas
        self.assertEqual(result["properties"]["id"]["type"], "integer")
        self.assertEqual(result["properties"]["username"]["type"], "string")

    def test_generate_openapi_schema_object_with_relationships(self):
        """Test schema generation with relationships."""
        self.mock_table.relationships = [
            {
                "name": "author",
                "type": "many-to-one",
                "target_model_name": "User",
                "django_field_options": {"null": True}
            }
        ]

        result = generate_openapi_schema_object(self.mock_table, self.config)

        # With pk relation style, relationship should not add extra properties
        # (assuming FK field is already in fields)
        self.assertIn("properties", result)

    def test_generate_openapi_input_schema_excludes_readonly(self):
        """Test that input schema excludes read-only fields."""
        # Add a read-only field
        self.mock_table.fields.append({
            "name": "created_at",
            "is_pk": False,
            "is_handled_by_relation": False,
            "original_column_name": "created_at",
            "openapi_schema": {"type": "string", "format": "date-time", "readOnly": True}
        })

        result = generate_openapi_input_schema(self.mock_table, self.config)

        # Should not include read-only fields
        self.assertNotIn("created_at", result["properties"])
        self.assertIn("username", result["properties"])

    @patch('drf_auto_generator.openapi_gen.generate_openapi_schema_object')
    def test_generate_openapi_input_schema_calls_main_schema(self, mock_schema_gen):
        """Test that input schema generation calls main schema generation."""
        mock_schema_gen.return_value = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "username": {"type": "string"},
                "readonly_field": {"type": "string", "readOnly": True}
            }
        }

        result = generate_openapi_input_schema(self.mock_table, self.config)

        # Should have called main schema generation
        mock_schema_gen.assert_called_once_with(self.mock_table, self.config)

        # Should exclude readonly field
        self.assertNotIn("readonly_field", result["properties"])


class TestEndpointGeneration(unittest.TestCase):
    """Test endpoint generation functions."""

    def setUp(self):
        """Set up test data."""
        self.mock_table = Mock()
        self.mock_table.relationships = []
        self.mock_table.meta_indexes = []
        self.mock_table.fields = []

        self.model_name = "User"
        self.table_name_plural = "users"
        self.tag_name = "User"
        self.schema_ref = "#/components/schemas/User"
        self.input_schema_ref = "#/components/schemas/UserInput"

    @patch('drf_auto_generator.openapi_gen._build_query_parameters')
    @patch('drf_auto_generator.openapi_gen._create_pagination_schema')
    @patch('drf_auto_generator.openapi_gen.p')
    def test_generate_list_endpoint(self, mock_p, mock_pagination, mock_query_params):
        """Test list endpoint generation."""
        mock_p.plural.return_value = "Users"
        mock_query_params.return_value = [
            {"name": "page", "in": "query", "required": False}
        ]
        mock_pagination.return_value = {"type": "object", "properties": {}}

        result = _generate_list_endpoint(
            self.mock_table, self.model_name, self.table_name_plural,
            self.tag_name, self.schema_ref
        )

        # Check basic structure
        self.assertIn("tags", result)
        self.assertIn("summary", result)
        self.assertIn("operationId", result)
        self.assertIn("parameters", result)
        self.assertIn("responses", result)

        # Check that required functions were called
        mock_query_params.assert_called_once_with(self.mock_table)
        mock_pagination.assert_called_once_with(self.schema_ref, self.model_name)

    def test_generate_create_endpoint(self):
        """Test create endpoint generation."""
        result = _generate_create_endpoint(
            self.model_name, self.tag_name, self.input_schema_ref
        )

        # Check basic structure
        self.assertIn("tags", result)
        self.assertIn("summary", result)
        self.assertIn("operationId", result)
        self.assertIn("requestBody", result)
        self.assertIn("responses", result)

        # Check request body content types
        content = result["requestBody"]["content"]
        self.assertIn("application/json", content)
        self.assertIn("application/x-www-form-urlencoded", content)
        self.assertIn("multipart/form-data", content)

        # Check schema reference
        self.assertEqual(
            content["application/json"]["schema"]["$ref"],
            self.input_schema_ref
        )

    def test_generate_detail_endpoint(self):
        """Test detail endpoint generation."""
        result = _generate_detail_endpoint(
            self.model_name, self.tag_name, self.schema_ref
        )

        # Check basic structure
        self.assertIn("tags", result)
        self.assertIn("summary", result)
        self.assertIn("operationId", result)
        self.assertIn("responses", result)

        # Check response structure
        responses = result["responses"]
        self.assertIn("200", responses)
        self.assertIn("404", responses)
        self.assertIn("default", responses)

    def test_generate_update_endpoint(self):
        """Test update endpoint generation."""
        result = _generate_update_endpoint(
            self.model_name, self.tag_name, self.input_schema_ref
        )

        # Check basic structure
        self.assertIn("requestBody", result)
        self.assertIn("responses", result)

        # Check that it's a PUT operation (has required body)
        self.assertTrue(result["requestBody"]["required"])

    def test_generate_patch_endpoint(self):
        """Test patch endpoint generation."""
        patch_schema_ref = "#/components/schemas/UserPatchInput"

        result = _generate_patch_endpoint(
            self.model_name, self.tag_name, patch_schema_ref
        )

        # Check basic structure
        self.assertIn("requestBody", result)
        self.assertIn("responses", result)

        # Check that it uses patch schema
        self.assertEqual(
            result["requestBody"]["content"]["application/json"]["schema"]["$ref"],
            patch_schema_ref
        )

    def test_generate_delete_endpoint(self):
        """Test delete endpoint generation."""
        result = _generate_delete_endpoint(self.model_name, self.tag_name)

        # Check basic structure
        self.assertIn("responses", result)

        # Check response codes
        responses = result["responses"]
        self.assertIn("204", responses)  # No content for successful delete
        self.assertIn("404", responses)
        self.assertIn("default", responses)


if __name__ == '__main__':
    unittest.main()
