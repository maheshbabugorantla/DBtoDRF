"""
Main Django generator that combines all file generators.

This is the entry point for generating a complete Django REST Framework project.
"""

import logging
from typing import Any, Optional

from ..base import ProjectGenerator, register_generator
from ..schema import DatabaseSchema
from .models import ModelsGenerator
from .serializers import SerializersGenerator
from .views import ViewsGenerator
from .urls import UrlsGenerator
from .admin import AdminGenerator
from .project import ProjectFilesGenerator

logger = logging.getLogger(__name__)


@register_generator
class DjangoGenerator(ProjectGenerator):
    """
    Generates a complete Django REST Framework project.

    This generator produces:
    - Django models from database schema
    - DRF serializers for all models
    - DRF ViewSets with filtering and search
    - URL routing with DRF router
    - Admin configuration
    - Project settings and configuration files
    """

    name = "django"
    description = "Django REST Framework project generator"

    def __init__(self, schema: DatabaseSchema, config: Optional[dict[str, Any]] = None):
        super().__init__(schema, config)
        self.app_name = self.get_app_name()
        self.project_name = self.get_project_name()

    def generate(self) -> dict[str, str]:
        """
        Generate all Django project files.

        Returns:
            Dictionary mapping file paths to file contents
        """
        files = {}

        logger.info(f"Generating Django project: {self.project_name}")
        logger.info(f"App name: {self.app_name}")
        logger.info(f"Tables to process: {len(self.schema.tables)}")

        # Generate app files
        logger.info("Generating models.py...")
        files[f"{self.app_name}/models.py"] = ModelsGenerator(self.schema).generate()

        logger.info("Generating serializers.py...")
        files[f"{self.app_name}/serializers.py"] = SerializersGenerator(self.schema).generate()

        logger.info("Generating views.py...")
        files[f"{self.app_name}/views.py"] = ViewsGenerator(self.schema).generate()

        logger.info("Generating urls.py...")
        files[f"{self.app_name}/urls.py"] = UrlsGenerator(self.schema).generate()

        logger.info("Generating admin.py...")
        files[f"{self.app_name}/admin.py"] = AdminGenerator(self.schema).generate()

        # Generate project files
        logger.info("Generating project configuration files...")
        project_files = ProjectFilesGenerator(self.schema, self.config).generate_all()
        files.update(project_files)

        logger.info(f"Generated {len(files)} files")

        return files

    def generate_models_only(self) -> str:
        """Generate only the models.py file."""
        return ModelsGenerator(self.schema).generate()

    def generate_serializers_only(self) -> str:
        """Generate only the serializers.py file."""
        return SerializersGenerator(self.schema).generate()

    def generate_views_only(self) -> str:
        """Generate only the views.py file."""
        return ViewsGenerator(self.schema).generate()

    def generate_urls_only(self) -> str:
        """Generate only the urls.py file."""
        return UrlsGenerator(self.schema).generate()

    def generate_admin_only(self) -> str:
        """Generate only the admin.py file."""
        return AdminGenerator(self.schema).generate()
