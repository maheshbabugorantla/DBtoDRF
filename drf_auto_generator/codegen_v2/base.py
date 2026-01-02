"""
Base generator plugin architecture for code generation.

This module provides the abstract base class for all code generators and
a registry for managing generator plugins.

Usage:
    class DjangoGenerator(CodeGenerator):
        name = "django"

        def generate(self) -> dict[str, str]:
            return {
                "models.py": self._generate_models(),
                "serializers.py": self._generate_serializers(),
            }

    # Register and use
    registry = GeneratorRegistry()
    registry.register(DjangoGenerator)

    generator = registry.get("django")(schema)
    files = generator.generate()
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .schema import DatabaseSchema

logger = logging.getLogger(__name__)


class CodeGenerator(ABC):
    """
    Abstract base class for all code generators.

    Subclasses should implement the generate() method to produce
    code files from the database schema.
    """

    # Override in subclasses
    name: str = "base"
    description: str = "Base code generator"

    def __init__(self, schema: DatabaseSchema):
        """
        Initialize the generator with a database schema.

        Args:
            schema: The database schema IR to generate code from
        """
        self.schema = schema
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    def generate(self) -> dict[str, str]:
        """
        Generate code files from the schema.

        Returns:
            Dictionary mapping file paths (relative) to file contents
        """
        pass

    def write_files(self, output_dir: str | Path) -> list[Path]:
        """
        Generate and write all files to the output directory.

        Args:
            output_dir: Directory to write files to

        Returns:
            List of paths to written files
        """
        output_path = Path(output_dir)
        files = self.generate()
        written_files = []

        for relative_path, content in files.items():
            file_path = output_path / relative_path

            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(file_path, 'w') as f:
                f.write(content)

            written_files.append(file_path)
            self.logger.info(f"Generated: {file_path}")

        return written_files


class GeneratorRegistry:
    """
    Registry for code generator plugins.

    This allows for dynamic registration and discovery of generators.
    """

    def __init__(self):
        self._generators: dict[str, type[CodeGenerator]] = {}

    def register(self, generator_class: type[CodeGenerator]) -> None:
        """
        Register a generator class.

        Args:
            generator_class: The generator class to register
        """
        name = generator_class.name
        if name in self._generators:
            logger.warning(f"Generator '{name}' already registered, overwriting")
        self._generators[name] = generator_class
        logger.debug(f"Registered generator: {name}")

    def get(self, name: str) -> type[CodeGenerator]:
        """
        Get a generator class by name.

        Args:
            name: The generator name

        Returns:
            The generator class

        Raises:
            KeyError: If generator not found
        """
        if name not in self._generators:
            available = ", ".join(self._generators.keys())
            raise KeyError(f"Generator '{name}' not found. Available: {available}")
        return self._generators[name]

    def create(self, name: str, schema: DatabaseSchema) -> CodeGenerator:
        """
        Create a generator instance.

        Args:
            name: The generator name
            schema: The database schema

        Returns:
            A generator instance
        """
        generator_class = self.get(name)
        return generator_class(schema)

    def list_generators(self) -> list[dict[str, str]]:
        """
        List all registered generators.

        Returns:
            List of dicts with generator info
        """
        return [
            {"name": gen.name, "description": gen.description}
            for gen in self._generators.values()
        ]

    @property
    def available_generators(self) -> list[str]:
        """Get list of available generator names."""
        return list(self._generators.keys())


# Global registry instance
default_registry = GeneratorRegistry()


def register_generator(generator_class: type[CodeGenerator]) -> type[CodeGenerator]:
    """
    Decorator to register a generator class with the default registry.

    Usage:
        @register_generator
        class MyGenerator(CodeGenerator):
            name = "my-generator"
            ...
    """
    default_registry.register(generator_class)
    return generator_class


class FileGenerator(ABC):
    """
    Base class for individual file generators.

    This is a helper for generators that produce multiple files,
    allowing each file's generation logic to be encapsulated.
    """

    def __init__(self, schema: DatabaseSchema):
        self.schema = schema

    @abstractmethod
    def generate(self) -> str:
        """Generate the file content."""
        pass

    @property
    @abstractmethod
    def filename(self) -> str:
        """The output filename."""
        pass


class ProjectGenerator(CodeGenerator):
    """
    Extended base class for generators that produce complete projects.

    Provides additional utilities for project structure generation.
    """

    def __init__(self, schema: DatabaseSchema, config: Optional[dict] = None):
        super().__init__(schema)
        self.config = config or {}

    def get_project_name(self) -> str:
        """Get the project name from schema or config."""
        return self.config.get("project_name", self.schema.project_name)

    def get_app_name(self) -> str:
        """Get the app name from schema or config."""
        return self.config.get("app_name", self.schema.app_name)
