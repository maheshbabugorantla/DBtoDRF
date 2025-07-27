"""
Django AST Code Generator

This module implements a comprehensive AST-based code generation solution
for Django and DRF components based on database schema.
"""

import os
import logging
import stat
from pathlib import Path
from typing import List, Dict, Type, Any
from abc import ABC, abstractmethod
from jinja2 import Environment

from drf_auto_generator.domain.models import TableInfo
from drf_auto_generator.codegen import generate_file_from_template
from drf_auto_generator.codegen_utils import format_python_code_using_black

from drf_auto_generator.ast_codegen.models import generate_models_code
from drf_auto_generator.ast_codegen.serializers import generate_serializers_code
from drf_auto_generator.ast_codegen.views import generate_views_code
from drf_auto_generator.ast_codegen.urls import generate_urls_code
from drf_auto_generator.ast_codegen.admin import generate_admin_code
from drf_auto_generator.ast_codegen.project_files import (
    generate_settings_code,
    generate_root_urls_code,
    generate_wsgi_code,
    generate_asgi_code,
    generate_manage_py_code,
    generate_apps_code
)
from drf_auto_generator.ast_codegen.schemathesis_tests import generate_schemathesis_tests

logger = logging.getLogger(__name__)

# ---- Design Patterns ----

# Strategy Pattern for different code generators
class CodeGeneratorStrategy(ABC):
    """Abstract Strategy for code generation"""

    @abstractmethod
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        """Generate code for a specific component."""
        pass

# Concrete Strategy implementations
class ModelsGenerator(CodeGeneratorStrategy):
    """Generates Django models code"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        return generate_models_code(tables_info)

class SerializersGenerator(CodeGeneratorStrategy):
    """Generates DRF serializers code"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        models_module = kwargs.get('models_module', '.models')
        return generate_serializers_code(tables_info, models_module)


class ViewsGenerator(CodeGeneratorStrategy):
    """Generates DRF views code"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        models_module = kwargs.get('models_module', '.models')
        serializers_module = kwargs.get('serializers_module', '.serializers')
        return generate_views_code(tables_info, models_module, serializers_module)


class UrlsGenerator(CodeGeneratorStrategy):
    """Generates Django app URLs code"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        views_module = kwargs.get('views_module', f'{kwargs.get("app_name")}.views as views')
        return generate_urls_code(tables_info, views_module)


class AdminGenerator(CodeGeneratorStrategy):
    """Generates Django admin code"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        models_module = kwargs.get('models_module', '.models')
        return generate_admin_code(tables_info, models_module)


class SettingsGenerator(CodeGeneratorStrategy):
    """Generates Django settings.py code"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        project_name = kwargs.get('project_name', 'django_project')
        app_name = kwargs.get('app_name', 'api')
        return generate_settings_code(project_name, app_name, kwargs)


class RootUrlsGenerator(CodeGeneratorStrategy):
    """Generates Django root urls.py code"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        project_name = kwargs.get('project_name', 'django_project')
        app_name = kwargs.get('app_name', 'api')
        return generate_root_urls_code(project_name, app_name)


class WSGIGenerator(CodeGeneratorStrategy):
    """Generates Django WSGI app code"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        project_name = kwargs.get('project_name', 'django_project')
        return generate_wsgi_code(project_name)


class ASGIGenerator(CodeGeneratorStrategy):
    """Generates Django ASGI app code"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        project_name = kwargs.get('project_name', 'django_project')
        return generate_asgi_code(project_name)


class ManagePyGenerator(CodeGeneratorStrategy):
    """Generates Django manage.py code"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        project_name = kwargs.get('project_name', 'django_project')
        return generate_manage_py_code(project_name)


class AppsGenerator(CodeGeneratorStrategy):
    """Generates Django apps.py code"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        app_name = kwargs.get('app_name', 'api')
        return generate_apps_code(app_name)


class InitPyGenerator(CodeGeneratorStrategy):
    """Generates empty __init__.py files"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        return ""


class SchemathesisTestsGenerator(CodeGeneratorStrategy):
    """Generates schemathesis integration tests"""
    def generate_code(self, tables_info: List[TableInfo], **kwargs) -> str:
        openapi_spec_path = kwargs.get('openapi_spec_path', 'openapi.yaml')
        base_url = kwargs.get('base_url', 'http://127.0.0.1:8000/api/')
        test_class_name = kwargs.get('test_class_name', 'SchemathesisAPITests')
        include_performance = kwargs.get('include_performance', True)
        include_security = kwargs.get('include_security', True)

        return generate_schemathesis_tests(
            openapi_spec_path=openapi_spec_path,
            output_path=None,  # We'll handle file writing in the main generator
            base_url=base_url,
            test_class_name=test_class_name,
            include_performance=include_performance,
            include_security=include_security
        )


# Factory Pattern for creating generators
class CodeGeneratorFactory:
    """Factory for creating code generator strategies"""

    _registry: Dict[str, Type[CodeGeneratorStrategy]] = {
        'models': ModelsGenerator,
        'serializers': SerializersGenerator,
        'views': ViewsGenerator,
        'urls': UrlsGenerator,
        'admin': AdminGenerator,
        'settings': SettingsGenerator,
        'root_urls': RootUrlsGenerator,
        'wsgi': WSGIGenerator,
        'asgi': ASGIGenerator,
        'manage_py': ManagePyGenerator,
        'apps': AppsGenerator,
        'init_py': InitPyGenerator,
        'schemathesis_tests': SchemathesisTestsGenerator,
    }

    @classmethod
    def register(cls, name: str, generator_class: Type[CodeGeneratorStrategy]) -> None:
        """Register a new generator strategy"""
        cls._registry[name] = generator_class

    @classmethod
    def create(cls, name: str) -> CodeGeneratorStrategy:
        """Create a generator strategy instance by name"""
        generator_class = cls._registry.get(name)
        if not generator_class:
            raise ValueError(f"Unknown generator type: {name}")
        return generator_class()


# Facade Pattern for simplified interface
class CodeGenerator:
    """Facade for the code generation system"""

    def __init__(self, output_dir: str, project_name: str, app_name: str):
        self.output_dir = Path(output_dir)
        self.project_name = project_name
        self.app_name = app_name
        self.project_path = self.output_dir / project_name
        self.app_path = self.output_dir / app_name

    def generate_file(self, generator_name: str, output_path: Path, tables_info: List[TableInfo], **kwargs) -> None:
        """Generate a file using a specific generator strategy"""
        try:
            # Create generator using factory
            generator = CodeGeneratorFactory.create(generator_name)

            # Add common kwargs
            kwargs.update({
                'project_name': self.project_name,
                'app_name': self.app_name
            })

            # Generate code
            code = generator.generate_code(tables_info, **kwargs)

            # Format the generated Python code if needed
            if output_path.suffix == '.py':
                code = format_python_code_using_black(output_path, code)

            # Ensure the parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the generated code to the file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(code)

            logger.info(f"Generated file: {output_path}")

            # Make file executable if it's manage.py
            if output_path.name == 'manage.py':
                self._make_executable(output_path)

        except Exception as e:
            logger.error(f"Error generating file '{output_path}': {e}", exc_info=True)
            raise

    def _make_executable(self, path: Path) -> None:
        """Make a file executable"""
        try:
            current_st = os.stat(path)
            os.chmod(path, current_st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except Exception as e:
            logger.warning(f"Could not make {path} executable: {e}")

    def setup_project_structure(self, tables_info: List[TableInfo], env: Environment, config: Dict[str, Any]) -> None:
        """Create the Django project structure with AST-generated files"""
        # Create necessary directories
        self.project_path.mkdir(parents=True, exist_ok=True)
        self.app_path.mkdir(exist_ok=True)
        (self.app_path / 'migrations').mkdir(exist_ok=True)

        runtime_secret_key = os.urandom(50).hex()
        context = {
            "project_name": self.project_name,
            "app_name": self.app_name,
            "config": config,  # Pass full config for potential use in templates
            "secret_key": runtime_secret_key,  # Use a generated key for settings.py,
        }
        logger.info("Generating sample .env and .gitignore files...")
        generate_file_from_template(env, ".env.j2", context, self.output_dir / ".env")
        generate_file_from_template(env, ".gitignore.j2", context, self.output_dir / ".gitignore")

        # Generate project-level files
        self.generate_file('init_py', self.project_path / '__init__.py', tables_info, config=config)
        self.generate_file('settings', self.project_path / 'settings.py', tables_info, config=config)
        self.generate_file('root_urls', self.project_path / 'urls.py', tables_info, config=config)
        self.generate_file('wsgi', self.project_path / 'wsgi.py', tables_info, config=config)
        self.generate_file('asgi', self.project_path / 'asgi.py', tables_info, config=config)

        # Generate app-level files
        self.generate_file('init_py', self.app_path / '__init__.py', tables_info, config=config)
        self.generate_file('init_py', self.app_path / 'migrations' / '__init__.py', tables_info, config=config)
        self.generate_file('apps', self.app_path / 'apps.py', tables_info, config=config)

        # Generate manage.py
        self.generate_file('manage_py', self.output_dir / 'manage.py', tables_info)

        # Generate API files
        self.generate_file('models', self.app_path / 'models.py', tables_info)
        self.generate_file('serializers', self.app_path / 'serializers.py', tables_info)
        self.generate_file('views', self.app_path / 'views.py', tables_info)
        self.generate_file('urls', self.app_path / 'urls.py', tables_info)
        self.generate_file('admin', self.app_path / 'admin.py', tables_info)

        # Generate test files
        self._generate_test_files(tables_info, config)

    def _generate_test_files(self, tables_info: List[TableInfo], config: Dict[str, Any]) -> None:
        """Generate various test files for the Django project"""
        # Create tests directory
        tests_path = self.app_path / 'tests'
        tests_path.mkdir(exist_ok=True)

        # Generate __init__.py for tests package
        self.generate_file('init_py', tests_path / '__init__.py', tables_info)

        # Generate schemathesis integration tests
        # Use the OpenAPI spec file that will be generated by the main CLI workflow
        openapi_spec_path = str(self.output_dir / 'openapi.yaml')
        base_url = config.get('openapi_server_url', 'http://127.0.0.1:8000/api/')

        # Only generate schemathesis tests if explicitly enabled or not disabled
        generate_schemathesis = config.get('generate_schemathesis_tests', True)

        if generate_schemathesis:
            self.generate_file(
                'schemathesis_tests',
                tests_path / 'test_schemathesis_integration.py',
                tables_info,
                openapi_spec_path=openapi_spec_path,
                base_url=base_url,
                test_class_name='SchemathesisAPITests',
                include_performance=config.get('include_performance_tests', True),
                include_security=config.get('include_security_tests', True)
            )
            logger.info(f"Generated schemathesis integration tests at {tests_path / 'test_schemathesis_integration.py'}")

            # Generate a README for running the tests
            self._generate_test_readme(tests_path, config)

    def _generate_test_readme(self, tests_path: Path, config: Dict[str, Any]) -> None:
        """Generate a README file with instructions for running schemathesis tests"""
        readme_content = f"""# API Integration Tests

This directory contains automatically generated API integration tests using schemathesis.

## Generated Tests

- `test_schemathesis_integration.py`: Standalone property-based tests that validate API endpoints against the OpenAPI specification

## Prerequisites

1. Install test dependencies:
   ```bash
   pip install schemathesis hypothesis requests
   ```

2. Start your API server:
   ```bash
   python manage.py runserver
   # OR any other way you run your API server
   ```

3. Ensure the OpenAPI spec is available at: `openapi.yaml`

## Running Tests

The tests are **completely independent** of Django and can be run in multiple ways:

### Run with unittest (built-in):
```bash
python {tests_path.name}/test_schemathesis_integration.py
```

### Run with pytest:
```bash
python -m pytest {tests_path.name}/test_schemathesis_integration.py -v
```

### Run specific test classes:
```bash
# Main API tests
python -m pytest {tests_path.name}/test_schemathesis_integration.py::SchemathesisAPITests -v

# Performance tests
python -m pytest {tests_path.name}/test_schemathesis_integration.py::SchemathesisPerformanceTests -v

# Security tests
python -m pytest {tests_path.name}/test_schemathesis_integration.py::SchemathesisSecurityTests -v
```

### Run from any directory:
```bash
# No need to be in Django project directory
cd /anywhere
python /path/to/test_schemathesis_integration.py
```

## Test Configuration

The tests are configured to:
- Use base URL: `{config.get('base_url', 'http://localhost:8000')}`
- Load OpenAPI spec from: `openapi.yaml`
- Run up to 50 examples per test
- Include performance and security test placeholders
- **Zero Django dependencies** - pure HTTP testing

## Customization

You can modify the test configuration by editing the constants at the top of `test_schemathesis_integration.py`:

- `API_BASE_URL`: Change the API server URL
- `MAX_EXAMPLES`: Adjust the number of test examples (default: 50)
- `DEADLINE_MS`: Change the test timeout (default: 10000ms)
- `OPENAPI_SPEC_PATH`: Path to your OpenAPI specification file

## Understanding Test Results

Schemathesis will:
1. Generate random test data based on your OpenAPI schema
2. Send HTTP requests to your API endpoints
3. Validate responses against the schema
4. Report any inconsistencies or failures

Failed tests indicate potential issues with:
- API implementation not matching the schema
- Missing validation
- Incorrect response formats
- Network connectivity issues
- Performance issues (if using performance tests)

## Why Standalone Tests?

These tests are designed to be:
- **Framework agnostic**: No Django test harness overhead
- **Portable**: Can run on any machine with Python + dependencies
- **Fast**: Direct HTTP requests without Django test setup
- **CI/CD friendly**: Easy to integrate into any testing pipeline
- **Independent**: Can test any API server, not just Django
"""

        readme_path = tests_path / 'README.md'
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)

        logger.info(f"Generated test README at {readme_path}")


# Helper function to simplify the code generation process
def generate_django_project(
    tables_info: List[TableInfo],
    output_dir: str,
    project_name: str,
    app_name: str,
    env: Environment,
    config: Dict[str, Any],
) -> None:
    """Generate a complete Django project using AST-based code generation"""
    generator = CodeGenerator(output_dir, project_name, app_name)
    generator.setup_project_structure(tables_info, env, config)

    logger.info(f"Successfully generated Django project at {output_dir}")
