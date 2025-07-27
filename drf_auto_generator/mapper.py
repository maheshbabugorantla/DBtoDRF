"""
Field mapping and naming utilities for DRF Auto Generator.

This module provides comprehensive field mapping functionality for converting
database schema information into Django model fields, DRF serializer fields,
and OpenAPI schema definitions. It handles naming conventions, field type
mappings, and relationship inference.

Key Components:
- Field type mapping from database types to Django field types
- Naming convention utilities (snake_case, PascalCase, etc.)
- Relationship analysis and mapping
- OpenAPI schema generation for fields
- DRF serializer field mapping

Example:
    >>> from .mapper import FieldMapper
    >>> mapper = FieldMapper()
    >>> django_field = mapper.map_django_field(column_info)
    >>> openapi_schema = mapper.map_openapi_field(column_info)
"""

import logging
from typing import List, Dict, Any, Tuple
import inflect

# Import domain models and services
from drf_auto_generator.domain.models import TableInfo, ColumnInfo
from drf_auto_generator.domain.field_mapping import FieldMapper as DomainFieldMapper
from drf_auto_generator.domain.relationships import RelationshipAnalyzer
from drf_auto_generator.domain.constraints import ConstraintAnalyzer
from drf_auto_generator.constants import (
    DjangoFieldTypes, DJANGO_FIELD_MAP, OPENAPI_TYPE_MAP,
    FieldCategories, RelationshipDefaults
)
from drf_auto_generator.domain.naming import NamingConventions, clean_field_name, to_pascal_case

# Initialize inflect engine for pluralization
p = inflect.engine()


logger = logging.getLogger(__name__)


# --- Legacy naming helpers (moved to domain/naming.py) ---
# These are imported above for backward compatibility


# --- Legacy Type Mapping Functions ---
# These functions are kept for backward compatibility with existing code.
# New code should use domain services instead.


# --- Mapping Functions ---


def map_db_type_to_django(col: ColumnInfo, table_info: TableInfo = None) -> Tuple[str, Dict[str, Any]]:
    """Maps DB type string (from Django introspection) to Django model field type and options."""

    # 1. Get the base Django field type from mapping
    field_type = DJANGO_FIELD_MAP.get(col.db_type_string, DjangoFieldTypes.TEXT_FIELD)

    # 2. Base Options from ColumnInfo attributes
    options: Dict[str, Any] = {}

    # Basic nullability & unique
    if col.nullable:
        options["null"] = True
    if col.is_unique and not col.is_pk:  # PKs are implicitly unique
        options["unique"] = True

    # Size-related options for specific types
    if field_type in (DjangoFieldTypes.CHAR_FIELD, DjangoFieldTypes.TEXT_FIELD) and col.internal_size:
        # Note: If internal_size is -1 or very large, maybe skip max_length
        if col.internal_size > 0:
            options["max_length"] = col.internal_size
    elif field_type == DjangoFieldTypes.DECIMAL_FIELD:
        options["max_digits"] = col.precision or 10  # Default fallback
        options["decimal_places"] = col.scale or 0

    # 3. Refine Field Type and Options based on ColumnInfo
    if col.is_pk:
        # Check if this table has a composite primary key
        is_composite_pk = table_info and len(table_info.primary_key_columns) > 1

        if is_composite_pk:
            # For composite primary keys, individual fields should NOT be AutoField
            # The composite constraint will be handled by unique_together or CompositePrimaryKey
            # Keep the original field type (IntegerField, DateTimeField, etc.)

            # If Django introspection already converted this to AutoField, we need to convert it back
            if field_type in (DjangoFieldTypes.AUTO_FIELD, DjangoFieldTypes.BIG_AUTO_FIELD, DjangoFieldTypes.SMALL_AUTO_FIELD):
                if field_type == DjangoFieldTypes.BIG_AUTO_FIELD:
                    field_type = DjangoFieldTypes.BIG_INTEGER_FIELD
                elif field_type == DjangoFieldTypes.SMALL_AUTO_FIELD:
                    field_type = DjangoFieldTypes.SMALL_INTEGER_FIELD
                else:  # AutoField
                    field_type = DjangoFieldTypes.INTEGER_FIELD
                logger.debug(f"Column {col.name} is part of composite PK, converting {col.db_type_string} from AutoField back to {field_type}")

            options.pop("primary_key", None)  # Don't mark individual fields as primary_key=True
            logger.debug(f"Column {col.name} is part of composite PK, keeping type: {field_type}")
            # Do NOT convert to AutoField for composite primary keys
        else:
            # Single primary key - check if it looks like an auto-incrementing integer PK
            is_standard_int_pk = field_type in FieldCategories.INTEGER_TYPES
            # `inspectdb` has complex logic checking sequences/defaults. We simplify:
            # Assume integer PKs are auto-incrementing unless specified otherwise.
            if is_standard_int_pk:
                if "Big" in field_type:
                    field_type = DjangoFieldTypes.BIG_AUTO_FIELD
                elif "Small" in field_type:
                    field_type = DjangoFieldTypes.SMALL_AUTO_FIELD
                else:
                    field_type = DjangoFieldTypes.AUTO_FIELD
                options.pop(
                    "primary_key", None
                )  # AutoFields have implicit primary_key=True
            else:  # Non-integer PK (e.g., UUID, CharField)
                options["primary_key"] = True
                # Ensure default is not set for non-auto PKs if introspection didn't provide one
                options.pop("default", None)
    else:  # Not a PK
        options.pop("primary_key", None)

    # Handle Nullability & Blank
    options["null"] = col.nullable
    # Django convention: Char/Text fields usually use blank=True instead of null=True
    if col.nullable and field_type in FieldCategories.TEXT_TYPES:
        options["blank"] = True
        # Keep null=True if the DB explicitly allows NULL, for consistency? Or remove it?
        # Django practice leans towards blank=True, null=False for string fields. Let's try that.
        # options['null'] = False # Overwrite null for these types if nullable? Risky.
    elif not col.nullable and field_type not in (
        DjangoFieldTypes.BOOLEAN_FIELD,
    ):  # Set blank=False if not nullable (bool handles null differently)
        options["blank"] = False

    # Handle defaults (introspection often doesn't retrieve them properly)
    if col.default is not None:  # Only set if explicitly provided
        # Maybe parse string defaults like 'uuid4()' into UUID field defaults
        if field_type == DjangoFieldTypes.UUID_FIELD and str(col.default).lower() in [
            "uuid4()",
            "gen_random_uuid()",
        ]:
            options["default"] = "uuid.uuid4"  # String to be parsed later
        else:
            options["default"] = col.default

    # Handle Foreign Key info (if available) - useful for correct field type
    if col.is_foreign_key and col.foreign_key_to:
        target_table, target_column = col.foreign_key_to
        options["related_to"] = (target_table, target_column)

    # Add collation if available (requires Django 4.1+)
    # Add collation if available (requires Django 4.1+)
    # if col.collation and hasattr(models, 'collation'): # Check Django version capability
    #      options['db_collation'] = col.collation

    # Ensure AutoFields don't have conflicting options like 'default'
    if "Auto" in field_type:
        options.pop("default", None)
        options.pop("null", None)
        options.pop("blank", None)
        options.pop("unique", None)  # PK implies unique

    return field_type, options


def map_db_type_to_openapi(col: ColumnInfo) -> Dict[str, Any]:
    """Maps DB type string (or derived Django field type) to OpenAPI schema properties."""

    # Instead of calling map_db_type_to_django with table_info=None (which is fragile),
    # we'll determine the Django field type locally with simpler logic for OpenAPI purposes
    field_type = DJANGO_FIELD_MAP.get(col.db_type_string, DjangoFieldTypes.TEXT_FIELD)

    # For OpenAPI purposes, we treat all primary key integer fields as AutoField
    # since we don't have table context to determine if it's composite
    if col.is_pk and field_type in FieldCategories.INTEGER_TYPES:
        if "Big" in field_type:
            field_type = DjangoFieldTypes.BIG_AUTO_FIELD
        elif "Small" in field_type:
            field_type = DjangoFieldTypes.SMALL_AUTO_FIELD
        else:
            field_type = DjangoFieldTypes.AUTO_FIELD

    # Get the base schema from the OpenAPI map
    schema = OPENAPI_TYPE_MAP.get(field_type, OPENAPI_TYPE_MAP["Unknown"]).copy()

    # Apply constraints/details from ColumnInfo to the schema
    schema["nullable"] = col.nullable

    # Add maxLength if applicable and available
    if field_type in (DjangoFieldTypes.CHAR_FIELD, DjangoFieldTypes.TEXT_FIELD) and col.internal_size and col.internal_size > 0:
        schema["maxLength"] = col.internal_size

    # Ensure readOnly is set for PKs if not already handled by type map
    if col.is_pk and not schema.get("readOnly"):
        schema["readOnly"] = True
        if "description" not in schema:
            schema["description"] = "Primary Key"

    # Add description for clarity if missing
    if "description" not in schema and schema["type"] != "Unknown":
        schema["description"] = f"{field_type} field"

    return schema


def analyze_relationships_django(
    tables: List[TableInfo], table_map: Dict[str, TableInfo]
):
    """
    Analyzes foreign keys from Django's introspection results. Updates TableInfo in-place.
    Identifies ManyToOne relationships. M2M requires join table detection logic.
    """
    logger.info("Analyzing relationships (using Django introspection data)...")
    all_table_names = set(table_map.keys())

    # --- Pass 1: Identify ManyToOne relationships based on FKs ---
    for table in tables:
        relationships = []  # Store relationship definitions as dicts

        # Process FKs from relations or constraints
        fk_source = table.relations if table.relations else table.constraints
        potential_fks: Dict[str, Tuple[str, str]] = (
            {}
        )  # {fk_col_name: (target_table, target_col)}

        # Extract FK info into a consistent format {col_name: (target_table, target_col)}
        for name, data in fk_source.items():
            target_table, target_col = None, None
            fk_cols = []
            if "foreign_key" in data and isinstance(
                data.get("foreign_key"), tuple
            ):  # Constraint format
                if data.get("columns") and isinstance(data["columns"], list):
                    fk_cols = data["columns"]
                    target_table, target_col = data[
                        "foreign_key"
                    ]  # Assumes single target col from tuple
            elif (
                isinstance(data, tuple) and len(data) == 2
            ):  # Relation format (key is fk_col)
                fk_cols = [name]
                target_col, target_table = (
                    data  # Note order difference from constraint format
                )

            # Only process single-column FKs for now
            if len(fk_cols) == 1 and target_table and target_col:
                potential_fks[fk_cols[0]] = (target_table, target_col)

        logger.debug(f"Potential FKs identified for {table.name}: {potential_fks}")

        # Create relationship definitions
        for fk_col_name, (target_table_name, target_col_name) in potential_fks.items():
            if target_table_name not in all_table_names:
                logger.warning(
                    f"Skipping FK from {table.name}.{fk_col_name}: Target table '{target_table_name}' not found or excluded."
                )
                continue

            target_table = table_map[target_table_name]
            target_model_name = target_table.model_name  # Get mapped name

            # Generate relationship field name using naming conventions
            rel_name_guess = NamingConventions.foreign_key_to_relationship(fk_col_name)

            # Get the cleaned FK field name for comparison
            fk_field_name = clean_field_name(fk_col_name)

            # Django FK naming strategy:
            # For a column 'address_id', create relationship field 'address' and exclude the raw 'address_id' field
            # Django will automatically map 'address' ForeignKey to 'address_id' database column
            # This avoids all naming conflicts.

            # Only add suffix if there would be a conflict with other field names or the target model name
            needs_suffix = False
            original_rel_name = rel_name_guess

            # Case 1: Avoid clash with target model name (lowercase)
            if rel_name_guess == target_model_name.lower():
                needs_suffix = True
                logger.debug(f"Target model name clash detected: relationship '{rel_name_guess}' == model '{target_model_name.lower()}'")

            # Case 2: Check for conflicts with existing non-FK field names
            # Only consider fields that are NOT FK fields (since we'll be excluding all FK fields anyway)
            existing_non_fk_field_names = set()
            for field_data in table.fields:
                if not field_data.get("is_fk", False):
                    existing_non_fk_field_names.add(field_data["name"])

            if rel_name_guess in existing_non_fk_field_names:
                needs_suffix = True
                logger.debug(f"Non-FK field clash detected: relationship '{rel_name_guess}' conflicts with existing field")

            # Case 3: Check for conflicts with relationship names we've already created
            existing_rel_names = {r["name"] for r in relationships}
            if rel_name_guess in existing_rel_names:
                needs_suffix = True
                logger.debug(f"Relationship name clash detected: '{rel_name_guess}' already exists")

            if needs_suffix:
                rel_name_guess += "_rel"

            # Additional safety check: if relationship name would still conflict, make it more unique
            counter = 1
            original_rel_name = rel_name_guess
            while (rel_name_guess in existing_non_fk_field_names or
                   rel_name_guess in existing_rel_names or
                   rel_name_guess == target_model_name.lower()):
                rel_name_guess = f"{original_rel_name}_{counter}"
                counter += 1
                if counter > 10:  # Prevent infinite loop
                    logger.error(f"Could not generate unique relationship name for {fk_col_name} after 10 attempts")
                    break

            logger.debug(f"Generated relationship name '{rel_name_guess}' for FK column '{fk_col_name}'")

            # Get null/blank status from the original FK column
            fk_col_obj = next((c for c in table.columns if c.name == fk_col_name), None)
            fk_nullable = (
                fk_col_obj.nullable if fk_col_obj else True
            )  # Default to True if column not found
            fk_blankable = fk_nullable  # Simple assumption: blank = null for FKs

            # TODO: Determine on_delete (requires specific constraint info or config)
            on_delete_action = RelationshipDefaults.DEFAULT_ON_DELETE

            # Generate unique related_name to avoid clashes
            # Count how many FKs from current table already point to target_table
            existing_rels_to_target = [r for r in relationships if r.get("target_table") == target_table_name]

            if len(existing_rels_to_target) == 0:
                # First FK to this target - use simple plural name
                related_name = NamingConventions.generate_reverse_name(table.name)
            else:
                # Multiple FKs to same target - make related_name unique
                # Use the field name to differentiate
                related_name = NamingConventions.generate_reverse_name(table.name, rel_name_guess)

            # Ensure related_name is unique across all existing relationships
            # Need to check all relationships from all tables, not just current table
            all_existing_related_names = set()
            for tbl in tables:
                for rel in tbl.relationships:
                    if rel.get("related_name"):
                        all_existing_related_names.add(rel.get("related_name"))

            # Also check current relationships being built
            for rel in relationships:
                if rel.get("related_name"):
                    all_existing_related_names.add(rel.get("related_name"))

            counter = 1
            original_related_name = related_name
            while related_name in all_existing_related_names:
                related_name = f"{original_related_name}_{counter}"
                counter += 1
                if counter > 10:  # Prevent infinite loop
                    logger.error(f"Could not generate unique related_name for {rel_name_guess} after 10 attempts")
                    break

            # ManyToOne relationship from current table to target table
            django_field_options = {
                "on_delete": on_delete_action,
                "null": fk_nullable,
                "blank": fk_blankable,
                # Add verbose_name, help_text later?
            }

            # Only set db_column if the relationship name doesn't follow Django's automatic convention
            # Django automatically maps 'address' -> 'address_id', so we don't need to specify db_column
            expected_db_column = f"{rel_name_guess}_id"
            if fk_col_name != expected_db_column:
                # The FK column doesn't follow Django's naming convention, so we need to specify it
                django_field_options["db_column"] = fk_col_name
                logger.debug(f"Setting db_column='{fk_col_name}' for relationship '{rel_name_guess}' (doesn't follow Django convention)")
            else:
                logger.debug(f"Using Django's automatic column mapping for relationship '{rel_name_guess}' -> column '{fk_col_name}'")

            mto_rel = {
                "name": rel_name_guess,
                "type": "many-to-one",
                "target_table": target_table_name,
                "target_model_name": target_model_name,
                # Generate a usable related_name for the reverse relation (e.g., 'book_set')
                # Use singular of target + _set or plural of current table name
                "related_name": related_name,
                "source_columns": [fk_col_name],
                "target_columns": [
                    target_col_name
                ],  # Assumed from introspection format
                "django_field_options": django_field_options,
            }
            relationships.append(mto_rel)

            # Mark the original FK column's corresponding Django field as 'handled'
            # so it's not rendered directly in models.py if the FK relation field exists
            fk_field_marked = False
            for field_data in table.fields:
                if field_data["original_column_name"] == fk_col_name:
                    field_data["is_handled_by_relation"] = True
                    fk_field_marked = True
                    logger.debug(
                        f"Marking field {table.name}.{field_data['name']} (column: {fk_col_name}) as handled by relation {rel_name_guess}"
                    )
                    break

            if not fk_field_marked:
                logger.warning(
                    f"Could not find field corresponding to FK column {fk_col_name} in table {table.name} to mark as handled"
                )

        # --- TODO: Pass 2: Detect ManyToMany relationships ---
        # Heuristic: Identify join tables (tables with exactly two FKs forming the PK)
        # This requires iterating through tables again and adding M2M RelationshipInfo
        # to the *two endpoint tables*, referencing the join table via `through`.

        table.relationships = relationships

    potential_join_tables = []
    for table in tables:
        # Skip table without exactly 2 FKs
        fk_fields = [f for f in table.fields if f["is_fk"]]
        if len(fk_fields) != 2:
            continue

        # Get PK fields details
        pk_fields = [f for f in table.fields if f["is_pk"]]
        if len(pk_fields) != 2:
            continue

        # Check if PK consists of both FK columns (composite key)
        # or check if table has exactly 2 FKs and nothing else substantial
        has_pk_consisting_of_fks = False
        if len(pk_fields) >= 2:
            # Check if all PKs are FKs
            pk_field_names = [f["original_column_name"] for f in pk_fields]
            fk_field_names = [f["original_column_name"] for f in fk_fields]
            has_pk_consisting_of_fks = all(name in fk_field_names for name in pk_field_names)

        # Alternative check: if the table only has 2 FKs and no other substantial fields
        # (allow for timestamps, IDs, etc.), it might be a join table
        substantial_fields = [
            f for f in table.fields
            if not f["is_pk"] and not f["is_fk"] and
            f["name"].lower() not in (
                "created_at", "updated_at", "created", "modified",
                "creation_date", "modification_date", "timestamp"
            )
        ]

        has_only_fks_and_minimal_fields = len(substantial_fields) <= 1
        logger.debug(
            f"Table {table.name} has has_pk_consisting_of_fks={has_pk_consisting_of_fks}, "
            f"substantial_fields={len(substantial_fields)}"
        )

        if has_pk_consisting_of_fks or has_only_fks_and_minimal_fields:
            # Get FK target information
            fk_targets = []
            fk_columns = []

            for fk_field in fk_fields:
                original_column_name = fk_field["original_column_name"]
                column_obj = next((c for c in table.columns if c.name == original_column_name), None)

                if column_obj and column_obj.foreign_key_to:
                    target_table_name, target_column_name = column_obj.foreign_key_to
                    if target_table_name in table_map:
                        fk_targets.append((target_table_name, target_column_name))
                        fk_columns.append(original_column_name)

            # Verify we have two distinct targets
            if len(fk_targets) == 2:
                # Extract additional metadata fields - any non-PK, non-FK fields that might
                # represent relationship attributes
                metadata_fields = []
                for field in table.fields:
                    if (not field["is_pk"] and not field["is_fk"] and
                        field["name"].lower() not in (
                            "created_at", "updated_at", "created", "modified",
                            "creation_date", "modification_date", "timestamp"
                        )
                    ):
                        metadata_fields.append(field)

                potential_join_tables.append({
                    "join_table": table,
                    "fk1_column": fk_columns[0],
                    "target1": fk_targets[0][0],
                    "target1_col": fk_targets[0][1],
                    "fk2_column": fk_columns[1],
                    "target2": fk_targets[1][0],
                    "target2_col": fk_targets[1][1],
                    "metadata_fields": metadata_fields
                })
                logger.debug(
                    f"Potential M2M join table found: {table.name} linking "
                    f"{fk_targets[0][0]} and {fk_targets[1][0]}"
                )

    # Now create M2M relationshipS based on the identified join tables
    for join_table in potential_join_tables:
        _join_table: TableInfo = join_table["join_table"]

        # Mark the join table
        _join_table.is_m2m_through_table = True
        logger.info(f"Marked table {_join_table.name} as M2M through table")

        target1_name = join_table["target1"]
        target2_name = join_table["target2"]
        fk1_column = join_table["fk1_column"]
        fk2_column = join_table["fk2_column"]
        metadata_fields = join_table["metadata_fields"]

        # Get the model objects
        target1 = table_map.get(target1_name)
        target2 = table_map.get(target2_name)

        if not target1 or not target2:
            logger.warning(
                f"Skipping M2M relationship for {_join_table.name}: Target tables not found"
            )
            continue

        # Handle self-referential M2M (both FKs point to the same table)
        is_self_referential = target1_name == target2_name

        if is_self_referential:
            logger.info(f"Found self-referential M2M relationship for {_join_table.name} for {target1_name}")

            # For self-referential M2M, we only create one relationship
            # The field name needs to be descriptive of the relationship
            # Try to use the join table name or something based on it
            rel_name = clean_field_name(_join_table.name)
            # Make it plural since it's a to-many relationship
            rel_name = p.plural(rel_name)

            # Generate better names based on column names if possible
            # e.g., "followers" and "following" for a user-follows-user relationship
            # This is a heuristic and might need adjustment for specific schemas
            if any(s in fk1_column.lower() for s in ["from", "source", "follower"]):
                rel_name = "followers"
            elif any(s in fk1_column.lower() for s in ["to", "target", "following"]):
                rel_name = "following"

            # Avoid name clashes
            # Check if the name already exists in relationships
            existing_rel_names = {r["name"] for r in target1.relationships}
            if rel_name in existing_rel_names:
                rel_name = f"{rel_name}_self"

                # If still clashing, add a suffix
                if rel_name in existing_rel_names:
                    rel_name = f"{rel_name}_{_join_table.name}"

            # Find the actual FK field names in the through model for through_fields
            fk1_field_name = None
            fk2_field_name = None
            for rel in _join_table.relationships:
                if rel["type"] == "many-to-one" and fk1_column in rel.get("source_columns", []):
                    fk1_field_name = rel["name"]
                elif rel["type"] == "many-to-one" and fk2_column in rel.get("source_columns", []):
                    fk2_field_name = rel["name"]

            # Create the self-referential M2M relationship
            m2m_rel = {
                "name": rel_name,
                "type": "many-to-many",
                "target_table": target1.name,
                "target_model_name": target1.model_name,
                "through": _join_table.name,
                "through_model": _join_table.model_name,
                "source_field": fk1_column,
                "target_field": fk2_column,
                "symmetrical": False,  # Most self-referential relationships aren't symmetrical
                "is_self_referential": True,
                "related_name": f"{rel_name}_of",  # Or another appropriate name
                "django_field_options": {
                    "through": _join_table.model_name,
                    "through_fields": (fk1_field_name or fk1_column, fk2_field_name or fk2_column),
                    "blank": True,
                    "symmetrical": False,
                }
            }

            # Add metadata fields if any
            if metadata_fields:
                m2m_rel["metadata_fields"] = metadata_fields
                m2m_rel["has_relationship_attributes"] = True

            # Add the relationship to the model
            target1.relationships.append(m2m_rel)
            logger.info(f"Created self-referential M2M relationship '{rel_name}' for {target1.name}")
        else:
            # Find the actual FK field names in the through model for through_fields
            fk1_field_name = None
            fk2_field_name = None
            for rel in _join_table.relationships:
                if rel["type"] == "many-to-one" and fk1_column in rel.get("source_columns", []):
                    fk1_field_name = rel["name"]
                elif rel["type"] == "many-to-one" and fk2_column in rel.get("source_columns", []):
                    fk2_field_name = rel["name"]

            if target1.name <= target2.name:
                # Put the M2M field on target1
                rel_name = p.plural(target2.name.lower())  # Use plural of target2 as field name
                # Avoid name clashes
                if rel_name == target1.name.lower():
                    rel_name = f"{rel_name}_list"

                # Check if name already exists in target1's relationships
                existing_rel_names = {r["name"] for r in target1.relationships}
                if rel_name in existing_rel_names:
                    rel_name = f"{rel_name}_via_{_join_table.name}"

                m2m_rel = {
                    "name": rel_name,
                    "type": "many-to-many",
                    "target_table": target2.name,
                    "target_model_name": target2.model_name,
                    "through": _join_table.name,
                    "through_model": _join_table.model_name,
                    "source_field": fk1_column,
                    "target_field": fk2_column,
                    "related_name": p.plural(target1.name.lower()),  # For reverse relation
                    "is_self_referential": False,
                    "django_field_options": {
                        "through": _join_table.model_name,
                        "through_fields": (fk1_field_name or fk1_column, fk2_field_name or fk2_column),
                        "blank": True,
                        "related_name": p.plural(target1.name.lower()),
                    }
                }

                # Add metadata fields if any
                if metadata_fields:
                    m2m_rel["metadata_fields"] = metadata_fields
                    m2m_rel["has_relationship_attributes"] = True

                # Add the M2M relationship to target1 only
                target1.relationships.append(m2m_rel)

                logger.info(f"Created M2M relationship on {target1.name} pointing to {target2.name} through {_join_table.name}")
            else:
                # Put the M2M field on target2
                rel_name = p.plural(target1.name.lower())  # Use plural of target1 as field name
                # Avoid name clashes
                if rel_name == target2.name.lower():
                    rel_name = f"{rel_name}_list"

                # Check if name already exists in target2's relationships
                existing_rel_names = {r["name"] for r in target2.relationships}
                if rel_name in existing_rel_names:
                    rel_name = f"{rel_name}_via_{_join_table.name}"

                m2m_rel = {
                    "name": rel_name,
                    "type": "many-to-many",
                    "target_table": target1.name,
                    "target_model_name": target1.model_name,
                    "through": _join_table.name,
                    "through_model": _join_table.model_name,
                    "source_field": fk2_column,  # Note the reversed columns
                    "target_field": fk1_column,
                    "related_name": p.plural(target2.name.lower()),  # For reverse relation
                    "is_self_referential": False,
                    "django_field_options": {
                        "through": _join_table.model_name,
                        "through_fields": (fk2_field_name or fk2_column, fk1_field_name or fk1_column),  # Reversed
                        "blank": True,
                        "related_name": p.plural(target2.name.lower()),
                    }
                }

                # Add metadata fields if any
                if metadata_fields:
                    m2m_rel["metadata_fields"] = metadata_fields
                    m2m_rel["has_relationship_attributes"] = True

                # Add the M2M relationship to target2 only
                target2.relationships.append(m2m_rel)

                logger.info(f"Created M2M relationship on {target2.name} pointing to {target1.name} through {_join_table.name}")


def build_intermediate_representation(schema_infos: List[TableInfo]) -> List[TableInfo]:
    """
    Process raw schema info using domain services for mapping and analysis.

    This function orchestrates the transformation of database schema information
    into Django model representations using the domain layer services.

    Args:
        schema_infos: List of TableInfo from database introspection

    Returns:
        List of processed TableInfo with mapped fields, relationships, and constraints
    """
    logger.info(
        "Building intermediate representation using domain services..."
    )
    intermediate_repr: List[TableInfo] = []

    # Initialize domain services
    field_mapper = DomainFieldMapper()
    relationship_analyzer = RelationshipAnalyzer()
    constraint_analyzer = ConstraintAnalyzer()

    # --- Pass 1: Map basic fields using domain service ---
    for table_info in schema_infos:
        # Set model name using naming convention
        if not table_info.model_name:
            table_info.model_name = to_pascal_case(table_info.name)

        logger.info(
            f"Mapping table '{table_info.name}' to model '{table_info.model_name}'"
        )

        # Use domain field mapper for field mapping
        django_fields = []
        for col in table_info.columns:
            try:
                # Use domain field mapping service
                field_mapping = field_mapper.map_column(col)
                field_name = clean_field_name(col.name)

                django_fields.append(
                    {
                        "name": field_name,
                        "type": field_mapping.django_field_type,
                        "options": field_mapping.django_field_options,
                        "original_column_name": col.name,
                        "is_pk": col.is_pk,
                        "is_fk": col.is_foreign_key,
                        "is_handled_by_relation": False,  # Initial default
                        "openapi_schema": field_mapping.openapi_schema,
                        "field_mapping": field_mapping,  # Store domain mapping
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to map column {col.name}: {e}")
                # Fallback to legacy mapping
                django_field_type, django_options = map_db_type_to_django(col, table_info)
                field_name = clean_field_name(col.name)
                django_fields.append(
                    {
                        "name": field_name,
                        "type": django_field_type,
                        "options": django_options,
                        "original_column_name": col.name,
                        "is_pk": col.is_pk,
                        "is_fk": col.is_foreign_key,
                        "is_handled_by_relation": False,
                        "openapi_schema": map_db_type_to_openapi(col),
                    }
                )

        table_info.fields = django_fields
        intermediate_repr.append(table_info)

    # --- Pass 2: Analyze Relationships using domain service ---
    try:
        relationships = relationship_analyzer.analyze_relationships(intermediate_repr)

        # Convert domain relationships to legacy format for compatibility
        for table_info in intermediate_repr:
            table_relationships = [
                rel for rel in relationships
                if rel.source_table == table_info.name
            ]

            # Convert to legacy format for now (backward compatibility)
            legacy_relationships = []
            for rel in table_relationships:
                legacy_rel = {
                    "name": rel.name,
                    "type": rel.relationship_type.value,
                    "target_table": rel.target_table,
                    "related_name": rel.related_name,
                    "on_delete": rel.on_delete,
                    "source_columns": rel.source_columns,
                    "target_columns": rel.target_columns
                }

                # Add M2M-specific fields if they exist
                if rel.through_table:
                    legacy_rel["through"] = rel.through_table
                if rel.through_fields:
                    legacy_rel["through_fields"] = rel.through_fields
                if rel.symmetrical is not None:
                    legacy_rel["symmetrical"] = rel.symmetrical

                legacy_relationships.append(legacy_rel)

            table_info.relationships = legacy_relationships

        # Domain service doesn't mark fields as handled yet, so we need to do this manually
        # Mark foreign key fields as handled by relationships
        for table_info in intermediate_repr:
            for rel in table_info.relationships:
                # For many-to-one relationships, mark the source FK column as handled
                if rel.get("type") in ("many-to-one", "many_to_one"):
                    # Use the actual source columns from the relationship
                    source_columns = rel.get("source_columns", [])

                    for source_col in source_columns:
                        # Mark the corresponding field as handled
                        for field_dict in table_info.fields:
                            if field_dict.get("original_column_name") == source_col:
                                field_dict["is_handled_by_relation"] = True
                                logger.debug(f"Marking field {table_info.name}.{field_dict['name']} (column: {source_col}) as handled by relation {rel.get('name')}")
                                break

    except Exception as e:
        logger.warning(f"Domain relationship analysis failed, using legacy: {e}")
        # Fallback to legacy relationship analysis
        table_map = {info.name: info for info in intermediate_repr}
        analyze_relationships_django(intermediate_repr, table_map)

    logger.info("Relationship analysis complete.")

    # --- Pass 3: Process Constraints using domain service ---
    logger.info("Processing constraints and indexes using domain services...")
    for table_info in intermediate_repr:  # Iterate again over the updated tables
        meta_constraints = []
        meta_indexes = []
        db_check_constraints = []
        processed_constraint_names = set()
        current_field_names_in_model = {
            f["name"] for f in table_info.fields if not f["is_handled_by_relation"]
        }
        current_relation_names_in_model = {r["name"] for r in table_info.relationships}
        valid_model_field_names = current_field_names_in_model.union(
            current_relation_names_in_model
        )

        # Quick lookup: original DB column -> field dict
        col_to_field_dict_map = {
            f["original_column_name"]: f for f in table_info.fields
        }

        for constraint in table_info.constraints:
            constraint_name = constraint.name
            if constraint_name in processed_constraint_names:
                continue
            columns = constraint.columns
            if not columns:
                continue

            # Get constraint data - build from ConstraintInfo attributes
            c_data = {
                "unique": constraint.constraint_type == "unique" or constraint.is_unique_index,
                "primary_key": constraint.constraint_type == "primary_key",
                "foreign_key": constraint.constraint_type == "foreign_key",
                "index": constraint.constraint_type == "index" or constraint.is_unique_index,
                "check": constraint.constraint_type == "check",
                "definition": constraint.definition
            }

            # --- Determine correct Django field names for this constraint/index ---
            mapped_field_names_for_meta = []
            constraint_is_valid = True
            for original_col_name in columns:
                field_dict = col_to_field_dict_map.get(original_col_name)
                if not field_dict:
                    logger.warning(
                        f"Cannot process constraint/index '{constraint_name}' on table '{table_info.name}': Original column '{original_col_name}' has no mapped field."
                    )
                    constraint_is_valid = False
                    break

                if field_dict["is_handled_by_relation"]:
                    # Find the corresponding relationship that handles this FK column
                    related_rel = next(
                        (
                            rel
                            for rel in table_info.relationships
                            if original_col_name in rel.get("source_columns", [])
                        ),
                        None,
                    )
                    if related_rel and related_rel["name"] in valid_model_field_names:
                        mapped_field_names_for_meta.append(
                            related_rel["name"]
                        )  # Use the relationship name (e.g., author_rel)
                    else:
                        logger.warning(
                            f"Cannot process constraint/index '{constraint_name}' on table '{table_info.name}': Could not find valid relationship field for FK column '{original_col_name}'."
                        )
                        constraint_is_valid = False
                        break
                elif field_dict["name"] in valid_model_field_names:
                    # Use the direct field name (e.g., title, status)
                    mapped_field_names_for_meta.append(field_dict["name"])
                else:
                    # This case shouldn't happen if field mapping is correct
                    logger.warning(
                        f"Cannot process constraint/index '{constraint_name}' on table '{table_info.name}': Mapped field '{field_dict['name']}' for column '{original_col_name}' seems invalid."
                    )
                    constraint_is_valid = False
                    break

            if not constraint_is_valid:
                continue  # Skip this constraint/index

            # Now use 'mapped_field_names_for_meta' which contains correct Django field names
            is_unique = c_data.get("unique", False)
            is_pk = c_data.get("primary_key", False)
            is_fk = c_data.get("foreign_key", False)
            is_index = c_data.get("index", False)
            is_check = c_data.get("check", False)

            # 1. Handle Multi-Column Unique Constraints -> models.UniqueConstraint
            if is_unique and not is_pk and not is_fk and len(columns) > 1:
                meta_constraints.append(
                    {
                        "type": "unique",
                        "fields": sorted(
                            mapped_field_names_for_meta
                        ),  # Use correct field names
                        "name": constraint_name,
                    }
                )
                processed_constraint_names.add(constraint_name)
                if is_index:
                    processed_constraint_names.add(constraint_name + "_idx")

            # 2. Handle Indexes -> models.Index
            elif is_index and not is_pk and not is_fk:
                is_single_col_unique_field = len(
                    mapped_field_names_for_meta
                ) == 1 and any(
                    f["name"] == mapped_field_names_for_meta[0]
                    and f["options"].get("unique")
                    for f in table_info.fields
                )
                is_multi_col_unique_constraint = (
                    is_unique
                    and len(columns) > 1
                    and any(mc["name"] == constraint_name for mc in meta_constraints)
                )
                if (
                    not is_single_col_unique_field
                    and not is_multi_col_unique_constraint
                ):
                    meta_indexes.append(
                        {
                            "fields": mapped_field_names_for_meta,  # Use correct field names
                            "name": constraint_name,  # Keep DB name for index object
                        }
                    )
                    processed_constraint_names.add(constraint_name)

            # 3. Note DB Check Constraints
            elif is_check:
                db_check_constraints.append(
                    {
                        "name": constraint_name,
                        "definition": c_data.get("definition", "?"),
                    }
                )
                processed_constraint_names.add(constraint_name)

        # Update the TableInfo object
        table_info.meta_constraints = meta_constraints
        table_info.meta_indexes = meta_indexes
        table_info.db_check_constraints = db_check_constraints

    logger.info("Intermediate representation processing complete.")
    return intermediate_repr
