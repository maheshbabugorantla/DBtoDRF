import logging
import re
from typing import List, Dict, Any, Tuple
import inflect

# Import from the new Django introspection module
from .introspection_django import TableInfo, ColumnInfo


logger = logging.getLogger(__name__)
p = inflect.engine() # For pluralization/singularization


# --- Naming Convention Helpers ---
def to_snake_case(name: str) -> str:
    """Converts CamelCase or PascalCase to snake_case."""
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    name = re.sub('__([A-Z])', r'_\1', name)
    name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name)
    return name.lower()


def to_pascal_case(name: str) -> str:
    """Converts snake_case to PascalCase (ClassName)."""
    # Try to singularize table names for model names
    singular_name = p.singular_noun(name)
    if singular_name is False: # inflect returns False if already singular or irregular
        singular_name = name
    # Handle cases like 'data' -> 'Data', 'series' -> 'Series' where singular is same
    if not singular_name:
        singular_name = name

    return ''.join(word.capitalize() for word in singular_name.split('_'))


def clean_field_name(name: str) -> str:
    """Ensures field name is a valid Python identifier and not a keyword."""
    name = to_snake_case(name)
    # Remove invalid characters (allow underscore)
    name = re.sub(r'[^a-zA-Z0-9_]', '', name)
    # Ensure it starts with a letter or underscore
    if name and not name[0].isalpha() and name[0] != '_':
        name = '_' + name
    # Handle Python keywords
    # List from: import keyword; keyword.kwlist
    keywords = {
        'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break',
        'class', 'continue', 'def', 'del', 'elif', 'else', 'except', 'finally',
        'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
        'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try', 'while',
        'with', 'yield'
    }
    if name in keywords:
        name += '_'
    # Handle potential clash with 'pk' if the column name wasn't originally 'pk'
    if name == 'pk' and name != 'pk':
        name = 'pk_val' # Or another suitable suffix
    return name if name else '_field' # Ensure non-empty name


# --- Type Mapping Dictionaries ---

# Maps type strings returned by Django introspection's get_field_type() to Django model fields.
# This is HIGHLY backend-dependent and needs extensive testing/refinement.
# Inspired by django.core.management.commands.inspectdb.Command.data_types_reverse
# Use simple strings first, can refine with more specific types later.
DJANGO_FIELD_MAP = {
    # Generic Types (might be returned by get_field_type)
    'AutoField': 'AutoField',
    'BigAutoField': 'BigAutoField',
    'SmallAutoField': 'SmallAutoField',
    'BooleanField': 'BooleanField',
    'CharField': 'CharField',
    'DateField': 'DateField',
    'DateTimeField': 'DateTimeField',
    'DecimalField': 'DecimalField',
    'DurationField': 'DurationField',
    'EmailField': 'EmailField',
    'FileField': 'FileField',
    'FilePathField': 'FilePathField',
    'FloatField': 'FloatField',
    'GenericIPAddressField': 'GenericIPAddressField',
    'ImageField': 'ImageField',
    'IntegerField': 'IntegerField',
    'BigIntegerField': 'BigIntegerField',
    'SmallIntegerField': 'SmallIntegerField',
    'JSONField': 'JSONField',
    'PositiveBigIntegerField': 'PositiveBigIntegerField',
    'PositiveIntegerField': 'PositiveIntegerField',
    'PositiveSmallIntegerField': 'PositiveSmallIntegerField',
    'SlugField': 'SlugField',
    'TextField': 'TextField',
    'TimeField': 'TimeField',
    'URLField': 'URLField',
    'UUIDField': 'UUIDField',
    'BinaryField': 'BinaryField',
    # Add more specific backend types if needed, e.g.:
    # 'geometry': 'django.contrib.gis.db.models.GeometryField', # If using PostGIS
    # 'jsonb': 'JSONField', # PostgreSQL JSONB often maps to JSONField
    # 'varchar': 'CharField', # Explicit mapping if needed
    # 'int': 'IntegerField',
}


# Maps Django Model Field types (or common DB types) to OpenAPI schema types/formats.
OPENAPI_TYPE_MAP = {
    'AutoField': {'type': 'integer', 'readOnly': True},
    'BigAutoField': {'type': 'integer', 'format': 'int64', 'readOnly': True},
    'SmallAutoField': {'type': 'integer', 'readOnly': True},
    'IntegerField': {'type': 'integer'},
    'BigIntegerField': {'type': 'integer', 'format': 'int64'},
    'SmallIntegerField': {'type': 'integer'},
    'PositiveIntegerField': {'type': 'integer', 'minimum': 0},
    'PositiveBigIntegerField': {'type': 'integer', 'format': 'int64', 'minimum': 0},
    'PositiveSmallIntegerField': {'type': 'integer', 'minimum': 0},
    'BooleanField': {'type': 'boolean'},
    'FloatField': {'type': 'number', 'format': 'float'},
    'DecimalField': {'type': 'number', 'format': 'double'}, # Or use 'string' for exact precision
    'CharField': {'type': 'string'},
    'TextField': {'type': 'string'},
    'EmailField': {'type': 'string', 'format': 'email'},
    'SlugField': {'type': 'string', 'pattern': r'^[-a-zA-Z0-9_]+$'},
    'URLField': {'type': 'string', 'format': 'uri'},
    'UUIDField': {'type': 'string', 'format': 'uuid'},
    'DateField': {'type': 'string', 'format': 'date'},
    'DateTimeField': {'type': 'string', 'format': 'date-time'},
    'TimeField': {'type': 'string', 'format': 'time'}, # Custom format, OpenAPI standard is date-time
    'DurationField': {'type': 'string', 'format': 'duration'}, # ISO 8601 duration format
    'JSONField': {'type': 'object', 'additionalProperties': True}, # Allows any JSON structure
    'BinaryField': {'type': 'string', 'format': 'byte'}, # Base64 encoded string
    'FileField': {'type': 'string', 'format': 'uri', 'readOnly': True}, # Often represented as URL
    'ImageField': {'type': 'string', 'format': 'uri', 'readOnly': True},# Often represented as URL
    'GenericIPAddressField': {'type': 'string', 'format': 'ipv4 or ipv6'}, # Clarify format
    # Default fallback
    'Unknown': {'type': 'string', 'description': 'Type mapping fallback.'}
}


# --- Mapping Functions ---

def map_db_type_to_django(col: ColumnInfo) -> Tuple[str, Dict[str, Any]]:
    """Maps DB type string (from Django introspection) to Django model field type and options."""
    db_type = col.db_type_string # This is the key for mapping
    options: Dict[str, Any] = {}

    # 1. Find Direct Match in Map
    field_type = DJANGO_FIELD_MAP.get(db_type, None)

    # 2. Fallback Logic (if no direct match) - Inspired by inspectdb
    if field_type is None:
        logger.warning(f"Unknown DB type '{db_type}' for column '{col.name}'. Attempting fallback mapping.")
        db_type_lower = db_type.lower() if db_type else ''
        if 'text' in db_type_lower:
            field_type = 'TextField'
        elif 'char' in db_type_lower or 'string' in db_type_lower or 'varchar' in db_type_lower:
            field_type = 'CharField'
        elif 'int' in db_type_lower:
            field_type = 'IntegerField' # Needs refinement for small/big int
        elif 'bool' in db_type_lower:
            field_type = 'BooleanField'
        elif 'date' in db_type_lower and 'time' not in db_type_lower:
            field_type = 'DateField'
        elif 'time' in db_type_lower and 'date' in db_type_lower:
            field_type = 'DateTimeField' # Timestamp/Datetime
        elif 'time' in db_type_lower:
            field_type = 'TimeField'
        elif 'float' in db_type_lower or 'double' in db_type_lower or 'real' in db_type_lower:
            field_type = 'FloatField'
        elif 'decimal' in db_type_lower or 'numeric' in db_type_lower:
            field_type = 'DecimalField'
        elif 'uuid' in db_type_lower:
            field_type = 'UUIDField'
        elif 'json' in db_type_lower:
            field_type = 'JSONField'
        elif 'binary' in db_type_lower or 'blob' in db_type_lower:
            field_type = 'BinaryField'
        elif 'duration' in db_type_lower:
            field_type = 'DurationField'
        # Add more backend-specific fallbacks as needed
        else: # Ultimate fallback
            logger.error(f"Could not map DB type '{db_type}' for column '{col.name}'. Defaulting to TextField.")
            field_type = 'TextField'

    # 3. Refine Field Type and Options based on ColumnInfo
    if col.is_pk:
        # Check if it looks like an auto-incrementing integer PK
        is_standard_int_pk = field_type in ('IntegerField', 'BigIntegerField', 'SmallIntegerField')
        # `inspectdb` has complex logic checking sequences/defaults. We simplify:
        # Assume integer PKs are auto-incrementing unless specified otherwise.
        if is_standard_int_pk:
            if 'Big' in field_type:
                field_type = 'BigAutoField'
            elif 'Small' in field_type:
                field_type = 'SmallAutoField'
            else:
                field_type = 'AutoField'
            options.pop('primary_key', None) # AutoFields have implicit primary_key=True
        else: # Non-integer PK (e.g., UUID, CharField)
            options['primary_key'] = True
            # Ensure default is not set for non-auto PKs if introspection didn't provide one
            options.pop('default', None)
    else: # Not a PK
        options.pop('primary_key', None)

    # Handle Nullability & Blank
    options['null'] = col.nullable
    # Django convention: Char/Text fields usually use blank=True instead of null=True
    if col.nullable and field_type in ("CharField", "TextField", "EmailField", "URLField", "SlugField"):
        options['blank'] = True
        # Keep null=True if the DB explicitly allows NULL, for consistency? Or remove it?
        # Django practice leans towards blank=True, null=False for string fields. Let's try that.
        # options['null'] = False # Overwrite null for these types if nullable? Risky.
    elif not col.nullable and field_type not in ("BooleanField",): # Set blank=False if not nullable (bool handles null differently)
        options['blank'] = False

    # Handle Unique constraints (single column)
    if col.is_unique and not col.is_pk and not col.is_foreign_key:
        options['unique'] = True

    # Handle Max Length for CharField
    if field_type == 'CharField':
        if 'max_length' not in options: # Only set if not already inferred
            options['max_length'] = col.internal_size if col.internal_size and col.internal_size > 0 else 255 # Default fallback

    # Handle Decimal Precision/Scale
    if field_type == 'DecimalField':
         if 'max_digits' not in options:
            options['max_digits'] = col.precision if col.precision else 10
         if 'decimal_places' not in options:
            options['decimal_places'] = col.scale if col.scale else 2

    # Default Value (Very basic - assumes default string is directly usable)
    # This needs significant improvement based on field type and default format.
    # if col.default is not None and not col.is_pk and 'default' not in options:
    #    options['default'] = col.default # Store as string, template needs to handle quoting/casting

    # Use db_column if cleaned Python name differs from original DB column name
    cleaned_name = clean_field_name(col.name)

    # Only add db_column if the names differ *after* lowercasing,
    # OR if the cleaned name is different but the lowercased versions are the same
    # (meaning cleaning did more than just change case, e.g. adding underscore for keywords)

    if cleaned_name.lower() != col.name.lower():
        options['db_column'] = col.name
        logger.debug(f"Adding db_column='{col.name}' for field '{cleaned_name}' because names differ significantly.")

    elif cleaned_name != col.name:
        # Case differs, but lower versions match. Django might handle this.
        # Decide whether to add db_column for explicitness or omit for brevity.
        # Let's OMIT it for less noise, relying on Django's default mapping for simple case changes.
        logger.debug(f"Omitting db_column for field '{cleaned_name}' (original: '{col.name}') as only case differs.")
        pass # Do not add db_column just for case difference

    # Add collation if available (requires Django 4.1+)
    # Add collation if available (requires Django 4.1+)
    # if col.collation and hasattr(models, 'collation'): # Check Django version capability
    #      options['db_collation'] = col.collation

    # Ensure AutoFields don't have conflicting options like 'default'
    if 'Auto' in field_type:
        options.pop('default', None)
        options.pop('null', None)
        options.pop('blank', None)
        options.pop('unique', None) # PK implies unique

    return field_type, options


def map_db_type_to_openapi(col: ColumnInfo) -> Dict[str, Any]:
    """Maps DB type string (or derived Django field type) to OpenAPI schema properties."""
    # First, determine the corresponding Django field type
    django_field_type, _ = map_db_type_to_django(col)

    # Get the base schema from the OpenAPI map
    schema = OPENAPI_TYPE_MAP.get(django_field_type, OPENAPI_TYPE_MAP['Unknown']).copy()

    # Apply constraints/details from ColumnInfo to the schema
    schema['nullable'] = col.nullable

    # Add maxLength if applicable and available
    if django_field_type == 'CharField' and col.internal_size and col.internal_size > 0:
         schema['maxLength'] = col.internal_size

    # Ensure readOnly is set for PKs if not already handled by type map
    if col.is_pk and not schema.get('readOnly'):
        schema['readOnly'] = True
        if 'description' not in schema:
            schema['description'] = 'Primary Key'

    # Informational: Add default if available (handle potential type issues)
    # if col.default is not None and not col.is_pk: schema['default'] = col.default # Represent as string

    # Add description for clarity if missing
    if 'description' not in schema and schema['type'] != 'Unknown':
        schema['description'] = f"{django_field_type} field"

    return schema


def analyze_relationships_django(tables: List[TableInfo], table_map: Dict[str, TableInfo]):
     """
     Analyzes foreign keys from Django's introspection results. Updates TableInfo in-place.
     Identifies ManyToOne relationships. M2M requires join table detection logic.
     """
     logger.info("Analyzing relationships (using Django introspection data)...")
     all_table_names = set(table_map.keys())

     # --- Pass 1: Identify ManyToOne relationships based on FKs ---
     for table in tables:
        model_name = table.model_name
        relationships = [] # Store relationship definitions as dicts

        # Process FKs from relations or constraints
        fk_source = table.relations if table.relations else table.constraints
        potential_fks: Dict[str, Tuple[str, str]] = {} # {fk_col_name: (target_table, target_col)}

        # Extract FK info into a consistent format {col_name: (target_table, target_col)}
        for name, data in fk_source.items():
            target_table, target_col = None, None
            fk_cols = []
            if 'foreign_key' in data and isinstance(data.get('foreign_key'), tuple): # Constraint format
                if data.get('columns') and isinstance(data['columns'], list):
                    fk_cols = data['columns']
                    target_table, target_col = data['foreign_key'] # Assumes single target col from tuple
            elif isinstance(data, tuple) and len(data) == 2: # Relation format (key is fk_col)
                fk_cols = [name]
                target_col, target_table = data # Note order difference from constraint format

            # Only process single-column FKs for now
            if len(fk_cols) == 1 and target_table and target_col:
                potential_fks[fk_cols[0]] = (target_table, target_col)

        logger.debug(f"Potential FKs identified for {table.name}: {potential_fks}")

        # Create relationship definitions
        for fk_col_name, (target_table_name, target_col_name) in potential_fks.items():
            if target_table_name not in all_table_names:
                logger.warning(f"Skipping FK from {table.name}.{fk_col_name}: Target table '{target_table_name}' not found or excluded.")
                continue

            target_table = table_map[target_table_name]
            target_model_name = target_table.model_name # Get mapped name

            # Generate relationship field name (e.g., 'author' from 'author_id')
            rel_name_base = fk_col_name.rsplit('_id', 1)[0] if fk_col_name.endswith('_id') else fk_col_name
            rel_name_guess = clean_field_name(rel_name_base)

            # Avoid name clash with the FK field itself (if cleaning didn't change it)
            if rel_name_guess == clean_field_name(fk_col_name):
                rel_name_guess += '_rel' # Add suffix to distinguish relation field from FK field
            # Avoid clash with target model name (lowercase)
            if rel_name_guess == target_model_name.lower():
                rel_name_guess += '_rel'

            # Get null/blank status from the original FK column
            fk_col_obj = next((c for c in table.columns if c.name == fk_col_name), None)
            fk_nullable = fk_col_obj.nullable if fk_col_obj else True # Default to True if column not found
            fk_blankable = fk_nullable # Simple assumption: blank = null for FKs

            # TODO: Determine on_delete (requires specific constraint info or config)
            on_delete_action = 'models.CASCADE' # Default, needs improvement

            # ManyToOne relationship from current table to target table
            mto_rel = {
                'name': rel_name_guess,
                'type': 'many-to-one',
                'target_table': target_table_name,
                'target_model_name': target_model_name,
                # Generate a usable related_name for the reverse relation (e.g., 'book_set')
                # Use singular of target + _set or plural of current table name
                'related_name': f"{p.plural(table.name)}", # Example: book_set or orders
                'source_columns': [fk_col_name],
                'target_columns': [target_col_name], # Assumed from introspection format
                'django_field_options': {
                    'on_delete': on_delete_action,
                    'db_column': fk_col_name, # Explicitly set db_column for clarity
                    'null': fk_nullable,
                    'blank': fk_blankable,
                    # Add verbose_name, help_text later?
                }
            }
            relationships.append(mto_rel)

            # Mark the original FK column's corresponding Django field as 'handled'
            # so it's not rendered directly in models.py if the FK relation field exists
            for field_data in table.fields:
                if field_data['original_column_name'] == fk_col_name:
                    field_data['is_handled_by_relation'] = True
                    logger.debug(f"Marking field {table.name}.{field_data['name']} as handled by relation {rel_name_guess}")
                    break

        # --- TODO: Pass 2: Detect ManyToMany relationships ---
        # Heuristic: Identify join tables (tables with exactly two FKs forming the PK)
        # This requires iterating through tables again and adding M2M RelationshipInfo
        # to the *two endpoint tables*, referencing the join table via `through`.

        table.relationships = relationships


def build_intermediate_representation(schema_infos: List[TableInfo]) -> List[TableInfo]:
    """Processes raw schema info, applies mappings & conventions, extracts meta constraints/indexes."""
    logger.info("Building intermediate representation (from Django introspection results)...")
    intermediate_repr: List[TableInfo] = []
    table_map: Dict[str, TableInfo] = {info.name: info for info in schema_infos}

    # --- Pass 1: Map basic fields ---
    for table_info in schema_infos:
        table_info.model_name = to_pascal_case(table_info.name)
        logger.info(f"Mapping table '{table_info.name}' to model '{table_info.model_name}'")
        django_fields = []
        for col in table_info.columns:
            django_field_type, django_options = map_db_type_to_django(col)
            field_name = clean_field_name(col.name)
            django_fields.append({
                'name': field_name,
                'type': django_field_type,
                'options': django_options,
                'original_column_name': col.name,
                'is_pk': col.is_pk,
                'is_fk': col.is_foreign_key,
                'is_handled_by_relation': False, # Initial default
                'openapi_schema': map_db_type_to_openapi(col)
            })
        table_info.fields = django_fields
        intermediate_repr.append(table_info) # Add tables with basic fields mapped

    # --- Pass 2: Analyze Relationships (Updates 'is_handled_by_relation' flag) ---
    analyze_relationships_django(intermediate_repr, table_map)
    logger.info("Relationship analysis complete.")

    # --- Pass 3: Process Constraints/Indexes using final field info ---
    logger.info("Processing constraints and indexes for Meta...")
    for table_info in intermediate_repr: # Iterate again over the updated tables
        meta_constraints = []
        meta_indexes = []
        db_check_constraints = []
        processed_constraint_names = set()
        current_field_names_in_model = {f['name'] for f in table_info.fields if not f['is_handled_by_relation']}
        current_relation_names_in_model = {r['name'] for r in table_info.relationships}
        valid_model_field_names = current_field_names_in_model.union(current_relation_names_in_model)

        # Quick lookup: original DB column -> field dict
        col_to_field_dict_map = {f['original_column_name']: f for f in table_info.fields}

        for constraint_name, c_data in table_info.constraints.items():
            if constraint_name in processed_constraint_names: continue
            columns = c_data.get('columns', [])
            if not columns: continue

            # --- Determine correct Django field names for this constraint/index ---
            mapped_field_names_for_meta = []
            constraint_is_valid = True
            for original_col_name in columns:
                field_dict = col_to_field_dict_map.get(original_col_name)
                if not field_dict:
                    logger.warning(f"Cannot process constraint/index '{constraint_name}' on table '{table_info.name}': Original column '{original_col_name}' has no mapped field.")
                    constraint_is_valid = False; break

                if field_dict['is_handled_by_relation']:
                    # Find the corresponding relationship that handles this FK column
                    related_rel = next((rel for rel in table_info.relationships if original_col_name in rel.get('source_columns', [])), None)
                    if related_rel and related_rel['name'] in valid_model_field_names:
                        mapped_field_names_for_meta.append(related_rel['name']) # Use the relationship name (e.g., author_rel)
                    else:
                        logger.warning(f"Cannot process constraint/index '{constraint_name}' on table '{table_info.name}': Could not find valid relationship field for FK column '{original_col_name}'.")
                        constraint_is_valid = False; break
                elif field_dict['name'] in valid_model_field_names:
                     # Use the direct field name (e.g., title, status)
                    mapped_field_names_for_meta.append(field_dict['name'])
                else:
                    # This case shouldn't happen if field mapping is correct
                     logger.warning(f"Cannot process constraint/index '{constraint_name}' on table '{table_info.name}': Mapped field '{field_dict['name']}' for column '{original_col_name}' seems invalid.")
                     constraint_is_valid = False; break

            if not constraint_is_valid:
                continue # Skip this constraint/index

            # Now use 'mapped_field_names_for_meta' which contains correct Django field names
            is_unique = c_data.get('unique', False)
            is_pk = c_data.get('primary_key', False)
            is_fk = c_data.get('foreign_key', False)
            is_index = c_data.get('index', False)
            is_check = c_data.get('check', False)

            # 1. Handle Multi-Column Unique Constraints -> models.UniqueConstraint
            if is_unique and not is_pk and not is_fk and len(columns) > 1:
                meta_constraints.append({
                    'type': 'unique',
                    'fields': sorted(mapped_field_names_for_meta), # Use correct field names
                    'name': constraint_name,
                })
                processed_constraint_names.add(constraint_name)
                if is_index: processed_constraint_names.add(constraint_name + '_idx')

            # 2. Handle Indexes -> models.Index
            elif is_index and not is_pk and not is_fk:
                is_single_col_unique_field = (
                    len(mapped_field_names_for_meta) == 1 and
                    any(f['name'] == mapped_field_names_for_meta[0] and f['options'].get('unique') for f in table_info.fields)
                )
                is_multi_col_unique_constraint = (
                    is_unique and len(columns) > 1 and
                    any(mc['name'] == constraint_name for mc in meta_constraints)
                )
                if not is_single_col_unique_field and not is_multi_col_unique_constraint:
                    meta_indexes.append({
                        'fields': mapped_field_names_for_meta, # Use correct field names
                        'name': constraint_name, # Keep DB name for index object
                    })
                    processed_constraint_names.add(constraint_name)

            # 3. Note DB Check Constraints
            elif is_check:
                 db_check_constraints.append({ 'name': constraint_name, 'definition': c_data.get('definition', '?')})
                 processed_constraint_names.add(constraint_name)

        # Update the TableInfo object
        table_info.meta_constraints = meta_constraints
        table_info.meta_indexes = meta_indexes
        table_info.db_check_constraints = db_check_constraints

    logger.info("Intermediate representation processing complete.")
    return intermediate_repr
