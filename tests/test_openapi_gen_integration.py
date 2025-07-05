"""
Integration tests for openapi_gen.py main functions and workflows.
"""
import unittest
from unittest.mock import Mock, patch
import sys
import os
import tempfile
import json
import yaml

# Add the parent directory to Python path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from drf_auto_generator.openapi_gen import (
    generate_paths_for_table,
    generate_endpoints_on_table_indexes_and_constraints,
    generate_m2m_endpoints,
    generate_openapi_spec,
    save_openapi_spec,
    _generate_unique_field_endpoints,
    _generate_composite_constraint_endpoints,
    _generate_index_endpoints
)


class TestGeneratePathsForTable(unittest.TestCase):
    """Test the main generate_paths_for_table function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_table = Mock()
        self.mock_table.name = "users"
        self.mock_table.model_name = "User"
        self.mock_table.is_m2m_through_table = False
        self.mock_table.fields = [
            {
                "name": "id",
                "is_pk": True,
                "openapi_schema": {"type": "integer"}
            },
            {
                "name": "username",
                "is_pk": False,
                "options": {"unique": True},
                "openapi_schema": {"type": "string"}
            }
        ]
        self.mock_table.relationships = []
        self.mock_table.meta_indexes = []
        self.mock_table.meta_constraints = []

        self.config = {"relation_style": "pk"}

    @patch('drf_auto_generator.openapi_gen.p')
    def test_basic_crud_path_generation(self, mock_p):
        """Test that basic CRUD paths are generated."""
        mock_p.plural.return_value = "users"

        result = generate_paths_for_table(self.mock_table, self.config)

        # Should generate list/create and detail paths
        self.assertIn("/users", result)
        self.assertIn("/users/{id}", result)

        # Check list/create path operations
        list_create_path = result["/users"]
        self.assertIn("get", list_create_path)  # List operation
        self.assertIn("post", list_create_path)  # Create operation

        # Check detail path operations
        detail_path = result["/users/{id}"]
        self.assertIn("get", detail_path)     # Retrieve operation
        self.assertIn("put", detail_path)     # Update operation
        self.assertIn("patch", detail_path)   # Partial update operation
        self.assertIn("delete", detail_path)  # Delete operation
        self.assertIn("parameters", detail_path)  # Path parameters

    def test_m2m_through_table_skipping(self):
        """Test that M2M through tables are skipped."""
        self.mock_table.is_m2m_through_table = True

        result = generate_paths_for_table(self.mock_table, self.config)

        # Should return empty dict for M2M through tables
        self.assertEqual(result, {})

    def test_missing_primary_key_handling(self):
        """Test handling of tables without primary keys."""
        # Remove primary key field
        self.mock_table.fields = [
            {"name": "username", "is_pk": False, "openapi_schema": {"type": "string"}}
        ]

        with self.assertLogs('drf_auto_generator.openapi_gen', level='WARNING') as log:
            result = generate_paths_for_table(self.mock_table, self.config)

        # Should return empty dict and log warning
        self.assertEqual(result, {})
        self.assertIn("no primary key field", log.output[0])

    @patch('drf_auto_generator.openapi_gen.generate_endpoints_on_table_indexes_and_constraints')
    def test_constraint_endpoints_integration_enabled(self, mock_constraint_gen):
        """Test integration with constraint endpoints when enabled."""
        mock_constraint_gen.return_value = {
            "/users/by_username/{value}": {"get": {"summary": "Get by username"}}
        }

        config = {"relation_style": "pk", "enable_constraint_endpoints": True}

        with patch('drf_auto_generator.openapi_gen.p') as mock_p:
            mock_p.plural.return_value = "users"
            result = generate_paths_for_table(self.mock_table, config)

        # Should include constraint endpoints
        mock_constraint_gen.assert_called_once_with(self.mock_table, config)
        self.assertIn("/users/by_username/{value}", result)

    @patch('drf_auto_generator.openapi_gen.generate_endpoints_on_table_indexes_and_constraints')
    def test_constraint_endpoints_integration_disabled(self, mock_constraint_gen):
        """Test that constraint endpoints are not called when disabled."""
        config = {"relation_style": "pk", "enable_constraint_endpoints": False}

        with patch('drf_auto_generator.openapi_gen.p') as mock_p:
            mock_p.plural.return_value = "users"
            result = generate_paths_for_table(self.mock_table, config)

        # Should not call constraint endpoint generation
        mock_constraint_gen.assert_not_called()

    @patch('drf_auto_generator.openapi_gen.generate_m2m_endpoints')
    def test_m2m_endpoints_integration_enabled(self, mock_m2m_gen):
        """Test integration with M2M endpoints when enabled."""
        mock_m2m_gen.return_value = {
            "/users/{user_id}/tags": {"get": {"summary": "List user tags"}}
        }

        config = {"relation_style": "pk", "enable_m2m_endpoints": True}

        with patch('drf_auto_generator.openapi_gen.p') as mock_p:
            mock_p.plural.return_value = "users"
            result = generate_paths_for_table(self.mock_table, config)

        # Should include M2M endpoints
        mock_m2m_gen.assert_called_once_with(self.mock_table, config)
        self.assertIn("/users/{user_id}/tags", result)

    @patch('drf_auto_generator.openapi_gen.p')
    def test_pluralization_fallback(self, mock_p):
        """Test pluralization fallback when inflect fails."""
        # Mock inflect to raise exception
        mock_p.plural.side_effect = Exception("Inflect error")

        result = generate_paths_for_table(self.mock_table, self.config)

        # Should fallback to simple pluralization
        self.assertIn("/userss", result)  # Simple fallback: name + 's'

    def test_schema_reference_consistency(self):
        """Test that schema references are consistent."""
        with patch('drf_auto_generator.openapi_gen.p') as mock_p:
            mock_p.plural.return_value = "users"
            result = generate_paths_for_table(self.mock_table, self.config)

        # Check that all schema references use the same model name
        list_response = result["/users"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        detail_response = result["/users/{id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

        # Both should reference the same schema
        self.assertEqual(detail_response["$ref"], "#/components/schemas/User")


class TestConstraintEndpointGeneration(unittest.TestCase):
    """Test constraint-based endpoint generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_table = Mock()
        self.mock_table.name = "articles"
        self.mock_table.model_name = "Article"
        self.mock_table.fields = [
            {"name": "id", "is_pk": True, "is_handled_by_relation": False},
            {"name": "slug", "is_pk": False, "is_handled_by_relation": False,
             "options": {"unique": True}, "openapi_schema": {"type": "string"}},
            {"name": "title", "is_pk": False, "is_handled_by_relation": False,
             "options": {}, "openapi_schema": {"type": "string"}},
            {"name": "author_rel", "is_pk": False, "is_handled_by_relation": True}  # Should be filtered
        ]
        self.mock_table.meta_constraints = []
        self.mock_table.meta_indexes = []

        self.config = {"relation_style": "pk"}

    @patch('drf_auto_generator.openapi_gen.p')
    def test_unique_field_endpoints_generation(self, mock_p):
        """Test generation of unique field endpoints."""
        mock_p.plural.return_value = "articles"

        result = _generate_unique_field_endpoints(
            self.mock_table, "Article", "articles", "Article", "#/components/schemas/Article"
        )

        # Should generate endpoint for unique slug field
        self.assertIn("/articles/by_slug/{value}", result)

        # Should not generate endpoint for primary key or relationship fields
        self.assertNotIn("/articles/by_id/{value}", result)
        self.assertNotIn("/articles/by_author_rel/{value}", result)

        # Check endpoint structure
        slug_endpoint = result["/articles/by_slug/{value}"]
        self.assertIn("parameters", slug_endpoint)
        self.assertIn("get", slug_endpoint)

        # Check parameter structure
        param = slug_endpoint["parameters"][0]
        self.assertEqual(param["name"], "value")
        self.assertEqual(param["in"], "path")
        self.assertTrue(param["required"])

    def test_composite_constraint_endpoints_generation(self):
        """Test generation of composite constraint endpoints."""
        self.mock_table.meta_constraints = [
            {
                "type": "unique",
                "fields": ["title", "author_id"]  # Composite unique constraint
            }
        ]

        # Add author_id field
        self.mock_table.fields.append({
            "name": "author_id",
            "is_pk": False,
            "is_handled_by_relation": False,
            "openapi_schema": {"type": "integer"}
        })

        result = _generate_composite_constraint_endpoints(
            self.mock_table, "Article", "articles", "Article", "#/components/schemas/Article"
        )

        # Should generate endpoint for composite constraint
        self.assertIn("/articles/by_title_and_author_id", result)

        # Check endpoint structure
        endpoint = result["/articles/by_title_and_author_id"]
        self.assertIn("parameters", endpoint)
        self.assertIn("get", endpoint)

        # Should have parameters for both fields
        param_names = [p["name"] for p in endpoint["parameters"]]
        self.assertIn("title", param_names)
        self.assertIn("author_id", param_names)

    def test_index_endpoints_single_field(self):
        """Test generation of single-field index endpoints."""
        self.mock_table.meta_indexes = [
            {"fields": ["title"]}  # Single field index
        ]

        with patch('drf_auto_generator.openapi_gen.p') as mock_p:
            mock_p.plural.return_value = "Articles"
            result = _generate_index_endpoints(
                self.mock_table, "Article", "articles", "Article", "#/components/schemas/Article"
            )

        # Should generate filter endpoint for non-unique indexed field
        self.assertIn("/articles/filter_by_title/{value}", result)

        # Check that it returns an array (list endpoint)
        endpoint = result["/articles/filter_by_title/{value}"]
        response_schema = endpoint["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(response_schema["type"], "array")
        self.assertEqual(response_schema["items"]["$ref"], "#/components/schemas/Article")

    def test_index_endpoints_multi_field(self):
        """Test generation of multi-field index endpoints."""
        self.mock_table.meta_indexes = [
            {"fields": ["title", "status"]}  # Multi-field index
        ]

        # Add status field
        self.mock_table.fields.append({
            "name": "status",
            "is_pk": False,
            "is_handled_by_relation": False,
            "openapi_schema": {"type": "string"}
        })

        result = _generate_index_endpoints(
            self.mock_table, "Article", "articles", "Article", "#/components/schemas/Article"
        )

        # Should generate filter endpoint for multi-field index
        self.assertIn("/articles/filter_by_title_and_status", result)

        # Check that parameters are optional for flexibility
        endpoint = result["/articles/filter_by_title_and_status"]
        for param in endpoint["parameters"]:
            self.assertFalse(param["required"])

    @patch('drf_auto_generator.openapi_gen.logger')
    @patch('drf_auto_generator.openapi_gen.p')
    def test_complete_constraint_endpoint_generation(self, mock_p, mock_logger):
        """Test complete constraint endpoint generation workflow."""
        mock_p.plural.return_value = "articles"

        # Set up complex table with various constraint types
        self.mock_table.meta_constraints = [
            {"type": "unique", "fields": ["slug"]},  # Single unique
            {"type": "unique", "fields": ["title", "author_id"]}  # Composite unique
        ]
        self.mock_table.meta_indexes = [
            {"fields": ["status"]},  # Single index
            {"fields": ["category", "published_date"]}  # Multi index
        ]

        # Add additional fields
        for field_name, field_type in [("author_id", "integer"), ("status", "string"),
                                       ("category", "string"), ("published_date", "string")]:
            self.mock_table.fields.append({
                "name": field_name,
                "is_pk": False,
                "is_handled_by_relation": False,
                "openapi_schema": {"type": field_type}
            })

        result = generate_endpoints_on_table_indexes_and_constraints(self.mock_table, self.config)

        # Should generate all types of endpoints
        expected_endpoints = [
            "/articles/by_slug/{value}",  # Unique field
            "/articles/by_title_and_author_id",  # Composite unique
            "/articles/filter_by_status/{value}",  # Single index
            "/articles/filter_by_category_and_published_date"  # Multi index
        ]

        for endpoint in expected_endpoints:
            self.assertIn(endpoint, result)

        # Should log debug information
        mock_logger.debug.assert_called()


class TestM2MEndpointGeneration(unittest.TestCase):
    """Test Many-to-Many endpoint generation."""

    def setUp(self):
        """Set up test fixtures for M2M testing."""
        self.mock_table = Mock()
        self.mock_table.name = "articles"
        self.mock_table.model_name = "Article"
        self.mock_table.fields = [
            {"name": "id", "is_pk": True, "openapi_schema": {"type": "integer"}}
        ]
        self.mock_table.relationships = [
            {
                "name": "tags",
                "type": "many-to-many",
                "target_model_name": "Tag",
                "has_relationship_attributes": False
            }
        ]

        self.config = {"relation_style": "pk"}

    @patch('drf_auto_generator.openapi_gen.p')
    def test_basic_m2m_endpoints_generation(self, mock_p):
        """Test basic M2M endpoint generation."""
        mock_p.plural.return_value = "articles"

        result = generate_m2m_endpoints(self.mock_table, self.config)

        # Should generate list and add/remove endpoints
        expected_endpoints = [
            "/articles/{article_id}/tags",  # List related
            "/articles/{article_id}/tags/{tag_id}"  # Add/remove related
        ]

        for endpoint in expected_endpoints:
            self.assertIn(endpoint, result)

        # Check list endpoint
        list_endpoint = result["/articles/{article_id}/tags"]
        self.assertIn("get", list_endpoint)
        self.assertIn("parameters", list_endpoint)

        # Check add/remove endpoint
        manage_endpoint = result["/articles/{article_id}/tags/{tag_id}"]
        self.assertIn("post", manage_endpoint)    # Add relationship
        self.assertIn("delete", manage_endpoint)  # Remove relationship

    def test_m2m_with_metadata_endpoints(self):
        """Test M2M endpoints with relationship metadata."""
        # Set up M2M with metadata
        self.mock_table.relationships[0].update({
            "has_relationship_attributes": True,
            "metadata_fields": [
                {"name": "created_at", "openapi_schema": {"type": "string", "format": "date-time"}},
                {"name": "created_by", "openapi_schema": {"type": "integer"}}
            ]
        })

        with patch('drf_auto_generator.openapi_gen.p') as mock_p:
            mock_p.plural.return_value = "articles"
            result = generate_m2m_endpoints(self.mock_table, self.config)

        # Should generate metadata endpoint
        self.assertIn("/articles/{article_id}/tags/{tag_id}/metadata", result)

        # Check metadata endpoint operations
        metadata_endpoint = result["/articles/{article_id}/tags/{tag_id}/metadata"]
        self.assertIn("get", metadata_endpoint)    # Get metadata
        self.assertIn("patch", metadata_endpoint)  # Update metadata

        # Check metadata schema includes defined fields
        patch_schema = metadata_endpoint["patch"]["requestBody"]["content"]["application/json"]["schema"]
        self.assertIn("created_at", patch_schema["properties"])
        self.assertIn("created_by", patch_schema["properties"])

    def test_m2m_no_primary_key_skipping(self):
        """Test that M2M generation skips tables without primary keys."""
        # Remove primary key field
        self.mock_table.fields = []

        result = generate_m2m_endpoints(self.mock_table, self.config)

        # Should return empty dict
        self.assertEqual(result, {})


class TestOpenApiSpecGeneration(unittest.TestCase):
    """Test complete OpenAPI specification generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_tables = [
            self._create_mock_table("users", "User"),
            self._create_mock_table("articles", "Article")
        ]

        self.config = {
            "relation_style": "pk",
            "openapi_title": "Test API",
            "openapi_version": "1.0.0",
            "openapi_description": "Test API Description",
            "openapi_server_url": "https://api.example.com"
        }

    def _create_mock_table(self, table_name, model_name):
        """Create a mock table for testing."""
        mock_table = Mock()
        mock_table.name = table_name
        mock_table.model_name = model_name
        mock_table.fields = [
            {"name": "id", "is_pk": True, "openapi_schema": {"type": "integer"}}
        ]
        mock_table.relationships = []
        mock_table.is_m2m_through_table = False
        return mock_table

    @patch('drf_auto_generator.openapi_gen.generate_paths_for_table')
    @patch('drf_auto_generator.openapi_gen.generate_openapi_input_schema')
    @patch('drf_auto_generator.openapi_gen.generate_openapi_schema_object')
    def test_complete_spec_generation(self, mock_schema_obj, mock_input_schema, mock_paths):
        """Test complete OpenAPI spec generation workflow."""
        # Mock the function calls
        mock_schema_obj.return_value = {"type": "object", "properties": {}}
        mock_input_schema.return_value = {"type": "object", "properties": {}}
        mock_paths.return_value = {"/test": {"get": {"summary": "Test"}}}

        result = generate_openapi_spec(self.mock_tables, self.config)

        # Check basic OpenAPI structure
        self.assertEqual(result["openapi"], "3.0.3")
        self.assertIn("info", result)
        self.assertIn("paths", result)
        self.assertIn("components", result)
        self.assertIn("tags", result)

        # Check info section
        self.assertEqual(result["info"]["title"], "Test API")
        self.assertEqual(result["info"]["version"], "1.0.0")
        self.assertEqual(result["info"]["description"], "Test API Description")

        # Check that schemas were generated for all tables
        schemas = result["components"]["schemas"]
        self.assertIn("User", schemas)
        self.assertIn("UserInput", schemas)
        self.assertIn("UserPatchInput", schemas)
        self.assertIn("Article", schemas)
        self.assertIn("ArticleInput", schemas)
        self.assertIn("ArticlePatchInput", schemas)

        # Check that error schema is included
        self.assertIn("ErrorDetail", schemas)

        # Check that paths were generated
        self.assertIn("paths", result)

    def test_empty_table_list_handling(self):
        """Test handling of empty table list."""
        with self.assertLogs('drf_auto_generator.openapi_gen', level='WARNING') as log:
            result = generate_openapi_spec([], self.config)

        # Should return empty dict and log warning
        self.assertEqual(result, {})
        self.assertIn("No tables provided", log.output[0])

    @patch('drf_auto_generator.openapi_gen.generate_openapi_schema_object')
    def test_error_recovery_per_table(self, mock_schema_obj):
        """Test that processing continues when individual tables fail."""
        # Make first table fail, second succeed
        mock_schema_obj.side_effect = [Exception("Schema error"), {"type": "object"}]

        with patch('drf_auto_generator.openapi_gen.generate_openapi_input_schema') as mock_input:
            with patch('drf_auto_generator.openapi_gen.generate_paths_for_table') as mock_paths:
                mock_input.return_value = {"type": "object"}
                mock_paths.return_value = {}

                with self.assertLogs('drf_auto_generator.openapi_gen', level='ERROR') as log:
                    result = generate_openapi_spec(self.mock_tables, self.config)

        # Should continue processing and generate spec for successful table
        self.assertIn("components", result)
        self.assertIn("Article", result["components"]["schemas"])

        # Should log error for failed table
        self.assertIn("Error generating OpenAPI spec for table users", log.output[0])

    def test_authentication_configuration_enabled(self):
        """Test authentication configuration when enabled."""
        auth_config = self.config.copy()
        auth_config.update({
            "enable_authentication": True,
            "auth_scheme": "BearerAuth"
        })

        with patch('drf_auto_generator.openapi_gen.generate_openapi_schema_object'):
            with patch('drf_auto_generator.openapi_gen.generate_openapi_input_schema'):
                with patch('drf_auto_generator.openapi_gen.generate_paths_for_table'):
                    result = generate_openapi_spec(self.mock_tables, auth_config)

        # Should include security schemes
        self.assertIn("securitySchemes", result["components"])
        security_schemes = result["components"]["securitySchemes"]
        self.assertIn("BearerAuth", security_schemes)
        self.assertIn("ApiKeyAuth", security_schemes)
        self.assertIn("BasicAuth", security_schemes)

        # Should include global security requirement
        self.assertIn("security", result)
        self.assertEqual(result["security"], [{"BearerAuth": []}])

    def test_authentication_configuration_disabled(self):
        """Test authentication configuration when disabled."""
        with patch('drf_auto_generator.openapi_gen.generate_openapi_schema_object'):
            with patch('drf_auto_generator.openapi_gen.generate_openapi_input_schema'):
                with patch('drf_auto_generator.openapi_gen.generate_paths_for_table'):
                    result = generate_openapi_spec(self.mock_tables, self.config)

        # Should not include security schemes when disabled
        self.assertEqual(result["components"]["securitySchemes"], {})
        self.assertEqual(result["security"], [])


class TestSaveOpenApiSpec(unittest.TestCase):
    """Test OpenAPI spec file saving functionality."""

    def test_save_spec_to_file(self):
        """Test saving OpenAPI spec to YAML file."""
        spec_dict = {
            "openapi": "3.0.3",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {}
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            save_openapi_spec(spec_dict, temp_dir, "test_api.yaml")

            # Check that file was created
            file_path = os.path.join(temp_dir, "test_api.yaml")
            self.assertTrue(os.path.exists(file_path))

            # Check file contents
            with open(file_path, 'r', encoding='utf-8') as f:
                saved_spec = yaml.safe_load(f)

            self.assertEqual(saved_spec["openapi"], "3.0.3")
            self.assertEqual(saved_spec["info"]["title"], "Test API")

    def test_save_spec_creates_directory(self):
        """Test that save_openapi_spec creates output directory if it doesn't exist."""
        spec_dict = {"openapi": "3.0.3", "info": {"title": "Test"}}

        with tempfile.TemporaryDirectory() as temp_dir:
            nested_dir = os.path.join(temp_dir, "nested", "output")

            save_openapi_spec(spec_dict, nested_dir, "spec.yaml")

            # Check that nested directory was created
            self.assertTrue(os.path.exists(nested_dir))
            self.assertTrue(os.path.exists(os.path.join(nested_dir, "spec.yaml")))

    @patch('drf_auto_generator.openapi_gen.yaml.safe_dump')
    def test_save_spec_handles_yaml_errors(self, mock_yaml_dump):
        """Test error handling when YAML dump fails."""
        mock_yaml_dump.side_effect = Exception("YAML serialization error")

        spec_dict = {"openapi": "3.0.3"}

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertLogs('drf_auto_generator.openapi_gen', level='ERROR') as log:
                save_openapi_spec(spec_dict, temp_dir, "test.yaml")

            # Should log the error
            self.assertIn("Failed to save OpenAPI specification", log.output[0])
            self.assertIn("YAML serialization error", log.output[0])

    @patch('builtins.open')
    def test_save_spec_handles_file_errors(self, mock_open):
        """Test error handling when file operations fail."""
        mock_open.side_effect = PermissionError("Permission denied")

        spec_dict = {"openapi": "3.0.3"}

        with self.assertLogs('drf_auto_generator.openapi_gen', level='ERROR') as log:
            save_openapi_spec(spec_dict, "/tmp", "test.yaml")

        # Should log the error
        self.assertIn("Failed to save OpenAPI specification", log.output[0])


if __name__ == '__main__':
    unittest.main()
