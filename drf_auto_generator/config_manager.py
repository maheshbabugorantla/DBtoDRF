"""
Configuration management system for DRF Auto Generator.

This module provides centralized configuration handling with validation,
defaults, and type safety. It replaces the scattered configuration logic
throughout the codebase.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod

from .constants import DefaultConfig, SupportedDatabases, PackageVersions
from .exceptions import ConfigurationError


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    
    engine: str
    name: str
    user: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = "localhost"
    port: Optional[int] = None
    options: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate database configuration."""
        if self.engine not in SupportedDatabases.ALL:
            raise ConfigurationError(
                f"Unsupported database engine: {self.engine}",
                context={"supported_engines": SupportedDatabases.ALL}
            )
        
        if not self.name:
            raise ConfigurationError(
                "Database name is required",
                context={"provided_name": self.name}
            )
    
    @property
    def is_sqlite(self) -> bool:
        """Check if this is a SQLite database."""
        return self.engine == SupportedDatabases.SQLITE
    
    @property
    def is_postgresql(self) -> bool:
        """Check if this is a PostgreSQL database."""
        return self.engine == SupportedDatabases.POSTGRESQL
    
    @property
    def is_mysql(self) -> bool:
        """Check if this is a MySQL database."""
        return self.engine == SupportedDatabases.MYSQL
    
    def get_connection_string(self) -> str:
        """Generate database connection string."""
        if self.is_sqlite:
            return f"sqlite:///{self.name}"
        
        # Build connection string for other databases
        conn_parts = [f"{self.engine}://"]
        
        if self.user:
            conn_parts.append(self.user)
            if self.password:
                conn_parts.append(f":{self.password}")
            conn_parts.append("@")
        
        if self.host:
            conn_parts.append(self.host)
            if self.port:
                conn_parts.append(f":{self.port}")
        
        conn_parts.append(f"/{self.name}")
        
        return "".join(conn_parts)


@dataclass
class GenerationConfig:
    """Code generation configuration."""
    
    # Output settings
    output_dir: str = DefaultConfig.OUTPUT_DIR
    project_name: str = DefaultConfig.PROJECT_NAME
    app_name: str = DefaultConfig.APP_NAME
    
    # Generation options
    relation_style: str = DefaultConfig.RELATION_STYLE
    generate_api_tests: bool = DefaultConfig.GENERATE_API_TESTS
    use_timestamps: bool = DefaultConfig.USE_TIMESTAMPS
    auto_add_str_method: bool = DefaultConfig.AUTO_ADD_STR_METHOD
    
    # OpenAPI settings
    openapi_version: str = DefaultConfig.OPENAPI_VERSION
    openapi_title: str = DefaultConfig.OPENAPI_TITLE
    openapi_version_number: str = DefaultConfig.OPENAPI_VERSION_NUMBER
    openapi_description: str = DefaultConfig.OPENAPI_DESCRIPTION
    openapi_server_url: str = DefaultConfig.OPENAPI_SERVER_URL
    
    # Advanced options
    exclude_tables: List[str] = field(default_factory=list)
    include_tables: List[str] = field(default_factory=list)
    table_prefix: str = ""
    custom_field_mappings: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate generation configuration."""
        if self.relation_style not in ["pk", "object", "hyperlink"]:
            raise ConfigurationError(
                f"Invalid relation_style: {self.relation_style}",
                context={"valid_options": ["pk", "object", "hyperlink"]}
            )
        
        # Ensure output directory is absolute
        self.output_dir = str(Path(self.output_dir).resolve())
    
    @property
    def should_exclude_table(self) -> bool:
        """Check if tables should be excluded."""
        return bool(self.exclude_tables)
    
    @property
    def should_include_only_tables(self) -> bool:
        """Check if only specific tables should be included."""
        return bool(self.include_tables)
    
    def is_table_included(self, table_name: str) -> bool:
        """Check if a table should be included in generation."""
        # If include_tables is specified, only include those tables
        if self.should_include_only_tables:
            return table_name in self.include_tables
        
        # If exclude_tables is specified, exclude those tables
        if self.should_exclude_table:
            return table_name not in self.exclude_tables
        
        # Include all tables by default
        return True


@dataclass
class ProjectConfig:
    """Complete project configuration."""
    
    database: DatabaseConfig
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectConfig':
        """Create from dictionary representation."""
        db_config = DatabaseConfig(**data['database'])
        gen_config = GenerationConfig(**data.get('generation', {}))
        
        return cls(
            database=db_config,
            generation=gen_config
        )


class ConfigLoader(ABC):
    """Abstract base class for configuration loaders."""
    
    @abstractmethod
    def load(self, source: Union[str, Path, Dict[str, Any]]) -> ProjectConfig:
        """Load configuration from source."""
        pass
    
    @abstractmethod
    def can_handle(self, source: Union[str, Path, Dict[str, Any]]) -> bool:
        """Check if this loader can handle the source."""
        pass


class YamlConfigLoader(ConfigLoader):
    """YAML configuration file loader."""
    
    def can_handle(self, source: Union[str, Path, Dict[str, Any]]) -> bool:
        """Check if this loader can handle the source."""
        if isinstance(source, dict):
            return False
        
        path = Path(source)
        return path.suffix.lower() in ['.yaml', '.yml']
    
    def load(self, source: Union[str, Path, Dict[str, Any]]) -> ProjectConfig:
        """Load configuration from YAML file."""
        if not self.can_handle(source):
            raise ConfigurationError(
                f"YamlConfigLoader cannot handle source: {source}",
                context={"source_type": type(source).__name__}
            )
        
        config_path = Path(source)
        
        if not config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {config_path}",
                context={"resolved_path": str(config_path.resolve())}
            )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                raise ConfigurationError(
                    "Configuration file must contain a dictionary",
                    context={"loaded_type": type(data).__name__}
                )
            
            return ProjectConfig.from_dict(data)
            
        except yaml.YAMLError as e:
            raise ConfigurationError(
                f"Invalid YAML configuration: {e}",
                context={"file_path": str(config_path)}
            )
        except Exception as e:
            raise ConfigurationError(
                f"Error loading configuration: {e}",
                context={"file_path": str(config_path)}
            )


class DictConfigLoader(ConfigLoader):
    """Dictionary configuration loader."""
    
    def can_handle(self, source: Union[str, Path, Dict[str, Any]]) -> bool:
        """Check if this loader can handle the source."""
        return isinstance(source, dict)
    
    def load(self, source: Union[str, Path, Dict[str, Any]]) -> ProjectConfig:
        """Load configuration from dictionary."""
        if not self.can_handle(source):
            raise ConfigurationError(
                f"DictConfigLoader cannot handle source: {source}",
                context={"source_type": type(source).__name__}
            )
        
        return ProjectConfig.from_dict(source)


class ConfigManager:
    """
    Central configuration manager for DRF Auto Generator.
    
    This class provides a unified interface for loading, validating,
    and managing configuration across the entire application.
    """
    
    def __init__(self):
        """Initialize configuration manager."""
        self.loaders: List[ConfigLoader] = [
            YamlConfigLoader(),
            DictConfigLoader()
        ]
        self._config: Optional[ProjectConfig] = None
    
    def load_config(self, source: Union[str, Path, Dict[str, Any]]) -> ProjectConfig:
        """
        Load configuration from various sources.
        
        Args:
            source: Configuration source (file path, dict, etc.)
            
        Returns:
            Loaded and validated configuration
            
        Raises:
            ConfigurationError: If configuration cannot be loaded or is invalid
        """
        # Find appropriate loader
        loader = None
        for l in self.loaders:
            if l.can_handle(source):
                loader = l
                break
        
        if loader is None:
            raise ConfigurationError(
                f"No loader available for source: {source}",
                context={"source_type": type(source).__name__}
            )
        
        # Load configuration
        config = loader.load(source)
        
        # Validate configuration
        self._validate_config(config)
        
        # Store configuration
        self._config = config
        
        return config
    
    def load_from_file(self, file_path: Union[str, Path]) -> ProjectConfig:
        """
        Load configuration from file.
        
        Args:
            file_path: Path to configuration file
            
        Returns:
            Loaded configuration
        """
        return self.load_config(file_path)
    
    def load_from_dict(self, config_dict: Dict[str, Any]) -> ProjectConfig:
        """
        Load configuration from dictionary.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            Loaded configuration
        """
        return self.load_config(config_dict)
    
    def get_config(self) -> Optional[ProjectConfig]:
        """Get current configuration."""
        return self._config
    
    def has_config(self) -> bool:
        """Check if configuration is loaded."""
        return self._config is not None
    
    def _validate_config(self, config: ProjectConfig) -> None:
        """
        Validate configuration.
        
        Args:
            config: Configuration to validate
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Validate database configuration
        if not config.database.engine:
            raise ConfigurationError(
                "Database engine is required",
                context={"supported_engines": SupportedDatabases.ALL}
            )
        
        # Validate generation configuration
        if not config.generation.output_dir:
            raise ConfigurationError(
                "Output directory is required",
                context={"default_output_dir": DefaultConfig.OUTPUT_DIR}
            )
        
        # Validate project name
        if not config.generation.project_name:
            raise ConfigurationError(
                "Project name is required",
                context={"default_project_name": DefaultConfig.PROJECT_NAME}
            )
        
        # Validate app name
        if not config.generation.app_name:
            raise ConfigurationError(
                "App name is required",
                context={"default_app_name": DefaultConfig.APP_NAME}
            )
    
    def create_default_config(self) -> ProjectConfig:
        """
        Create default configuration.
        
        Returns:
            Default configuration
        """
        # Create database config from environment or defaults
        db_config = DatabaseConfig(
            engine=os.getenv('DB_ENGINE', SupportedDatabases.SQLITE),
            name=os.getenv('DB_NAME', 'db.sqlite3'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')) if os.getenv('DB_PORT') else None
        )
        
        # Create generation config with defaults
        gen_config = GenerationConfig()
        
        config = ProjectConfig(
            database=db_config,
            generation=gen_config
        )
        
        self._config = config
        return config
    
    def save_config(self, file_path: Union[str, Path], config: Optional[ProjectConfig] = None) -> None:
        """
        Save configuration to file.
        
        Args:
            file_path: Path to save configuration
            config: Configuration to save (uses current config if None)
        """
        if config is None:
            config = self.get_config()
        
        if config is None:
            raise ConfigurationError(
                "No configuration to save",
                context={"suggestion": "Load or create configuration first"}
            )
        
        config_path = Path(file_path)
        
        # Create directory if it doesn't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save as YAML
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False, indent=2)
    
    def register_loader(self, loader: ConfigLoader) -> None:
        """
        Register a custom configuration loader.
        
        Args:
            loader: Configuration loader to register
        """
        self.loaders.append(loader)


# Global configuration manager instance
config_manager = ConfigManager()


def get_config() -> Optional[ProjectConfig]:
    """Get the current global configuration."""
    return config_manager.get_config()


def load_config(source: Union[str, Path, Dict[str, Any]]) -> ProjectConfig:
    """Load configuration from source."""
    return config_manager.load_config(source)


def create_default_config() -> ProjectConfig:
    """Create default configuration."""
    return config_manager.create_default_config()