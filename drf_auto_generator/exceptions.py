"""
Custom exception hierarchy for DRF Auto Generator.

This module provides a comprehensive exception system with rich context
and error recovery guidance for contributors and users.
"""

from typing import Dict, Any, Optional, List


class DRFAutoGeneratorError(Exception):
    """
    Base exception for all DRF Auto Generator errors.
    
    Provides rich context and error recovery guidance.
    """
    
    def __init__(
        self, 
        message: str, 
        context: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        error_code: Optional[str] = None
    ):
        """
        Initialize the exception with context and recovery suggestions.
        
        Args:
            message: Human-readable error message
            context: Additional context about where/why the error occurred
            suggestions: List of potential solutions or next steps
            error_code: Unique error code for programmatic handling
        """
        super().__init__(message)
        self.context = context or {}
        self.suggestions = suggestions or []
        self.error_code = error_code
        
    def __str__(self) -> str:
        """Return formatted error message with context."""
        lines = [super().__str__()]
        
        if self.error_code:
            lines.append(f"Error Code: {self.error_code}")
            
        if self.context:
            lines.append("Context:")
            for key, value in self.context.items():
                lines.append(f"  {key}: {value}")
                
        if self.suggestions:
            lines.append("Suggestions:")
            for suggestion in self.suggestions:
                lines.append(f"  • {suggestion}")
                
        return "\n".join(lines)


class ConfigurationError(DRFAutoGeneratorError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, config_file: str = None, **kwargs):
        context = kwargs.get('context', {})
        if config_file:
            context['config_file'] = config_file
            
        suggestions = kwargs.get('suggestions', [])
        if not suggestions:
            suggestions = [
                "Check the configuration file syntax",
                "Verify all required fields are present",
                "Run the configuration validator",
                "Check the documentation for configuration examples"
            ]
            
        super().__init__(
            message, 
            context=context, 
            suggestions=suggestions,
            error_code="CONFIG_ERROR"
        )


class SchemaIntrospectionError(DRFAutoGeneratorError):
    """Raised when database schema introspection fails."""
    
    def __init__(self, message: str, table: str = None, column: str = None, **kwargs):
        context = kwargs.get('context', {})
        if table:
            context['table'] = table
        if column:
            context['column'] = column
            
        suggestions = kwargs.get('suggestions', [])
        if not suggestions:
            suggestions = [
                "Check database connection settings",
                "Verify the table/column exists in the database",
                "Check database user permissions",
                "Review the include/exclude table filters"
            ]
            
        super().__init__(
            message,
            context=context,
            suggestions=suggestions,
            error_code="INTROSPECTION_ERROR"
        )


class FieldMappingError(DRFAutoGeneratorError):
    """Raised when field type mapping fails."""
    
    def __init__(self, message: str, db_type: str = None, django_field: str = None, **kwargs):
        context = kwargs.get('context', {})
        if db_type:
            context['db_type'] = db_type
        if django_field:
            context['django_field'] = django_field
            
        suggestions = kwargs.get('suggestions', [])
        if not suggestions:
            suggestions = [
                "Check if the database type is supported",
                "Add a custom field mapping configuration",
                "Consider using a generic Django field type",
                "Report this as a new field type request"
            ]
            
        super().__init__(
            message,
            context=context,
            suggestions=suggestions,
            error_code="FIELD_MAPPING_ERROR"
        )


class CodeGenerationError(DRFAutoGeneratorError):
    """Raised when AST code generation fails."""
    
    def __init__(self, message: str, component: str = None, table: str = None, **kwargs):
        context = kwargs.get('context', {})
        if component:
            context['component'] = component  # e.g., 'models', 'serializers', 'views'
        if table:
            context['table'] = table
            
        suggestions = kwargs.get('suggestions', [])
        if not suggestions:
            suggestions = [
                "Check the table schema for unsupported patterns",
                "Verify all dependencies are available",
                "Try generating one component at a time",
                "Check for naming conflicts or reserved words"
            ]
            
        super().__init__(
            message,
            context=context,
            suggestions=suggestions,
            error_code="CODE_GENERATION_ERROR"
        )


class RelationshipError(DRFAutoGeneratorError):
    """Raised when relationship analysis or generation fails."""
    
    def __init__(
        self, 
        message: str, 
        source_table: str = None, 
        target_table: str = None,
        relationship_type: str = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        if source_table:
            context['source_table'] = source_table
        if target_table:
            context['target_table'] = target_table
        if relationship_type:
            context['relationship_type'] = relationship_type
            
        suggestions = kwargs.get('suggestions', [])
        if not suggestions:
            suggestions = [
                "Check foreign key constraints in the database",
                "Verify both tables are included in generation",
                "Consider manual relationship configuration",
                "Check for circular dependencies"
            ]
            
        super().__init__(
            message,
            context=context,
            suggestions=suggestions,
            error_code="RELATIONSHIP_ERROR"
        )


class ValidationError(DRFAutoGeneratorError):
    """Raised when validation of generated code or configuration fails."""
    
    def __init__(self, message: str, validator: str = None, **kwargs):
        context = kwargs.get('context', {})
        if validator:
            context['validator'] = validator
            
        suggestions = kwargs.get('suggestions', [])
        if not suggestions:
            suggestions = [
                "Run the built-in validators for more details",
                "Check the generated code syntax",
                "Verify all imports and dependencies",
                "Review the validation rules"
            ]
            
        super().__init__(
            message,
            context=context,
            suggestions=suggestions,
            error_code="VALIDATION_ERROR"
        )


class DatabaseConnectionError(DRFAutoGeneratorError):
    """Raised when database connection fails."""
    
    def __init__(self, message: str, database_url: str = None, engine: str = None, **kwargs):
        context = kwargs.get('context', {})
        if database_url:
            # Mask sensitive parts of the URL
            context['database_url'] = self._mask_credentials(database_url)
        if engine:
            context['engine'] = engine
            
        suggestions = kwargs.get('suggestions', [])
        if not suggestions:
            suggestions = [
                "Check database server is running",
                "Verify connection credentials",
                "Check network connectivity",
                "Ensure database driver is installed"
            ]
            
        super().__init__(
            message,
            context=context,
            suggestions=suggestions,
            error_code="DATABASE_CONNECTION_ERROR"
        )
    
    @staticmethod
    def _mask_credentials(url: str) -> str:
        """Mask sensitive credentials in database URL."""
        # Simple masking - replace password with ***
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', url)


class PluginError(DRFAutoGeneratorError):
    """Raised when plugin loading or execution fails."""
    
    def __init__(self, message: str, plugin_name: str = None, **kwargs):
        context = kwargs.get('context', {})
        if plugin_name:
            context['plugin_name'] = plugin_name
            
        suggestions = kwargs.get('suggestions', [])
        if not suggestions:
            suggestions = [
                "Check plugin is properly installed",
                "Verify plugin compatibility",
                "Check plugin configuration",
                "Try disabling the plugin temporarily"
            ]
            
        super().__init__(
            message,
            context=context,
            suggestions=suggestions,
            error_code="PLUGIN_ERROR"
        )


# Convenience functions for common error patterns
def raise_configuration_error(message: str, config_file: str = None, **kwargs):
    """Convenience function to raise configuration errors."""
    raise ConfigurationError(message, config_file=config_file, **kwargs)


def raise_introspection_error(message: str, table: str = None, column: str = None, **kwargs):
    """Convenience function to raise introspection errors."""
    raise SchemaIntrospectionError(message, table=table, column=column, **kwargs)


def raise_field_mapping_error(message: str, db_type: str = None, **kwargs):
    """Convenience function to raise field mapping errors."""
    raise FieldMappingError(message, db_type=db_type, **kwargs)


def raise_code_generation_error(message: str, component: str = None, table: str = None, **kwargs):
    """Convenience function to raise code generation errors."""
    raise CodeGenerationError(message, component=component, table=table, **kwargs)