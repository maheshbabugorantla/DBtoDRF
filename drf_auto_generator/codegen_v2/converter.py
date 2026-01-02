"""
Converter to bridge from legacy TableInfo to new Pydantic schema.

This module provides conversion utilities to transform the existing
domain models (TableInfo, ColumnInfo, etc.) to the new Pydantic-based
DatabaseSchema IR.
"""

import logging
from typing import Any, Optional

from drf_auto_generator.domain.models import (
    TableInfo as LegacyTableInfo,
    ColumnInfo as LegacyColumnInfo,
    RelationshipInfo as LegacyRelationshipInfo,
    RelationshipType as LegacyRelationshipType,
)

from .schema import (
    DatabaseSchema,
    TableSchema,
    ColumnSchema,
    RelationshipSchema,
    IndexSchema,
    ConstraintSchema,
    FieldType,
    RelationshipType,
)

logger = logging.getLogger(__name__)


# Mapping from legacy Django field types to new FieldType enum
DJANGO_FIELD_TYPE_MAP = {
    "AutoField": FieldType.AUTO,
    "BigAutoField": FieldType.BIG_AUTO,
    "SmallAutoField": FieldType.SMALL_AUTO,
    "IntegerField": FieldType.INTEGER,
    "BigIntegerField": FieldType.BIG_INTEGER,
    "SmallIntegerField": FieldType.SMALL_INTEGER,
    "PositiveIntegerField": FieldType.POSITIVE_INTEGER,
    "PositiveBigIntegerField": FieldType.POSITIVE_BIG_INTEGER,
    "PositiveSmallIntegerField": FieldType.POSITIVE_SMALL_INTEGER,
    "CharField": FieldType.CHAR,
    "TextField": FieldType.TEXT,
    "EmailField": FieldType.EMAIL,
    "URLField": FieldType.URL,
    "SlugField": FieldType.SLUG,
    "FloatField": FieldType.FLOAT,
    "DecimalField": FieldType.DECIMAL,
    "BooleanField": FieldType.BOOLEAN,
    "NullBooleanField": FieldType.NULL_BOOLEAN,
    "DateField": FieldType.DATE,
    "DateTimeField": FieldType.DATETIME,
    "TimeField": FieldType.TIME,
    "DurationField": FieldType.DURATION,
    "BinaryField": FieldType.BINARY,
    "FileField": FieldType.FILE,
    "ImageField": FieldType.IMAGE,
    "UUIDField": FieldType.UUID,
    "JSONField": FieldType.JSON,
    "GenericIPAddressField": FieldType.IP_ADDRESS,
    "ForeignKey": FieldType.FOREIGN_KEY,
    "OneToOneField": FieldType.ONE_TO_ONE,
    "ManyToManyField": FieldType.MANY_TO_MANY,
}


def convert_field_type(django_type: str) -> FieldType:
    """Convert a Django field type string to FieldType enum."""
    return DJANGO_FIELD_TYPE_MAP.get(django_type, FieldType.CHAR)


def convert_relationship_type(legacy_type: str) -> RelationshipType:
    """Convert legacy relationship type to new RelationshipType enum."""
    type_map = {
        "many-to-one": RelationshipType.MANY_TO_ONE,
        "many_to_one": RelationshipType.MANY_TO_ONE,
        "one-to-one": RelationshipType.ONE_TO_ONE,
        "one_to_one": RelationshipType.ONE_TO_ONE,
        "many-to-many": RelationshipType.MANY_TO_MANY,
        "many_to_many": RelationshipType.MANY_TO_MANY,
        "one-to-many": RelationshipType.ONE_TO_MANY,
        "one_to_many": RelationshipType.ONE_TO_MANY,
    }
    return type_map.get(legacy_type, RelationshipType.MANY_TO_ONE)


def convert_column(col: LegacyColumnInfo, field_info: Optional[dict] = None) -> ColumnSchema:
    """
    Convert a legacy ColumnInfo to new ColumnSchema.

    Args:
        col: Legacy ColumnInfo object
        field_info: Optional field dict from TableInfo.fields with Django mapping info
    """
    # Get Django field type from field_info if available
    django_type = "CharField"
    options = {}

    if field_info:
        django_type = field_info.get("type", "CharField")
        options = field_info.get("options", {})

    field_type = convert_field_type(django_type)

    # Handle choices/enum
    choices = None
    if col.enum_values:
        choices = [(v, v) for v in col.enum_values]

    return ColumnSchema(
        name=col.name,
        field_type=field_type,
        nullable=col.nullable,
        primary_key=col.is_pk,
        unique=col.is_unique,
        max_length=options.get("max_length") or col.internal_size,
        max_digits=options.get("max_digits") or col.precision,
        decimal_places=options.get("decimal_places") or col.scale,
        default=options.get("default") or col.default,
        choices=choices,
        db_type=col.db_type_string,
        comment=col.comment,
    )


def convert_relationship(rel_dict: dict[str, Any]) -> RelationshipSchema:
    """Convert a legacy relationship dict to new RelationshipSchema."""
    rel_type = convert_relationship_type(rel_dict.get("type", "many-to-one"))
    options = rel_dict.get("django_field_options", {})

    # Get through table info for M2M
    through_table = rel_dict.get("through")
    through_model = rel_dict.get("through_model") or options.get("through")
    through_fields = rel_dict.get("through_fields") or options.get("through_fields")

    # Source column
    source_columns = rel_dict.get("source_columns", [])
    source_column = source_columns[0] if source_columns else None

    return RelationshipSchema(
        name=rel_dict.get("name", ""),
        type=rel_type,
        target_table=rel_dict.get("target_table", ""),
        target_model=rel_dict.get("target_model_name"),
        source_column=source_column,
        related_name=rel_dict.get("related_name") or options.get("related_name"),
        on_delete=options.get("on_delete", "CASCADE"),
        db_column=options.get("db_column"),
        through_table=through_table,
        through_model=through_model,
        through_fields=tuple(through_fields) if through_fields else None,
        symmetrical=options.get("symmetrical"),
        nullable=options.get("null", True),
    )


def convert_table(table: LegacyTableInfo) -> TableSchema:
    """Convert a legacy TableInfo to new TableSchema."""
    # Build field lookup
    field_lookup = {}
    for field in table.fields:
        orig_name = field.get("original_column_name")
        if orig_name:
            field_lookup[orig_name] = field

    # Convert columns, excluding those handled by relationships
    handled_columns = set()
    for rel in table.relationships:
        source_cols = rel.get("source_columns", [])
        handled_columns.update(source_cols)

    columns = []
    for col in table.columns:
        # Skip columns handled by relationships
        field_info = field_lookup.get(col.name)
        if field_info and field_info.get("is_handled_by_relation"):
            continue

        columns.append(convert_column(col, field_info))

    # Convert relationships
    relationships = [convert_relationship(rel) for rel in table.relationships]

    # Convert indexes
    indexes = []
    for idx in getattr(table, "meta_indexes", []) or []:
        indexes.append(IndexSchema(
            name=idx.get("name"),
            fields=idx.get("fields", []),
            unique=idx.get("unique", False),
        ))

    # Convert constraints
    constraints = []
    for const in getattr(table, "meta_constraints", []) or []:
        constraints.append(ConstraintSchema(
            name=const.get("name", ""),
            type=const.get("type", "unique"),
            fields=const.get("fields", []),
        ))

    return TableSchema(
        name=table.name,
        model_name=table.model_name,
        columns=columns,
        relationships=relationships,
        primary_key_columns=table.primary_key_columns,
        indexes=indexes,
        constraints=constraints,
        comment=table.comment,
        is_m2m_through_table=getattr(table, "is_m2m_through_table", False),
    )


def convert_tables_to_schema(
    tables: list[LegacyTableInfo],
    project_name: str = "django_project",
    app_name: str = "api",
    database_name: Optional[str] = None,
) -> DatabaseSchema:
    """
    Convert a list of legacy TableInfo objects to a new DatabaseSchema.

    Args:
        tables: List of legacy TableInfo objects
        project_name: Django project name
        app_name: Django app name
        database_name: Optional database name

    Returns:
        DatabaseSchema object
    """
    logger.info(f"Converting {len(tables)} tables to new schema format")

    converted_tables = []
    for table in tables:
        try:
            converted = convert_table(table)
            converted_tables.append(converted)
            logger.debug(f"Converted table: {table.name} -> {converted.model_name}")
        except Exception as e:
            logger.error(f"Failed to convert table {table.name}: {e}")
            raise

    return DatabaseSchema(
        tables=converted_tables,
        database_name=database_name,
        project_name=project_name,
        app_name=app_name,
    )
