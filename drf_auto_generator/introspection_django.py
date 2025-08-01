"""
Database introspection module for DRF Auto Generator.

This module provides Django-based database introspection functionality using
Django's built-in database introspection capabilities. It generates domain models
from database schema information.

The introspection process:
1. Configures Django with database settings
2. Uses Django's introspection API to examine database schema
3. Converts raw database information to domain models
4. Analyzes relationships, constraints, and indexes
"""

import logging
import django
from django.db import connections, DEFAULT_DB_ALIAS
from django.conf import settings
from django.db.backends.postgresql.introspection import DatabaseIntrospection
from typing import List, Optional, Dict, Any, Set, Tuple

# Import domain models instead of defining local ones
from drf_auto_generator.domain.models import TableInfo, ColumnInfo, ConstraintInfo


# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _map_constraint_type(constraint_data: Dict[str, Any]) -> str:
    """Map Django constraint data to domain constraint type."""
    if constraint_data.get('primary_key'):
        return 'primary_key'
    elif constraint_data.get('unique'):
        return 'unique'
    elif constraint_data.get('foreign_key'):
        return 'foreign_key'
    elif constraint_data.get('check'):
        return 'check'
    elif constraint_data.get('index'):
        return 'index'
    else:
        return 'unknown'

# --- Django Setup Helper ---
_django_setup_done = False


def setup_django(db_settings: Dict[str, Any], secret_key: str):
    """Configures minimal Django settings and runs django.setup()."""
    global _django_setup_done
    if _django_setup_done:
        logger.debug("Django setup already performed.")
        return

    logger.info("Configuring Django settings for introspection...")
    try:
        # --- Convert Pydantic models to plain dicts for Django settings ---
        plain_db_settings: Dict[str, Dict[str, Any]] = {}
        for alias, db_model in db_settings.items():
            # Check if it's a Pydantic model (has .dict method)
            if hasattr(db_model, "dict") and callable(db_model.dict):
                # Convert to dict, excluding None values for cleaner settings
                # This mimics Django's behavior where missing keys are handled internally
                plain_db_settings[alias] = db_model.dict(exclude_none=True)
            elif isinstance(db_model, dict):  # If it somehow already is a dict
                plain_db_settings[alias] = db_model  # Use as is
            else:
                # Handle unexpected type if necessary
                logger.error(
                    f"Unexpected type for database settings '{alias}': {type(db_model)}. Expected Pydantic model or dict."
                )
                raise TypeError(f"Invalid database settings type for alias '{alias}'.")
        # --------------------------------------------------------------------
        logger.debug(f"Using plain DB settings for Django: {plain_db_settings}")

        settings.configure(
            SECRET_KEY=secret_key,
            DATABASES=plain_db_settings,
            # Minimal INSTALLED_APPS might be needed by some backends/features
            # INSTALLED_APPS=['django.contrib.contenttypes', 'django.contrib.auth'],
            TIME_ZONE="UTC",  # Avoid timezone warnings
            USE_TZ=True,  # Avoid timezone warnings
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",  # Set a default
        )
        django.setup()
        _django_setup_done = True
        logger.info("Django setup complete.")
    except Exception as e:
        logger.error(f"Failed to configure Django: {e}", exc_info=True)
        raise  # Re-raise the exception to halt execution


# --- Helper Functions ---
def _get_column_details(
    description,
) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[int]]:
    """Helper to extract details potentially available on description tuple/object."""
    # Availability varies *greatly* by DB backend and Django version. Often None.
    internal_size = getattr(description, "internal_size", None)
    precision = getattr(description, "precision", None)
    scale = getattr(description, "scale", None)
    collation = getattr(description, "collation", None)
    return collation, internal_size, precision, scale


class CustomPostgreSQLIntrospection(DatabaseIntrospection):
    def get_field_type(self, data_type, description):
        try:
            return super().get_field_type(data_type, description)
        except Exception as e:
            logger.error(f"Error getting field type for {data_type}: {e}. Returning TextField as fallback.")
            return 'TextField'  # Fallback to TextField

    def is_enum_type(self, cursor, type_name):
        """Check if a given type is a PostgreSQL enum."""
        query = """
            SELECT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = %s AND typtype = 'e'
            )
        """
        cursor.execute(query, [type_name])
        return cursor.fetchone()[0]

    def get_enum_values(self, cursor, enum_type_name):
        """Fetch the values of a PostgreSQL enum type."""
        query = """
            SELECT enumlabel
            FROM pg_enum
            WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = %s)
            ORDER BY enumsortorder
        """
        cursor.execute(query, [enum_type_name])
        return [row[0] for row in cursor.fetchall()]

    def get_field_type_with_enum(self, cursor, data_type, description):
        """Get the field type, handling PostgreSQL enums."""
        type_name = description.name  # Get the type name
        if self.is_enum_type(cursor, type_name):
            enum_values = self.get_enum_values(cursor, type_name)
            return 'CharField', enum_values
        return self.get_field_type(data_type, description), None


# --- Main Introspection Function ---
def introspect_schema_django(
    db_alias: str = DEFAULT_DB_ALIAS,
    include_tables: Optional[List[str]] = None,
    exclude_tables: Optional[List[str]] = None,
) -> List[TableInfo]:
    """Introspects the database schema using Django's connection.introspection."""
    if not _django_setup_done:
        raise RuntimeError("Django has not been set up. Call setup_django() first.")

    logger.info(
        f"Starting schema introspection using Django backend for alias '{db_alias}'..."
    )
    try:
        # Get connection and introspector; setup_django should ensure this works
        conn = connections[db_alias]
        introspector = CustomPostgreSQLIntrospection(conn)
    except Exception as e:
        logger.error(
            f"Could not get Django connection or introspector for alias '{db_alias}': {e}"
        )
        return []  # Return empty list on failure

    all_tables_info: List[TableInfo] = []
    processed_tables: Set[str] = set()
    include_set = set(include_tables) if include_tables else None
    exclude_set = set(exclude_tables) if exclude_tables else set()

    try:
        # Use a cursor for database operations
        with conn.cursor() as cursor:
            # Get all tables and views
            all_db_items = introspector.get_table_list(cursor)
            logger.info(f"Found {len(all_db_items)} database items (tables/views).")
            logger.debug(
                f"Items found: {', '.join(item.name for item in all_db_items)}"
            )

            # Filter tables based on include/exclude lists and type
            tables_to_process = []
            for item in all_db_items:
                # Ensure 'item' has 'name' and 'type' (typically 't' or 'v')
                table_name = getattr(item, "name", None)
                item_type = getattr(
                    item, "type", "t"
                )  # Default to table if type missing

                if not table_name:
                    continue  # Skip if name is missing

                if item_type != "t":  # Skip views
                    logger.debug(f"Skipping item '{table_name}' (type: {item_type}).")
                    continue
                if table_name in exclude_set:
                    logger.info(f"Excluding table: {table_name}")
                    continue
                if include_set and table_name not in include_set:
                    logger.debug(
                        f"Skipping table '{table_name}' (not in include list)."
                    )
                    continue
                tables_to_process.append(table_name)

            if not tables_to_process:
                logger.warning("No tables selected for introspection after filtering.")
                return []

            logger.info(
                f"Introspecting selected tables: {', '.join(tables_to_process)}"
            )

            # Process each selected table
            for table_name in tables_to_process:
                if table_name in processed_tables:
                    continue

                logger.info(f"Processing table: {table_name}")
                columns_info = []

                # Get column descriptions
                try:
                    table_description = introspector.get_table_description(
                        cursor, table_name
                    )
                except Exception as e:
                    logger.error(
                        f"Could not get description for table '{table_name}': {e}. Skipping."
                    )
                    continue

                # Get constraints (PK, Unique, Check, Index)
                try:
                    constraints = introspector.get_constraints(cursor, table_name)
                    logger.debug(f"Constraints for '{table_name}': {constraints}")
                except Exception as e:
                    logger.warning(
                        f"Could not get constraints for table '{table_name}': {e}. Constraints may be incomplete."
                    )
                    constraints = {}

                # Get relations (Foreign Keys)
                try:
                    # Returns dict: {column_name: (pointed_to_col, pointed_to_table)}
                    relations = introspector.get_relations(cursor, table_name)
                    logger.debug(f"Relations for '{table_name}': {relations}")
                except NotImplementedError:
                    logger.warning(
                        f"Backend {conn.vendor} does not support get_relations. FK detection may rely solely on constraints."
                    )
                    relations = {}
                except Exception as e:
                    logger.warning(
                        f"Could not get relations for table '{table_name}': {e}."
                    )
                    relations = {}

                # --- Determine Primary Key Columns ---
                pk_col_name_single = None
                try:
                    # Some backends only support single PK col via this method
                    pk_col_name_single = introspector.get_primary_key_column(
                        cursor, table_name
                    )
                except NotImplementedError:
                    pass  # Ignore if not implemented, rely on constraints
                except Exception as e:
                    logger.warning(
                        f"Error calling get_primary_key_column for '{table_name}': {e}"
                    )

                pk_constraint = next(
                    (c for c in constraints.values() if c.get("primary_key")), None
                )
                pk_columns_from_constraint = (
                    pk_constraint.get("columns", []) if pk_constraint else []
                )

                # Combine results: prefer constraint, fallback to single method if constraint empty
                final_pk_columns = pk_columns_from_constraint
                if not final_pk_columns and pk_col_name_single:
                    final_pk_columns = [pk_col_name_single]
                logger.debug(
                    f"Primary key columns for '{table_name}': {final_pk_columns}"
                )

                # --- Process Columns ---
                for description in table_description:
                    col_name = description.name
                    # Defaults are hard - Django often doesn't retrieve them reliably/consistently.
                    # description.default might exist but its format is backend-specific.
                    default_val = None  # Safest to assume None for now
                    collation, internal_size, precision, scale = _get_column_details(
                        description
                    )

                    # Get field type and enum values (if applicable)
                    field_type = introspector.get_field_type(description.type_code, description)

                    # Create domain ColumnInfo with proper field type inference
                    col_info = ColumnInfo(
                        name=col_name,
                        db_type_string=field_type,
                        internal_size=internal_size,
                        precision=precision,
                        scale=scale,
                        nullable=description.null_ok,
                        default=default_val,
                        collation=collation,
                        is_pk=(col_name in final_pk_columns),
                        # enum_values=enum_values,  # Store enum values if applicable
                    )
                    columns_info.append(col_info)

                # --- Post-process: Mark Unique and FK based on Constraints/Relations ---
                unique_single_column_names = set()
                for c_data in constraints.values():
                    if c_data.get("unique") and len(c_data.get("columns", [])) == 1:
                        unique_single_column_names.add(c_data["columns"][0])
                    # Also consider unique indexes
                    if (
                        c_data.get("index")
                        and c_data.get("unique")
                        and len(c_data.get("columns", [])) == 1
                    ):
                        unique_single_column_names.add(c_data["columns"][0])

                fk_column_map: Dict[str, Tuple[str, str]] = (
                    {}
                )  # {fk_col_name: (target_table, target_col)}
                # Prefer 'relations' output if available
                if relations:
                    for fk_col, (target_col, target_table) in relations.items():
                        fk_column_map[fk_col] = (target_table, target_col)
                else:  # Fallback to parsing 'constraints' for FK info
                    for c_data in constraints.values():
                        if c_data.get("foreign_key") and isinstance(
                            c_data.get("foreign_key"), tuple
                        ):
                            fk_cols = c_data.get("columns", [])
                            target_table, target_col = c_data[
                                "foreign_key"
                            ]  # Assumes single target col
                            if len(fk_cols) == 1:  # Only handle single column FKs here
                                fk_column_map[fk_cols[0]] = (target_table, target_col)

                # Apply flags to ColumnInfo objects
                for col in columns_info:
                    if col.name in unique_single_column_names:
                        col.is_unique = True
                    if col.name in fk_column_map:
                        col.is_foreign_key = True
                        col.foreign_key_to = fk_column_map[col.name]

                # --- Create Domain TableInfo ---
                # Convert raw constraints to domain constraint models if needed
                constraint_infos = []
                for constraint_name, constraint_data in constraints.items():
                    constraint_info = ConstraintInfo(
                        name=constraint_name,
                        constraint_type=_map_constraint_type(constraint_data),
                        columns=constraint_data.get('columns', []),
                        definition=constraint_data.get('definition'),
                        is_deferrable=constraint_data.get('is_deferrable', False),
                        initially_deferred=constraint_data.get('initially_deferred', False)
                    )
                    constraint_infos.append(constraint_info)

                table_info = TableInfo(
                    name=table_name,
                    columns=columns_info,
                    primary_key_columns=final_pk_columns,
                    constraints=constraint_infos,
                    # Store raw data for backward compatibility during transition
                    raw_constraints=constraints,
                    raw_relations=relations,
                )
                all_tables_info.append(table_info)
                processed_tables.add(table_name)

        logger.info(
            f"Django introspection complete. Successfully processed {len(all_tables_info)} tables."
        )
        return all_tables_info

    except Exception as e:
        logger.error(
            f"Unexpected error during Django introspection: {e}", exc_info=True
        )
        # Depending on where it happened, might return partial results or empty
        return all_tables_info if all_tables_info else []
