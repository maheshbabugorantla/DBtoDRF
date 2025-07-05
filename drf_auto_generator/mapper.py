import logging
import re
from typing import List, Dict, Any, Tuple
import inflect

# Import from the new Django introspection module
from .introspection_django import TableInfo, ColumnInfo


logger = logging.getLogger(__name__)
p = inflect.engine()  # For pluralization/singularization


# --- Naming Convention Helpers ---
def to_snake_case(name: str) -> str:
    """Converts CamelCase or PascalCase to snake_case."""
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub("__([A-Z])", r"_\1", name)
    name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


def to_pascal_case(name: str) -> str:
    """Converts snake_case to PascalCase (ClassName)."""
    # Try to singularize table names for model names
    singular_name = p.singular_noun(name)
    if singular_name is False:  # inflect returns False if already singular or irregular
        singular_name = name
    # Handle cases like 'data' -> 'Data', 'series' -> 'Series' where singular is same
    if not singular_name:
        singular_name = name

    return "".join(word.capitalize() for word in singular_name.split("_"))


def clean_field_name(name: str) -> str:
    """Ensures field name is a valid Python identifier and not a keyword."""
    name = to_snake_case(name)
    # Remove invalid characters (allow underscore)
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    # Ensure it starts with a letter or underscore
    if name and not name[0].isalpha() and name[0] != "_":
        name = "_" + name
    # Handle Python keywords
    # List from: import keyword; keyword.kwlist
    keywords = {
        "False",
        "None",
        "True",
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
    }
    if name in keywords:
        name += "_"
    # Handle potential clash with 'pk' if the column name wasn't originally 'pk'
    if name == "pk" and name != "pk":
        name = "pk_val"  # Or another suitable suffix
    return name if name else "_field"  # Ensure non-empty name


# --- Type Mapping Dictionaries ---

# Maps type strings returned by Django introspection's get_field_type() to Django model fields.
# This is HIGHLY backend-dependent and needs extensive testing/refinement.
# Inspired by django.core.management.commands.inspectdb.Command.data_types_reverse
# Use simple strings first, can refine with more specific types later.
DJANGO_FIELD_MAP = {
    # Generic Types (might be returned by get_field_type)
    "AutoField": "AutoField",
    "BigAutoField": "BigAutoField",
    "SmallAutoField": "SmallAutoField",
    "BooleanField": "BooleanField",
    "CharField": "CharField",
    "DateField": "DateField",
    "DateTimeField": "DateTimeField",
    "DecimalField": "DecimalField",
    "DurationField": "DurationField",
    "EmailField": "EmailField",
    "FileField": "FileField",
    "FilePathField": "FilePathField",
    "FloatField": "FloatField",
    "GenericIPAddressField": "GenericIPAddressField",
    "ImageField": "ImageField",
    "IntegerField": "IntegerField",
    "BigIntegerField": "BigIntegerField",
    "SmallIntegerField": "SmallIntegerField",
    "JSONField": "JSONField",
    "PositiveBigIntegerField": "PositiveBigIntegerField",
    "PositiveIntegerField": "PositiveIntegerField",
    "PositiveSmallIntegerField": "PositiveSmallIntegerField",
    "SlugField": "SlugField",
    "TextField": "TextField",
    "TimeField": "TimeField",
    "URLField": "URLField",
    "UUIDField": "UUIDField",
    "BinaryField": "BinaryField",
    # Add more specific backend types if needed, e.g.:
    # 'geometry': 'django.contrib.gis.db.models.GeometryField', # If using PostGIS
    # 'jsonb': 'JSONField', # PostgreSQL JSONB often maps to JSONField
    # 'varchar': 'CharField', # Explicit mapping if needed
    # 'int': 'IntegerField',
}


# Maps Django Model Field types (or common DB types) to OpenAPI schema types/formats.
OPENAPI_TYPE_MAP = {
    "AutoField": {"type": "integer", "readOnly": True},
    "BigAutoField": {"type": "integer", "format": "int64", "readOnly": True},
    "SmallAutoField": {"type": "integer", "readOnly": True},
    "IntegerField": {"type": "integer"},
    "BigIntegerField": {"type": "integer", "format": "int64"},
    "SmallIntegerField": {"type": "integer"},
    "PositiveIntegerField": {"type": "integer", "minimum": 0},
    "PositiveBigIntegerField": {"type": "integer", "format": "int64", "minimum": 0},
    "PositiveSmallIntegerField": {"type": "integer", "minimum": 0},
    "BooleanField": {"type": "boolean"},
    "FloatField": {"type": "number", "format": "float"},
    "DecimalField": {
        "type": "number",
        "format": "double",
    },  # Or use 'string' for exact precision
    "CharField": {"type": "string"},
    "TextField": {"type": "string"},
    "EmailField": {"type": "string", "format": "email"},
    "SlugField": {"type": "string", "pattern": r"^[-a-zA-Z0-9_]+$"},
    "URLField": {"type": "string", "format": "uri"},
    "UUIDField": {"type": "string", "format": "uuid"},
    "DateField": {"type": "string", "format": "date"},
    "DateTimeField": {"type": "string", "format": "date-time"},
    "TimeField": {
        "type": "string",
        "format": "time",
    },  # Custom format, OpenAPI standard is date-time
    "DurationField": {
        "type": "string",
        "format": "duration",
    },  # ISO 8601 duration format
    "JSONField": {
        "type": "object",
        "additionalProperties": True,
    },  # Allows any JSON structure
    "BinaryField": {"type": "string", "format": "byte"},  # Base64 encoded string
    "FileField": {
        "type": "string",
        "format": "uri",
        "readOnly": True,
    },  # Often represented as URL
    "ImageField": {
        "type": "string",
        "format": "uri",
        "readOnly": True,
    },  # Often represented as URL
    "GenericIPAddressField": {
        "type": "string",
        "format": "ipv4 or ipv6",
    },  # Clarify format
    # Default fallback
    "Unknown": {"type": "string", "description": "Type mapping fallback."},
}


# --- Mapping Functions ---


def map_db_type_to_django(col: ColumnInfo, table_info: TableInfo = None) -> Tuple[str, Dict[str, Any]]:
    """Maps DB type string (from Django introspection) to Django model field type and options."""

    # 1. Get the base Django field type from mapping
    field_type = DJANGO_FIELD_MAP.get(col.db_type_string, "TextField")

    # 2. Base Options from ColumnInfo attributes
    options: Dict[str, Any] = {}

    # Basic nullability & unique
    if col.nullable:
        options["null"] = True
    if col.is_unique and not col.is_pk:  # PKs are implicitly unique
        options["unique"] = True

    # Size-related options for specific types
    if field_type in ("CharField", "TextField") and col.internal_size:
        # Note: If internal_size is -1 or very large, maybe skip max_length
        if col.internal_size > 0:
            options["max_length"] = col.internal_size
    elif field_type == "DecimalField":
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
            if field_type in ("AutoField", "BigAutoField", "SmallAutoField"):
                if field_type == "BigAutoField":
                    field_type = "BigIntegerField"
                elif field_type == "SmallAutoField":
                    field_type = "SmallIntegerField"
                else:  # AutoField
                    field_type = "IntegerField"
                logger.debug(f"Column {col.name} is part of composite PK, converting {col.db_type_string} from AutoField back to {field_type}")

            options.pop("primary_key", None)  # Don't mark individual fields as primary_key=True
            logger.debug(f"Column {col.name} is part of composite PK, keeping type: {field_type}")
            # Do NOT convert to AutoField for composite primary keys
        else:
            # Single primary key - check if it looks like an auto-incrementing integer PK
            is_standard_int_pk = field_type in (
                "IntegerField",
                "BigIntegerField",
                "SmallIntegerField",
            )
            # `inspectdb` has complex logic checking sequences/defaults. We simplify:
            # Assume integer PKs are auto-incrementing unless specified otherwise.
            if is_standard_int_pk:
                if "Big" in field_type:
                    field_type = "BigAutoField"
                elif "Small" in field_type:
                    field_type = "SmallAutoField"
                else:
                    field_type = "AutoField"
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
    if col.nullable and field_type in (
        "CharField",
        "TextField",
        "EmailField",
        "URLField",
        "SlugField",
    ):
        options["blank"] = True
        # Keep null=True if the DB explicitly allows NULL, for consistency? Or remove it?
        # Django practice leans towards blank=True, null=False for string fields. Let's try that.
        # options['null'] = False # Overwrite null for these types if nullable? Risky.
    elif not col.nullable and field_type not in (
        "BooleanField",
    ):  # Set blank=False if not nullable (bool handles null differently)
        options["blank"] = False

    # Handle defaults (introspection often doesn't retrieve them properly)
    if col.default is not None:  # Only set if explicitly provided
        # Maybe parse string defaults like 'uuid4()' into UUID field defaults
        if field_type == "UUIDField" and str(col.default).lower() in [
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
    field_type = DJANGO_FIELD_MAP.get(col.db_type_string, "TextField")

    # For OpenAPI purposes, we treat all primary key integer fields as AutoField
    # since we don't have table context to determine if it's composite
    if col.is_pk and field_type in ("IntegerField", "BigIntegerField", "SmallIntegerField"):
        if "Big" in field_type:
            field_type = "BigAutoField"
        elif "Small" in field_type:
            field_type = "SmallAutoField"
        else:
            field_type = "AutoField"

    # Get the base schema from the OpenAPI map
    schema = OPENAPI_TYPE_MAP.get(field_type, OPENAPI_TYPE_MAP["Unknown"]).copy()

    # Apply constraints/details from ColumnInfo to the schema
    schema["nullable"] = col.nullable

    # Add maxLength if applicable and available
    if field_type in ("CharField", "TextField") and col.internal_size and col.internal_size > 0:
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

            # Generate relationship field name (e.g., 'author' from 'author_id')
            rel_name_base = (
                fk_col_name.rsplit("_id", 1)[0]
                if fk_col_name.endswith("_id")
                else fk_col_name
            )
            rel_name_guess = clean_field_name(rel_name_base)

            # Avoid name clash with the FK field itself (if cleaning didn't change it)
            if rel_name_guess == clean_field_name(fk_col_name):
                rel_name_guess += (
                    "_rel"  # Add suffix to distinguish relation field from FK field
                )
            # Avoid clash with target model name (lowercase)
            if rel_name_guess == target_model_name.lower():
                rel_name_guess += "_rel"

            # Get null/blank status from the original FK column
            fk_col_obj = next((c for c in table.columns if c.name == fk_col_name), None)
            fk_nullable = (
                fk_col_obj.nullable if fk_col_obj else True
            )  # Default to True if column not found
            fk_blankable = fk_nullable  # Simple assumption: blank = null for FKs

            # TODO: Determine on_delete (requires specific constraint info or config)
            on_delete_action = "CASCADE"

            # Generate unique related_name to avoid clashes
            # Count how many FKs from current table already point to target_table
            existing_rels_to_target = [r for r in relationships if r.get("target_table") == target_table_name]
            base_related_name = p.plural(table.name)

            if len(existing_rels_to_target) == 0:
                # First FK to this target - use simple plural name
                related_name = base_related_name
            else:
                # Multiple FKs to same target - make related_name unique
                # Use the field name to differentiate
                related_name = f"{base_related_name}_{rel_name_guess}"

            # ManyToOne relationship from current table to target table
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
                "django_field_options": {
                    "on_delete": on_delete_action,
                    "db_column": fk_col_name,  # Explicitly set db_column for clarity
                    "null": fk_nullable,
                    "blank": fk_blankable,
                    # Add verbose_name, help_text later?
                },
            }
            relationships.append(mto_rel)

            # Mark the original FK column's corresponding Django field as 'handled'
            # so it's not rendered directly in models.py if the FK relation field exists
            for field_data in table.fields:
                if field_data["original_column_name"] == fk_col_name:
                    field_data["is_handled_by_relation"] = True
                    logger.debug(
                        f"Marking field {table.name}.{field_data['name']} as handled by relation {rel_name_guess}"
                    )
                    break

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
            not f["name"].lower() in (
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
                        not field["name"].lower() in (
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

        # Get the model objects        m2m_rel = {
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
    """Processes raw schema info, applies mappings & conventions, extracts meta constraints/indexes."""
    logger.info(
        "Building intermediate representation (from Django introspection results)..."
    )
    intermediate_repr: List[TableInfo] = []
    table_map: Dict[str, TableInfo] = {info.name: info for info in schema_infos}

    # --- Pass 1: Map basic fields ---
    for table_info in schema_infos:
        table_info.model_name = to_pascal_case(table_info.name)
        logger.info(
            f"Mapping table '{table_info.name}' to model '{table_info.model_name}'"
        )
        django_fields = []
        for col in table_info.columns:
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
                    "is_handled_by_relation": False,  # Initial default
                    "openapi_schema": map_db_type_to_openapi(col),
                }
            )
        table_info.fields = django_fields
        intermediate_repr.append(table_info)  # Add tables with basic fields mapped

    # --- Pass 2: Analyze Relationships (Updates 'is_handled_by_relation' flag) ---
    analyze_relationships_django(intermediate_repr, table_map)
    logger.info("Relationship analysis complete.")

    # --- Pass 3: Process Constraints/Indexes using final field info ---
    logger.info("Processing constraints and indexes for Meta...")
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

        for constraint_name, c_data in table_info.constraints.items():
            if constraint_name in processed_constraint_names:
                continue
            columns = c_data.get("columns", [])
            if not columns:
                continue

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
