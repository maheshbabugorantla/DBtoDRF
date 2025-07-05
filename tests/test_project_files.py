import unittest
from unittest.mock import Mock, patch, MagicMock
import ast
from typing import Dict, Any

from drf_auto_generator.ast_codegen.project_files import (
    _create_name,
    generate_settings_code,
    generate_root_urls_code,
    generate_wsgi_code,
    generate_asgi_code,
    generate_manage_py_code,
    generate_apps_code
)
from drf_auto_generator.config_validation import DatabaseSettings


class TestCreateName(unittest.TestCase):
    """Test cases for _create_name helper function."""

    def test_create_name_with_default_context(self):
        """Test creating name with default Load context."""
        result = _create_name("test_var")

        self.assertIsInstance(result, ast.Name)
        self.assertEqual(result.id, "test_var")
        self.assertIsInstance(result.ctx, ast.Load)
        # Should have location info
        self.assertIsNotNone(result.lineno)
        self.assertIsNotNone(result.col_offset)

    def test_create_name_with_custom_context(self):
        """Test creating name with custom context."""
        custom_ctx = ast.Store()
        result = _create_name("test_var", custom_ctx)

        self.assertIsInstance(result, ast.Name)
        self.assertEqual(result.id, "test_var")
        self.assertIsInstance(result.ctx, ast.Store)
        self.assertIsNotNone(result.lineno)
        self.assertIsNotNone(result.col_offset)

    def test_create_name_with_none_context(self):
        """Test creating name with None context defaults to Load."""
        result = _create_name("test_var", None)

        self.assertIsInstance(result, ast.Name)
        self.assertEqual(result.id, "test_var")
        self.assertIsInstance(result.ctx, ast.Load)

    def test_create_name_with_empty_string(self):
        """Test creating name with empty string."""
        result = _create_name("")

        self.assertIsInstance(result, ast.Name)
        self.assertEqual(result.id, "")
        self.assertIsInstance(result.ctx, ast.Load)


class TestGenerateSettingsCode(unittest.TestCase):
    """Test cases for generate_settings_code function."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_name = "test_project"
        self.app_name = "test_app"

        # Mock database settings
        self.mock_db_settings = Mock(spec=DatabaseSettings)
        self.mock_db_settings.ENGINE = "django.db.backends.postgresql"
        self.mock_db_settings.NAME = "test_db"
        self.mock_db_settings.USER = "test_user"
        self.mock_db_settings.PASSWORD = "test_pass"
        self.mock_db_settings.HOST = "localhost"
        self.mock_db_settings.PORT = "5432"

        self.basic_kwargs = {
            'config': {
                'databases': {
                    'default': self.mock_db_settings
                }
            }
        }

    @patch('drf_auto_generator.ast_codegen.project_files.get_random_secret_key')
    def test_generate_settings_code_basic(self, mock_get_secret_key):
        """Test basic settings generation."""
        mock_get_secret_key.return_value = "test-secret-key"

        result = generate_settings_code(self.project_name, self.app_name, self.basic_kwargs)

        # Verify it's valid Python code
        self.assertIsInstance(result, str)
        self.assertIn("test_project", result)
        self.assertIn("test_app", result)
        self.assertIn("BASE_DIR", result)
        self.assertIn("SECRET_KEY", result)
        self.assertIn("DEBUG", result)
        self.assertIn("ALLOWED_HOSTS", result)
        self.assertIn("INSTALLED_APPS", result)
        self.assertIn("MIDDLEWARE", result)
        self.assertIn("DATABASES", result)
        self.assertIn("REST_FRAMEWORK", result)
        self.assertIn("CORS_ALLOW_ALL_ORIGINS", result)
        self.assertIn("LOGGING", result)

        # Verify secret key was used
        mock_get_secret_key.assert_called_once()

    @patch('drf_auto_generator.ast_codegen.project_files.get_random_secret_key')
    def test_generate_settings_code_with_custom_secret_key(self, mock_get_secret_key):
        """Test settings generation with custom secret key."""
        custom_secret = "custom-secret-key"
        kwargs_with_secret = {
            'secret_key': custom_secret,
            'config': {
                'databases': {
                    'default': self.mock_db_settings
                }
            }
        }

        result = generate_settings_code(self.project_name, self.app_name, kwargs_with_secret)

        # Verify custom secret key is used
        self.assertIn(custom_secret, result)
        # get_random_secret_key should not be called
        mock_get_secret_key.assert_not_called()

    def test_generate_settings_code_with_empty_config(self):
        """Test settings generation with empty config."""
        empty_kwargs = {}

        result = generate_settings_code(self.project_name, self.app_name, empty_kwargs)

        # Should still generate valid settings
        self.assertIsInstance(result, str)
        self.assertIn("DATABASES", result)
        # Should have default database values (empty strings)
        self.assertIn("'ENGINE': ''", result)
        self.assertIn("'NAME': ''", result)
        self.assertIn("'USER': ''", result)
        self.assertIn("'PASSWORD': ''", result)
        self.assertIn("'HOST': ''", result)
        self.assertIn("'PORT': ''", result)

    def test_generate_settings_code_with_missing_database_config(self):
        """Test settings generation with missing database config."""
        kwargs_no_db = {
            'config': {
                'databases': {}
            }
        }

        result = generate_settings_code(self.project_name, self.app_name, kwargs_no_db)

        # Should handle missing default database
        self.assertIsInstance(result, str)
        self.assertIn("DATABASES", result)
        # Should have default database values (empty strings)
        self.assertIn("'ENGINE': ''", result)
        self.assertIn("'NAME': ''", result)
        self.assertIn("'USER': ''", result)
        self.assertIn("'PASSWORD': ''", result)
        self.assertIn("'HOST': ''", result)
        self.assertIn("'PORT': ''", result)

    def test_generate_settings_code_installed_apps_includes_app(self):
        """Test that generated settings includes the specified app."""
        result = generate_settings_code(self.project_name, self.app_name, self.basic_kwargs)

        # Verify the app is included in INSTALLED_APPS
        self.assertIn(f"'{self.app_name}'", result)
        # Also verify standard Django apps are included
        self.assertIn("'django.contrib.admin'", result)
        self.assertIn("'rest_framework'", result)
        self.assertIn("'corsheaders'", result)
        self.assertIn("'drf_spectacular'", result)

    def test_generate_settings_code_middleware_configuration(self):
        """Test middleware configuration in settings."""
        result = generate_settings_code(self.project_name, self.app_name, self.basic_kwargs)

        # Verify middleware includes required components
        self.assertIn("'corsheaders.middleware.CorsMiddleware'", result)
        self.assertIn("'django.middleware.security.SecurityMiddleware'", result)
        self.assertIn("'django.contrib.sessions.middleware.SessionMiddleware'", result)

    def test_generate_settings_code_rest_framework_config(self):
        """Test REST framework configuration in settings."""
        result = generate_settings_code(self.project_name, self.app_name, self.basic_kwargs)

        # Verify REST framework settings
        self.assertIn("'DEFAULT_SCHEMA_CLASS'", result)
        self.assertIn("'drf_spectacular.openapi.AutoSchema'", result)
        self.assertIn("'DEFAULT_AUTHENTICATION_CLASSES'", result)
        self.assertIn("'DEFAULT_PERMISSION_CLASSES'", result)
        self.assertIn("'DEFAULT_PAGINATION_CLASS'", result)
        self.assertIn("'PAGE_SIZE'", result)

    def test_generate_settings_code_database_configuration(self):
        """Test database configuration in settings."""
        result = generate_settings_code(self.project_name, self.app_name, self.basic_kwargs)

        # Verify database settings are included
        self.assertIn("'ENGINE': 'django.db.backends.postgresql'", result)
        self.assertIn("'NAME': 'test_db'", result)
        self.assertIn("'USER': 'test_user'", result)
        self.assertIn("'PASSWORD': 'test_pass'", result)
        self.assertIn("'HOST': 'localhost'", result)
        self.assertIn("'PORT': '5432'", result)

    def test_generate_settings_code_logging_configuration(self):
        """Test logging configuration in settings."""
        result = generate_settings_code(self.project_name, self.app_name, self.basic_kwargs)

        # Verify logging configuration
        self.assertIn("LOGGING", result)
        self.assertIn("'version': 1", result)
        self.assertIn("'disable_existing_loggers': False", result)
        self.assertIn("'formatters'", result)
        self.assertIn("'handlers'", result)
        self.assertIn("'loggers'", result)

    def test_generate_settings_code_can_be_parsed(self):
        """Test that generated settings code can be parsed as valid Python."""
        result = generate_settings_code(self.project_name, self.app_name, self.basic_kwargs)

        # Should be able to parse without errors
        try:
            ast.parse(result)
        except SyntaxError as e:
            self.fail(f"Generated settings code has syntax error: {e}")

    def test_generate_settings_code_with_complex_project_names(self):
        """Test settings generation with complex project names."""
        complex_project = "my_complex_project_123"
        complex_app = "my_complex_app_456"

        result = generate_settings_code(complex_project, complex_app, self.basic_kwargs)

        self.assertIn(complex_project, result)
        self.assertIn(complex_app, result)
        self.assertIn(f"'{complex_app}'", result)  # In INSTALLED_APPS
        self.assertIn(f"'{complex_project}.urls'", result)  # In ROOT_URLCONF
        self.assertIn(f"'{complex_project}.wsgi.application'", result)  # In WSGI_APPLICATION


class TestGenerateRootUrlsCode(unittest.TestCase):
    """Test cases for generate_root_urls_code function."""

    def test_generate_root_urls_code_basic(self):
        """Test basic root URLs generation."""
        project_name = "test_project"
        app_name = "test_app"

        result = generate_root_urls_code(project_name, app_name)

        self.assertIsInstance(result, str)
        self.assertIn("from django.contrib import admin", result)
        self.assertIn("from django.urls import path, include", result)
        self.assertIn("from drf_spectacular.views import", result)
        self.assertIn("from rest_framework.authtoken", result)
        self.assertIn("urlpatterns", result)
        self.assertIn("admin/", result)
        self.assertIn("api/", result)
        self.assertIn(f"{app_name}.urls", result)

    def test_generate_root_urls_code_includes_api_endpoints(self):
        """Test that root URLs include API endpoints."""
        project_name = "test_project"
        app_name = "test_app"

        result = generate_root_urls_code(project_name, app_name)

        # Verify API endpoints are included
        self.assertIn("api/schema/", result)
        self.assertIn("api/schema/swagger-ui/", result)
        self.assertIn("api/schema/redoc/", result)
        self.assertIn("api/auth-token/", result)

        # Verify view references
        self.assertIn("SpectacularAPIView", result)
        self.assertIn("SpectacularSwaggerView", result)
        self.assertIn("SpectacularRedocView", result)
        self.assertIn("authtoken_views.obtain_auth_token", result)

    def test_generate_root_urls_code_can_be_parsed(self):
        """Test that generated root URLs code can be parsed as valid Python."""
        result = generate_root_urls_code("test_project", "test_app")

        try:
            ast.parse(result)
        except SyntaxError as e:
            self.fail(f"Generated root URLs code has syntax error: {e}")

    def test_generate_root_urls_code_with_different_app_names(self):
        """Test root URLs generation with different app names."""
        test_cases = [
            ("proj1", "app1"),
            ("my_project", "my_app"),
            ("project_test", "app_test"),
            ("p", "a"),  # Short names
        ]

        for project_name, app_name in test_cases:
            with self.subTest(project=project_name, app=app_name):
                result = generate_root_urls_code(project_name, app_name)

                self.assertIsInstance(result, str)
                self.assertIn(f"{app_name}.urls", result)
                # Should be parseable
                try:
                    ast.parse(result)
                except SyntaxError as e:
                    self.fail(f"Generated code has syntax error: {e}")

    def test_generate_root_urls_code_url_names(self):
        """Test that generated URLs have proper names."""
        result = generate_root_urls_code("test_project", "test_app")

        # Verify URL names are included
        self.assertIn("name='schema'", result)
        self.assertIn("name='swagger-ui'", result)
        self.assertIn("name='redoc'", result)
        self.assertIn("name='api_token_auth'", result)


class TestGenerateWsgiCode(unittest.TestCase):
    """Test cases for generate_wsgi_code function."""

    def test_generate_wsgi_code_basic(self):
        """Test basic WSGI code generation."""
        project_name = "test_project"

        result = generate_wsgi_code(project_name)

        self.assertIsInstance(result, str)
        self.assertIn("import os", result)
        self.assertIn("from django.core.wsgi import get_wsgi_application", result)
        self.assertIn("os.environ.setdefault", result)
        self.assertIn("DJANGO_SETTINGS_MODULE", result)
        self.assertIn(f"{project_name}.settings", result)
        self.assertIn("application = get_wsgi_application()", result)

    def test_generate_wsgi_code_includes_docstring(self):
        """Test that WSGI code includes proper docstring."""
        project_name = "test_project"

        result = generate_wsgi_code(project_name)

        self.assertIn("WSGI config for", result)
        self.assertIn(project_name, result)
        self.assertIn("It exposes the WSGI callable", result)
        self.assertIn("https://docs.djangoproject.com", result)

    def test_generate_wsgi_code_can_be_parsed(self):
        """Test that generated WSGI code can be parsed as valid Python."""
        result = generate_wsgi_code("test_project")

        try:
            ast.parse(result)
        except SyntaxError as e:
            self.fail(f"Generated WSGI code has syntax error: {e}")

    def test_generate_wsgi_code_with_different_project_names(self):
        """Test WSGI code generation with different project names."""
        test_names = ["proj1", "my_project", "project_test", "p"]

        for project_name in test_names:
            with self.subTest(project=project_name):
                result = generate_wsgi_code(project_name)

                self.assertIsInstance(result, str)
                self.assertIn(f"{project_name}.settings", result)
                # Should be parseable
                try:
                    ast.parse(result)
                except SyntaxError as e:
                    self.fail(f"Generated code has syntax error: {e}")


class TestGenerateAsgiCode(unittest.TestCase):
    """Test cases for generate_asgi_code function."""

    def test_generate_asgi_code_basic(self):
        """Test basic ASGI code generation."""
        project_name = "test_project"

        result = generate_asgi_code(project_name)

        self.assertIsInstance(result, str)
        self.assertIn("import os", result)
        self.assertIn("from django.core.asgi import get_asgi_application", result)
        self.assertIn("os.environ.setdefault", result)
        self.assertIn("DJANGO_SETTINGS_MODULE", result)
        self.assertIn(f"{project_name}.settings", result)
        self.assertIn("application = get_asgi_application()", result)

    def test_generate_asgi_code_includes_docstring(self):
        """Test that ASGI code includes proper docstring."""
        project_name = "test_project"

        result = generate_asgi_code(project_name)

        self.assertIn("ASGI config for", result)
        self.assertIn(project_name, result)
        self.assertIn("It exposes the ASGI callable", result)
        self.assertIn("https://docs.djangoproject.com", result)

    def test_generate_asgi_code_can_be_parsed(self):
        """Test that generated ASGI code can be parsed as valid Python."""
        result = generate_asgi_code("test_project")

        try:
            ast.parse(result)
        except SyntaxError as e:
            self.fail(f"Generated ASGI code has syntax error: {e}")

    def test_generate_asgi_code_with_different_project_names(self):
        """Test ASGI code generation with different project names."""
        test_names = ["proj1", "my_project", "project_test", "p"]

        for project_name in test_names:
            with self.subTest(project=project_name):
                result = generate_asgi_code(project_name)

                self.assertIsInstance(result, str)
                self.assertIn(f"{project_name}.settings", result)
                # Should be parseable
                try:
                    ast.parse(result)
                except SyntaxError as e:
                    self.fail(f"Generated code has syntax error: {e}")


class TestGenerateManagePyCode(unittest.TestCase):
    """Test cases for generate_manage_py_code function."""

    def test_generate_manage_py_code_basic(self):
        """Test basic manage.py code generation."""
        project_name = "test_project"

        result = generate_manage_py_code(project_name)

        self.assertIsInstance(result, str)
        self.assertIn("import os", result)
        self.assertIn("import sys", result)
        self.assertIn("def main():", result)
        self.assertIn("os.environ.setdefault", result)
        self.assertIn("DJANGO_SETTINGS_MODULE", result)
        self.assertIn(f"{project_name}.settings", result)
        self.assertIn("execute_from_command_line", result)
        self.assertIn("if __name__ == '__main__':", result)
        self.assertIn("main()", result)

    def test_generate_manage_py_code_includes_docstrings(self):
        """Test that manage.py code includes proper docstrings."""
        project_name = "test_project"

        result = generate_manage_py_code(project_name)

        self.assertIn("Django's command-line utility", result)
        self.assertIn("Run administrative tasks", result)

    def test_generate_manage_py_code_includes_error_handling(self):
        """Test that manage.py code includes proper error handling."""
        project_name = "test_project"

        result = generate_manage_py_code(project_name)

        self.assertIn("try:", result)
        self.assertIn("except ImportError as exc:", result)
        self.assertIn("raise ImportError", result)
        self.assertIn("Couldn't import Django", result)
        self.assertIn("virtual environment", result)

    def test_generate_manage_py_code_can_be_parsed(self):
        """Test that generated manage.py code can be parsed as valid Python."""
        result = generate_manage_py_code("test_project")

        try:
            ast.parse(result)
        except SyntaxError as e:
            self.fail(f"Generated manage.py code has syntax error: {e}")

    def test_generate_manage_py_code_with_different_project_names(self):
        """Test manage.py code generation with different project names."""
        test_names = ["proj1", "my_project", "project_test", "p"]

        for project_name in test_names:
            with self.subTest(project=project_name):
                result = generate_manage_py_code(project_name)

                self.assertIsInstance(result, str)
                self.assertIn(f"{project_name}.settings", result)
                # Should be parseable
                try:
                    ast.parse(result)
                except SyntaxError as e:
                    self.fail(f"Generated code has syntax error: {e}")

    def test_generate_manage_py_code_main_function_structure(self):
        """Test that main function has correct structure."""
        result = generate_manage_py_code("test_project")

        # Should have main function definition
        self.assertIn("def main():", result)
        # Should have sys.argv usage
        self.assertIn("sys.argv", result)
        # Should have proper if __name__ == '__main__' block
        self.assertIn("if __name__ == '__main__':", result)


class TestGenerateAppsCode(unittest.TestCase):
    """Test cases for generate_apps_code function."""

    def test_generate_apps_code_basic(self):
        """Test basic apps.py code generation."""
        app_name = "test_app"

        result = generate_apps_code(app_name)

        self.assertIsInstance(result, str)
        self.assertIn("from django.apps import AppConfig", result)
        self.assertIn(f"class {app_name.capitalize()}Config(AppConfig):", result)
        self.assertIn("default_auto_field", result)
        self.assertIn("django.db.models.BigAutoField", result)
        self.assertIn(f"name = '{app_name}'", result)

    def test_generate_apps_code_class_naming(self):
        """Test that app config class is named correctly."""
        test_cases = [
            ("test_app", "Test_appConfig"),
            ("my_app", "My_appConfig"),
            ("app", "AppConfig"),
            ("my_test_app", "My_test_appConfig"),
        ]

        for app_name, expected_class in test_cases:
            with self.subTest(app=app_name):
                result = generate_apps_code(app_name)

                self.assertIn(f"class {expected_class}", result)
                self.assertIn(f"name = '{app_name}'", result)

    def test_generate_apps_code_can_be_parsed(self):
        """Test that generated apps.py code can be parsed as valid Python."""
        result = generate_apps_code("test_app")

        try:
            ast.parse(result)
        except SyntaxError as e:
            self.fail(f"Generated apps.py code has syntax error: {e}")

    def test_generate_apps_code_with_different_app_names(self):
        """Test apps.py code generation with different app names."""
        test_names = ["app1", "my_app", "test_app", "a"]

        for app_name in test_names:
            with self.subTest(app=app_name):
                result = generate_apps_code(app_name)

                self.assertIsInstance(result, str)
                self.assertIn(f"name = '{app_name}'", result)
                # Should be parseable
                try:
                    ast.parse(result)
                except SyntaxError as e:
                    self.fail(f"Generated code has syntax error: {e}")

    def test_generate_apps_code_inherits_from_appconfig(self):
        """Test that generated app config inherits from AppConfig."""
        result = generate_apps_code("test_app")

        self.assertIn("(AppConfig)", result)
        self.assertIn("from django.apps import AppConfig", result)

    def test_generate_apps_code_default_auto_field(self):
        """Test that default_auto_field is set correctly."""
        result = generate_apps_code("test_app")

        self.assertIn("default_auto_field = 'django.db.models.BigAutoField'", result)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration test scenarios for complex configurations."""

    def test_all_project_files_generation(self):
        """Test generating all project files together."""
        project_name = "integration_project"
        app_name = "integration_app"

        # Mock database settings
        mock_db_settings = Mock(spec=DatabaseSettings)
        mock_db_settings.ENGINE = "django.db.backends.sqlite3"
        mock_db_settings.NAME = "db.sqlite3"
        mock_db_settings.USER = ""
        mock_db_settings.PASSWORD = ""
        mock_db_settings.HOST = ""
        mock_db_settings.PORT = ""

        kwargs = {
            'secret_key': 'integration-secret-key',
            'config': {
                'databases': {
                    'default': mock_db_settings
                }
            }
        }

        # Generate all files
        settings_code = generate_settings_code(project_name, app_name, kwargs)
        urls_code = generate_root_urls_code(project_name, app_name)
        wsgi_code = generate_wsgi_code(project_name)
        asgi_code = generate_asgi_code(project_name)
        manage_code = generate_manage_py_code(project_name)
        apps_code = generate_apps_code(app_name)

        # Verify all files are valid Python
        files_to_test = [
            ("settings.py", settings_code),
            ("urls.py", urls_code),
            ("wsgi.py", wsgi_code),
            ("asgi.py", asgi_code),
            ("manage.py", manage_code),
            ("apps.py", apps_code),
        ]

        for filename, code in files_to_test:
            with self.subTest(file=filename):
                self.assertIsInstance(code, str)
                self.assertGreater(len(code), 0)
                try:
                    ast.parse(code)
                except SyntaxError as e:
                    self.fail(f"Generated {filename} has syntax error: {e}")

    def test_project_files_consistency(self):
        """Test that generated project files are consistent with each other."""
        project_name = "consistency_project"
        app_name = "consistency_app"

        mock_db_settings = Mock(spec=DatabaseSettings)
        mock_db_settings.ENGINE = "django.db.backends.postgresql"
        mock_db_settings.NAME = "consistency_db"
        mock_db_settings.USER = "user"
        mock_db_settings.PASSWORD = "pass"
        mock_db_settings.HOST = "localhost"
        mock_db_settings.PORT = "5432"

        kwargs = {
            'config': {
                'databases': {
                    'default': mock_db_settings
                }
            }
        }

        settings_code = generate_settings_code(project_name, app_name, kwargs)
        urls_code = generate_root_urls_code(project_name, app_name)
        wsgi_code = generate_wsgi_code(project_name)
        asgi_code = generate_asgi_code(project_name)
        manage_code = generate_manage_py_code(project_name)
        apps_code = generate_apps_code(app_name)

        # Verify project name consistency
        self.assertIn(f"{project_name}.urls", settings_code)
        self.assertIn(f"{project_name}.wsgi.application", settings_code)
        self.assertIn(f"{project_name}.settings", wsgi_code)
        self.assertIn(f"{project_name}.settings", asgi_code)
        self.assertIn(f"{project_name}.settings", manage_code)

        # Verify app name consistency
        self.assertIn(f"'{app_name}'", settings_code)
        self.assertIn(f"{app_name}.urls", urls_code)
        self.assertIn(f"name = '{app_name}'", apps_code)
        self.assertIn(f"{app_name.capitalize()}Config", apps_code)

    def test_edge_case_names(self):
        """Test project file generation with edge case names."""
        edge_cases = [
            ("a", "b"),  # Single character names
            ("project_with_underscores", "app_with_underscores"),
            ("PROJECT123", "APP123"),  # Numbers and uppercase
            ("my-project", "my-app"),  # Hyphens (though not recommended)
        ]

        for project_name, app_name in edge_cases:
            with self.subTest(project=project_name, app=app_name):
                mock_db_settings = Mock(spec=DatabaseSettings)
                mock_db_settings.ENGINE = "django.db.backends.sqlite3"
                mock_db_settings.NAME = "test.db"
                mock_db_settings.USER = ""
                mock_db_settings.PASSWORD = ""
                mock_db_settings.HOST = ""
                mock_db_settings.PORT = ""

                kwargs = {
                    'config': {
                        'databases': {
                            'default': mock_db_settings
                        }
                    }
                }

                # Should not raise exceptions
                settings_code = generate_settings_code(project_name, app_name, kwargs)
                urls_code = generate_root_urls_code(project_name, app_name)
                wsgi_code = generate_wsgi_code(project_name)
                asgi_code = generate_asgi_code(project_name)
                manage_code = generate_manage_py_code(project_name)
                apps_code = generate_apps_code(app_name)

                # All should be valid strings
                for code in [settings_code, urls_code, wsgi_code, asgi_code, manage_code, apps_code]:
                    self.assertIsInstance(code, str)
                    self.assertGreater(len(code), 0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def test_empty_project_name(self):
        """Test handling of empty project name."""
        project_name = ""
        app_name = "test_app"

        mock_db_settings = Mock(spec=DatabaseSettings)
        mock_db_settings.ENGINE = ""
        mock_db_settings.NAME = ""
        mock_db_settings.USER = ""
        mock_db_settings.PASSWORD = ""
        mock_db_settings.HOST = ""
        mock_db_settings.PORT = ""

        kwargs = {
            'config': {
                'databases': {
                    'default': mock_db_settings
                }
            }
        }

        # Should not raise exceptions
        settings_code = generate_settings_code(project_name, app_name, kwargs)
        urls_code = generate_root_urls_code(project_name, app_name)
        wsgi_code = generate_wsgi_code(project_name)
        asgi_code = generate_asgi_code(project_name)
        manage_code = generate_manage_py_code(project_name)

        # All should be valid strings
        for code in [settings_code, urls_code, wsgi_code, asgi_code, manage_code]:
            self.assertIsInstance(code, str)
            self.assertGreater(len(code), 0)

    def test_empty_app_name(self):
        """Test handling of empty app name."""
        project_name = "test_project"
        app_name = ""

        mock_db_settings = Mock(spec=DatabaseSettings)
        mock_db_settings.ENGINE = ""
        mock_db_settings.NAME = ""
        mock_db_settings.USER = ""
        mock_db_settings.PASSWORD = ""
        mock_db_settings.HOST = ""
        mock_db_settings.PORT = ""

        kwargs = {
            'config': {
                'databases': {
                    'default': mock_db_settings
                }
            }
        }

        # Should not raise exceptions
        settings_code = generate_settings_code(project_name, app_name, kwargs)
        urls_code = generate_root_urls_code(project_name, app_name)
        apps_code = generate_apps_code(app_name)

        # All should be valid strings
        for code in [settings_code, urls_code, apps_code]:
            self.assertIsInstance(code, str)
            self.assertGreater(len(code), 0)

    def test_none_database_settings(self):
        """Test handling of None database settings."""
        project_name = "test_project"
        app_name = "test_app"

        kwargs = {
            'config': {
                'databases': {
                    'default': None
                }
            }
        }

        # Should handle None gracefully
        result = generate_settings_code(project_name, app_name, kwargs)
        self.assertIsInstance(result, str)
        self.assertIn("DATABASES", result)
        # Should have default database values (empty strings)
        self.assertIn("'ENGINE': ''", result)
        self.assertIn("'NAME': ''", result)
        self.assertIn("'USER': ''", result)
        self.assertIn("'PASSWORD': ''", result)
        self.assertIn("'HOST': ''", result)
        self.assertIn("'PORT': ''", result)

    @patch('drf_auto_generator.ast_codegen.project_files.get_random_secret_key')
    def test_secret_key_generation_exception(self, mock_get_secret_key):
        """Test handling of secret key generation exception."""
        mock_get_secret_key.side_effect = Exception("Secret key generation failed")

        project_name = "test_project"
        app_name = "test_app"
        kwargs = {}

        # Should raise the exception
        with self.assertRaises(Exception):
            generate_settings_code(project_name, app_name, kwargs)


if __name__ == '__main__':
    unittest.main()
