import logging
import yaml
from pathlib import Path
from typing import List, Dict, Any
import inflect

# Import from the new Django introspection module
from drf_auto_generator.domain.models import TableInfo
from drf_auto_generator.mapper import clean_field_name


logger = logging.getLogger(__name__)
p = inflect.engine()


def _get_target_model_name(rel_info: Dict[str, Any]) -> str:
    """
    Safely extract target_model_name from relationship info.
    If target_model_name is missing, derive it from target_table.
    """
    if "target_model_name" in rel_info:
        return rel_info["target_model_name"]

    # Fallback: derive model name from target_table
    target_table = rel_info.get("target_table", "UnknownTable")
    # Convert snake_case to PascalCase
    words = target_table.split('_')
    return ''.join(word.capitalize() for word in words)


def generate_openapi_schema_object(
    table: TableInfo, config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generates an OpenAPI Schema Object for a table's model."""
    properties = {}
    required = []
    relation_style = config.get("relation_style", "pk")

    # Add regular fields derived from columns
    for field_info in table.fields:
        # Only include fields that are NOT solely represented by a separate relation field
        # Exception: Always include the actual PK field even if it's also an FK.
        if not field_info["is_handled_by_relation"] or field_info["is_pk"]:
            field_name = field_info["name"]
            openapi_schema = field_info.get(
                "openapi_schema", {"type": "string"}
            )  # Get stored schema
            properties[field_name] = openapi_schema

            # Determine required fields for the main schema (output)
            # Generally, non-nullable fields without defaults that aren't PKs.
            # We use the schema's nullable flag for consistency.
            original_col = next(
                (
                    c
                    for c in table.columns
                    if c.name == field_info["original_column_name"]
                ),
                None,
            )
            if (
                not openapi_schema.get("nullable", True)
                and not openapi_schema.get("readOnly", False)
                and (not original_col or original_col.default is None)
            ):
                required.append(field_name)

    # Add relationship fields based on configured style
    for rel_info in table.relationships:
        rel_name = rel_info["name"]
        rel_type = rel_info["type"]  # 'many-to-one', 'one-to-many', 'many-to-many'
        target_model_name = _get_target_model_name(rel_info)

        if rel_type == "many-to-one":
            if relation_style == "pk":
                # PK style implies the FK field (e.g., author_id) is already included above.
                # We might *also* want a read-only link or nested object optionally.
                pass  # FK field handles it
            elif relation_style == "link":
                properties[rel_name] = {
                    "type": "string",
                    "format": "uri",
                    "description": f"Link to related {target_model_name}",
                    "readOnly": True,  # Typically links are read-only representations
                }
            elif relation_style == "nested":
                properties[rel_name] = {
                    "$ref": f"#/components/schemas/{target_model_name}",
                    "readOnly": True,  # Default to read-only nesting for simplicity
                    "nullable": rel_info["django_field_options"].get(
                        "null", True
                    ),  # Reflect nullability
                }
        elif rel_type in ("one-to-many", "many-to-many"):
            # These are represented as arrays of related items
            item_schema = {}
            if relation_style == "pk":
                item_schema = {
                    "type": "integer"
                }  # Assuming integer PKs for related items
                # Try to get actual PK type of target model if possible? Complex.
            elif relation_style == "link":
                item_schema = {"type": "string", "format": "uri"}
            elif relation_style == "nested":
                item_schema = {"$ref": f"#/components/schemas/{target_model_name}"}

            # Safe pluralization for description
            try:
                plural_name = p.plural(target_model_name)
            except Exception:
                plural_name = f"{target_model_name}s"

            properties[rel_name] = {
                "type": "array",
                "items": item_schema,
                "readOnly": True,  # Reverse relations are typically read-only in list/detail views
                "description": f"Related {plural_name}",
            }

    return {
        "type": "object",
        "properties": properties,
        # Required fields only make sense for input schemas usually.
        # For output schemas, all properties defined are potentially present.
        # 'required': sorted(list(set(required))),
    }


def generate_openapi_input_schema(
    table: TableInfo, config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generates an OpenAPI Schema Object for input (POST/PUT/PATCH). Excludes readOnly fields."""
    output_schema = generate_openapi_schema_object(table, config)
    input_properties = {}
    input_required = []

    for name, prop_schema in output_schema.get("properties", {}).items():
        if not prop_schema.get("readOnly", False):
            input_properties[name] = prop_schema
            # If it was required in the base schema (non-null, no default, not PK)
            # then it's likely required for POST/PUT. PATCH is different (all optional).
            # Let's mark non-nullable, non-default fields as required for input.
            original_field = next((f for f in table.fields if f["name"] == name), None)
            if original_field:
                original_col = next(
                    (
                        c
                        for c in table.columns
                        if c.name == original_field["original_column_name"]
                    ),
                    None,
                )
                if (
                    original_col
                    and not original_col.nullable
                    and original_col.default is None
                ):
                    input_required.append(name)

    # Refine required list based on relationship style for MTO
    relation_style = config.get("relation_style", "pk")
    for rel_info in table.relationships:
        rel_name = rel_info["name"]
        if rel_info["type"] == "many-to-one":
            fk_field_name = clean_field_name(
                rel_info["source_columns"][0]
            )  # Original FK field name
            is_fk_nullable = rel_info["django_field_options"].get("null", True)

            if relation_style == "pk":
                # If FK field itself is required, mark it.
                if not is_fk_nullable and fk_field_name in input_properties:
                    if fk_field_name not in input_required:
                        input_required.append(fk_field_name)
                # The relation name (e.g., 'author') shouldn't be in input properties for 'pk' style
                input_properties.pop(rel_name, None)
            elif relation_style == "link":
                # Links are usually read-only, remove from input
                input_properties.pop(rel_name, None)
                # FK field might still be needed if links aren't used for input? Assume PK style input.
                if not is_fk_nullable and fk_field_name in input_properties:
                    if fk_field_name not in input_required:
                        input_required.append(fk_field_name)

            elif relation_style == "nested":
                # Nested input is complex. For now, assume we still provide the FK ID.
                input_properties.pop(
                    rel_name, None
                )  # Remove nested object ref from input
                if not is_fk_nullable and fk_field_name in input_properties:
                    if fk_field_name not in input_required:
                        input_required.append(fk_field_name)

    return {
        "type": "object",
        "properties": input_properties,
        "required": sorted(list(set(input_required))),
    }


def _filter_db_fields(table: TableInfo, field_names: List[str]) -> List[str]:
    """Filters field names to only include actual database columns."""
    actual_db_fields = []
    for field_name in field_names:
        field = next((f for f in table.fields if f["name"] == field_name), None)
        if (field and not field.get("is_handled_by_relation", False) and
            not field_name.endswith("_rel")):
            actual_db_fields.append(field_name)
    return actual_db_fields


def _create_field_parameter(field_name: str, field_schema: Dict[str, Any],
                           param_type: str = "query", required: bool = True) -> Dict[str, Any]:
    """Creates a parameter for field filtering."""
    return {
        "name": field_name if param_type == "query" else "value",
        "in": param_type,
        "required": required,
        "description": f"The {field_name} {'value to look up' if param_type == 'path' else 'to filter by'}",
        "schema": field_schema
    }


def _generate_unique_field_endpoints(table: TableInfo, model_name: str,
                                   table_name_plural: str, tag_name: str,
                                   schema_ref: str) -> Dict[str, Any]:
    """Generates endpoints for unique field lookups."""
    paths = {}

    for field in table.fields:
        field_name = field["name"]

        # Skip primary key fields, relationship fields, and non-unique fields
        if (field["is_pk"] or
            field.get("is_handled_by_relation", False) or
            field_name.endswith("_rel") or
            not field.get("options", {}).get("unique", False)):
            continue

        field_path = f"/{table_name_plural}/by_{field_name}/{{value}}"
        field_schema = field.get("openapi_schema", {"type": "string"})

        paths[field_path] = {
            "parameters": [_create_field_parameter(field_name, field_schema, "path")],
            "get": {
                "tags": [tag_name],
                "summary": f"Retrieve {model_name} by {field_name}",
                "operationId": f"retrieve{model_name}By{field_name.capitalize()}",
                "responses": {
                    "200": {
                        "description": f"Details of {model_name} matching the specified {field_name}",
                        "content": {"application/json": {"schema": {"$ref": schema_ref}}}
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "default": {"$ref": "#/components/responses/Error"}
                }
            }
        }

        logger.debug(f"Added endpoint for unique field lookup: {field_path}")

    return paths


def _generate_composite_constraint_endpoints(table: TableInfo, model_name: str,
                                           table_name_plural: str, tag_name: str,
                                           schema_ref: str) -> Dict[str, Any]:
    """Generates endpoints for composite unique constraints."""
    paths = {}

    for constraint in table.meta_constraints:
        if constraint["type"] != "unique" or len(constraint["fields"]) <= 1:
            continue

        actual_db_fields = _filter_db_fields(table, constraint["fields"])
        if not actual_db_fields:
            continue

        endpoint_name = "_and_".join(actual_db_fields)
        endpoint_path = f"/{table_name_plural}/by_{endpoint_name}"

        parameters = []
        for field_name in actual_db_fields:
            field = next((f for f in table.fields if f["name"] == field_name), None)
            if field:
                field_schema = field.get("openapi_schema", {"type": "string"})
                parameters.append(_create_field_parameter(field_name, field_schema, "query"))

        if parameters:
            paths[endpoint_path] = {
                "parameters": parameters,
                "get": {
                    "tags": [tag_name],
                    "summary": f"Retrieve {model_name} by composite unique constraint",
                    "operationId": f"retrieve{model_name}By{endpoint_name.capitalize().replace('_', '')}",
                    "responses": {
                        "200": {
                            "description": f"Details of {model_name} matching the compound constraint",
                            "content": {"application/json": {"schema": {"$ref": schema_ref}}}
                        },
                        "404": {"$ref": "#/components/responses/NotFound"},
                        "default": {"$ref": "#/components/responses/Error"}
                    }
                }
            }

            logger.debug(f"Added endpoint for compound unique constraint: {endpoint_path}")

    return paths


def _generate_index_endpoints(table: TableInfo, model_name: str,
                            table_name_plural: str, tag_name: str,
                            schema_ref: str) -> Dict[str, Any]:
    """Generates endpoints for index-based filtering."""
    paths = {}

    # Safe pluralization helper
    def safe_plural(word):
        try:
            return p.plural(word)
        except Exception:
            return f"{word}s"

    for index in table.meta_indexes:
        index_fields = index["fields"]
        if not index_fields:
            continue

        actual_db_index_fields = _filter_db_fields(table, index_fields)
        if not actual_db_index_fields:
            continue

        if len(actual_db_index_fields) == 1:
            field_name = actual_db_index_fields[0]
            field = next((f for f in table.fields if f["name"] == field_name), None)

            if not field or field.get("options", {}).get("unique", False):
                continue

            field_path = f"/{table_name_plural}/filter_by_{field_name}/{{value}}"
            field_schema = field.get("openapi_schema", {"type": "string"})

            paths[field_path] = {
                "parameters": [_create_field_parameter(field_name, field_schema, "path")],
                "get": {
                    "tags": [tag_name],
                    "summary": f"List {safe_plural(model_name)} filtered by {field_name}",
                    "operationId": f"list{safe_plural(model_name)}By{field_name.capitalize()}",
                    "responses": {
                        "200": {
                            "description": f"List of {safe_plural(model_name)} matching the specified {field_name}",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": schema_ref}
                                    }
                                }
                            }
                        },
                        "default": {"$ref": "#/components/responses/Error"}
                    }
                }
            }

            logger.debug(f"Added endpoint for non-unique index field lookup: {field_path}")
        else:
            endpoint_name = "_and_".join(actual_db_index_fields)
            endpoint_path = f"/{table_name_plural}/filter_by_{endpoint_name}"

            parameters = []
            for field_name in actual_db_index_fields:
                field = next((f for f in table.fields if f["name"] == field_name), None)
                if field:
                    field_schema = field.get("openapi_schema", {"type": "string"})
                    parameters.append(_create_field_parameter(field_name, field_schema, "query", False))

            if parameters:
                paths[endpoint_path] = {
                    "parameters": parameters,
                    "get": {
                        "tags": [tag_name],
                        "summary": f"List {safe_plural(model_name)} filtered by index fields",
                        "operationId": f"list{safe_plural(model_name)}By{endpoint_name.capitalize().replace('_', '')}",
                        "responses": {
                            "200": {
                                "description": f"List of {safe_plural(model_name)} matching the filter criteria",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {"$ref": schema_ref}
                                        }
                                    }
                                }
                            },
                            "default": {"$ref": "#/components/responses/Error"}
                        }
                    }
                }

                logger.debug(f"Added endpoint for multi-field index: {endpoint_path}")

    return paths


def generate_endpoints_on_table_indexes_and_constraints(table: TableInfo, config: Dict[str, Any]) -> Dict[str, Any]:
    """Generates OpenAPI Path Item Objects for indexes and unique constraints."""
    paths = {}
    model_name = table.model_name
    schema_ref = f"#/components/schemas/{model_name}"
    tag_name = model_name

    try:
        table_name_plural = p.plural(table.name)
    except Exception:
        table_name_plural = f"{table.name}s"

    logger.debug(f"Analyzing table {table.name} for constraint endpoints:")
    logger.debug(f"  Fields: {[f['name'] for f in table.fields]}")
    logger.debug(f"  Meta constraints: {table.meta_constraints}")
    logger.debug(f"  Meta indexes: {table.meta_indexes}")

    # Generate different types of endpoints
    unique_paths = _generate_unique_field_endpoints(table, model_name, table_name_plural, tag_name, schema_ref)
    paths.update(unique_paths)

    constraint_paths = _generate_composite_constraint_endpoints(table, model_name, table_name_plural, tag_name, schema_ref)
    paths.update(constraint_paths)

    index_paths = _generate_index_endpoints(table, model_name, table_name_plural, tag_name, schema_ref)
    paths.update(index_paths)

    logger.debug(f"Generated {len(paths)} constraint-based endpoints for table {table.name}")
    return paths


def generate_m2m_endpoints(
    table: TableInfo, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generates OpenAPI Path Item Objects for Many-to-Many relationship operations.
    These allow adding/removing items from M2M relationships.
    """
    paths = {}
    model_name = table.model_name
    schema_ref = f"#/components/schemas/{model_name}"
    tag_name = model_name

    # Use inflect for pluralization
    try:
        table_name_plural = p.plural(table.name)
    except Exception:
        table_name_plural = f"{table.name}s"

    # Find M2M relationships in this table
    m2m_relationships = [r for r in table.relationships if r["type"] == "many-to-many"]

    for relation in m2m_relationships:
        rel_name = relation["name"]
        target_model = _get_target_model_name(relation)

        # Create endpoints for managing the M2M relationship
        # 1. List related items
        list_path = f"/{table_name_plural}/{{{table.model_name.lower()}_id}}/{rel_name}"

        # Find PK field info
        pk_field_info = next((f for f in table.fields if f["is_pk"]), None)
        if not pk_field_info:
            continue  # Skip if no PK field found

        pk_schema = pk_field_info.get("openapi_schema", {"type": "integer"})

        paths[list_path] = {
            "parameters": [
                {
                    "name": f"{table.model_name.lower()}_id",
                    "in": "path",
                    "required": True,
                    "description": f"The ID of the {model_name}",
                    "schema": pk_schema
                }
            ],
            "get": {
                "tags": [tag_name],
                "summary": f"List related {rel_name} for a {model_name}",
                "operationId": f"list{model_name}{rel_name.capitalize()}",
                "responses": {
                    "200": {
                        "description": f"List of {rel_name} related to the {model_name}",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "$ref": f"#/components/schemas/{target_model}"
                                    }
                                }
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "default": {"$ref": "#/components/responses/Error"}
                }
            }
        }

        # 2. Add a related item to the M2M relationship
        add_path = f"/{table_name_plural}/{{{table.model_name.lower()}_id}}/{rel_name}/{{{target_model.lower()}_id}}"

        paths[add_path] = {
            "parameters": [
                {
                    "name": f"{table.model_name.lower()}_id",
                    "in": "path",
                    "required": True,
                    "description": f"The ID of the {model_name}",
                    "schema": pk_schema
                },
                {
                    "name": f"{target_model.lower()}_id",
                    "in": "path",
                    "required": True,
                    "description": f"The ID of the {target_model} to add",
                    "schema": {"type": "integer"}
                }
            ],
            "post": {
                "tags": [tag_name],
                "summary": f"Add a {target_model} to the {rel_name} of a {model_name}",
                "operationId": f"add{target_model}To{model_name}{rel_name.capitalize()}",
                "responses": {
                    "201": {
                        "description": f"{target_model} added to {rel_name} successfully."
                    },
                    "400": {"$ref": "#/components/responses/InvalidInput"},
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "default": {"$ref": "#/components/responses/Error"}
                }
            },
            "delete": {
                "tags": [tag_name],
                "summary": f"Remove a {target_model} from the {rel_name} of a {model_name}",
                "operationId": f"remove{target_model}From{model_name}{rel_name.capitalize()}",
                "responses": {
                    "204": {
                        "description": f"{target_model} removed from {rel_name} successfully."
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "default": {"$ref": "#/components/responses/Error"}
                }
            }
        }

        # 3. If the M2M relationship has metadata fields, add an endpoint to update them
        if relation.get("has_relationship_attributes", False) and relation.get("metadata_fields"):
            metadata_path = f"/{table_name_plural}/{{{table.model_name.lower()}_id}}/{rel_name}/{{{target_model.lower()}_id}}/metadata"

            # Build a schema for the metadata fields
            metadata_properties = {}
            for field in relation.get("metadata_fields", []):
                field_name = field["name"]
                field_schema = field.get("openapi_schema", {"type": "string"})
                metadata_properties[field_name] = field_schema

            paths[metadata_path] = {
                "parameters": [
                    {
                        "name": f"{table.model_name.lower()}_id",
                        "in": "path",
                        "required": True,
                        "description": f"The ID of the {model_name}",
                        "schema": pk_schema
                    },
                    {
                        "name": f"{target_model.lower()}_id",
                        "in": "path",
                        "required": True,
                        "description": f"The ID of the {target_model}",
                        "schema": {"type": "integer"}
                    }
                ],
                "get": {
                    "tags": [tag_name],
                    "summary": f"Get metadata for the relationship between {model_name} and {target_model}",
                    "operationId": f"get{model_name}{target_model}Metadata",
                    "responses": {
                        "200": {
                            "description": f"Metadata for the relationship",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": metadata_properties
                                    }
                                }
                            }
                        },
                        "404": {"$ref": "#/components/responses/NotFound"},
                        "default": {"$ref": "#/components/responses/Error"}
                    }
                },
                "patch": {
                    "tags": [tag_name],
                    "summary": f"Update metadata for the relationship between {model_name} and {target_model}",
                    "operationId": f"update{model_name}{target_model}Metadata",
                    "requestBody": {
                        "description": "Metadata fields to update",
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": metadata_properties
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Metadata updated successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": metadata_properties
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/InvalidInput"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                        "default": {"$ref": "#/components/responses/Error"}
                    }
                }
            }

    return paths


def _create_path_parameter(name: str, description: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a standardized path parameter."""
    return {
        "name": name,
        "in": "path",
        "required": True,
        "description": description,
        "schema": schema
    }


def _create_standard_responses(model_name: str, schema_ref: str) -> Dict[str, Any]:
    """Creates standard CRUD response definitions."""
    return {
        "retrieve": {
            "200": {
                "description": f"Details of {model_name}.",
                "content": {"application/json": {"schema": {"$ref": schema_ref}}},
            },
            "404": {"$ref": "#/components/responses/NotFound"},
            "default": {"$ref": "#/components/responses/Error"},
        },
        "create": {
            "201": {
                "description": f"{model_name} created successfully.",
                "content": {"application/json": {"schema": {"$ref": schema_ref}}},
            },
            "400": {"$ref": "#/components/responses/InvalidInput"},
            "default": {"$ref": "#/components/responses/Error"},
        },
        "update": {
            "200": {
                "description": f"{model_name} updated successfully.",
                "content": {"application/json": {"schema": {"$ref": schema_ref}}},
            },
            "400": {"$ref": "#/components/responses/InvalidInput"},
            "404": {"$ref": "#/components/responses/NotFound"},
            "default": {"$ref": "#/components/responses/Error"},
        },
        "delete": {
            "204": {"description": f"{model_name} deleted successfully."},
            "404": {"$ref": "#/components/responses/NotFound"},
            "default": {"$ref": "#/components/responses/Error"},
        }
    }


def _create_pagination_schema(schema_ref: str, model_name: str) -> Dict[str, Any]:
    """Creates pagination response schema."""
    return {
        "type": "object",
        "properties": {
            "count": {
                "type": "integer",
                "description": "Total number of items.",
            },
            "next": {
                "type": "string",
                "format": "uri",
                "nullable": True,
                "description": "URL to the next page.",
            },
            "previous": {
                "type": "string",
                "format": "uri",
                "nullable": True,
                "description": "URL to the previous page.",
            },
            "results": {
                "type": "array",
                "items": {"$ref": schema_ref},
            },
        },
    }


def _build_query_parameters(table: TableInfo) -> List[Dict[str, Any]]:
    """Builds query parameters for list endpoint."""
    query_parameters = [
        {
            "name": "page",
            "in": "query",
            "required": False,
            "schema": {"type": "integer", "default": 1},
            "description": "Page number",
        },
        {
            "name": "page_size",
            "in": "query",
            "required": False,
            "schema": {"type": "integer"},
            "description": "Number of results per page",
        },
        {
            "name": "ordering",
            "in": "query",
            "required": False,
            "schema": {"type": "string"},
            "description": "Field to order results by. Prefix with '-' for descending order.",
        },
        {
            "name": "search",
            "in": "query",
            "required": False,
            "schema": {"type": "string"},
            "description": "Search term to filter results",
        }
    ]

    # Add filtering parameters for foreign key relationships
    for rel in table.relationships:
        if rel["type"] == "many-to-one":
            rel_name = rel["name"]
            query_parameters.append({
                "name": rel_name,
                "in": "query",
                "required": False,
                "schema": {"type": "integer"},
                "description": f"Filter by {rel_name} ID",
            })

    # Add filtering parameters for indexed fields
    for index in table.meta_indexes:
        index_fields = index.get("fields", [])
        for field_name in index_fields:
            if any(param["name"] == field_name for param in query_parameters):
                continue

            field_info = next((f for f in table.fields if f.get("name") == field_name), None)
            if field_info and not field_info.get("is_pk", False):
                field_schema = field_info.get("openapi_schema", {"type": "string"})
                param_schema = {"type": field_schema.get("type", "string")}

                query_parameters.append({
                    "name": field_name,
                    "in": "query",
                    "required": False,
                    "schema": param_schema,
                    "description": f"Filter by {field_name}",
                })

    # Add unique field filters
    for field in table.fields:
        field_name = field.get("name")
        if (field.get("options", {}).get("unique", False) and
            not field.get("is_pk", False) and
            not any(param["name"] == field_name for param in query_parameters)):

            field_schema = field.get("openapi_schema", {"type": "string"})
            param_schema = {"type": field_schema.get("type", "string")}

            query_parameters.append({
                "name": field_name,
                "in": "query",
                "required": False,
                "schema": param_schema,
                "description": f"Filter by {field_name} (exact match)",
            })

    return query_parameters


def _generate_list_endpoint(table: TableInfo, model_name: str, table_name_plural: str,
                          tag_name: str, schema_ref: str) -> Dict[str, Any]:
    """Generates the list (GET) endpoint."""
    query_parameters = _build_query_parameters(table)

    # Safe pluralization helper
    def safe_plural(word):
        try:
            return p.plural(word)
        except Exception:
            return f"{word}s"

    return {
        "tags": [tag_name],
        "summary": f"List {safe_plural(model_name)}",
        "operationId": f"list{safe_plural(model_name)}",
        "parameters": query_parameters,
        "responses": {
            "200": {
                "description": f"Successfully retrieved list of {safe_plural(model_name)}.",
                "content": {
                    "application/json": {
                        "schema": _create_pagination_schema(schema_ref, model_name)
                    }
                },
            },
            "default": {"$ref": "#/components/responses/Error"},
        },
    }


def _generate_create_endpoint(model_name: str, tag_name: str, input_schema_ref: str) -> Dict[str, Any]:
    """Generates the create (POST) endpoint."""
    responses = _create_standard_responses(model_name, f"#/components/schemas/{model_name}")

    return {
        "tags": [tag_name],
        "summary": f"Create a new {model_name}",
        "operationId": f"create{model_name}",
        "requestBody": {
            "description": f"{model_name} object to create.",
            "required": True,
            "content": {
                "application/json": {"schema": {"$ref": input_schema_ref}},
                "application/x-www-form-urlencoded": {"schema": {"$ref": input_schema_ref}},
                "multipart/form-data": {"schema": {"$ref": input_schema_ref}},
            },
        },
        "responses": responses["create"],
    }


def _generate_detail_endpoint(model_name: str, tag_name: str, schema_ref: str) -> Dict[str, Any]:
    """Generates the detail (GET) endpoint."""
    responses = _create_standard_responses(model_name, schema_ref)

    return {
        "tags": [tag_name],
        "summary": f"Retrieve a specific {model_name}",
        "operationId": f"retrieve{model_name}",
        "responses": responses["retrieve"],
    }


def _generate_update_endpoint(model_name: str, tag_name: str, input_schema_ref: str) -> Dict[str, Any]:
    """Generates the update (PUT) endpoint."""
    responses = _create_standard_responses(model_name, f"#/components/schemas/{model_name}")

    return {
        "tags": [tag_name],
        "summary": f"Update a {model_name}",
        "operationId": f"update{model_name}",
        "requestBody": {
            "description": f"{model_name} object to update.",
            "required": True,
            "content": {
                "application/json": {"schema": {"$ref": input_schema_ref}},
                "application/x-www-form-urlencoded": {"schema": {"$ref": input_schema_ref}},
                "multipart/form-data": {"schema": {"$ref": input_schema_ref}},
            },
        },
        "responses": responses["update"],
    }


def _generate_patch_endpoint(model_name: str, tag_name: str, patch_schema_ref: str) -> Dict[str, Any]:
    """Generates the partial update (PATCH) endpoint."""
    responses = _create_standard_responses(model_name, f"#/components/schemas/{model_name}")

    return {
        "tags": [tag_name],
        "summary": f"Partially update a {model_name}",
        "operationId": f"partialUpdate{model_name}",
        "requestBody": {
            "description": f"Fields to partially update for a {model_name}. All fields are optional.",
            "required": True,
            "content": {
                "application/json": {"schema": {"$ref": patch_schema_ref}}
            },
        },
        "responses": responses["update"],
    }


def _generate_delete_endpoint(model_name: str, tag_name: str) -> Dict[str, Any]:
    """Generates the delete (DELETE) endpoint."""
    responses = _create_standard_responses(model_name, "")

    return {
        "tags": [tag_name],
        "summary": f"Delete a {model_name}",
        "operationId": f"delete{model_name}",
        "responses": responses["delete"],
    }


def generate_paths_for_table(table: TableInfo, config: Dict[str, Any]) -> Dict[str, Any]:
    """Generates OpenAPI Path Item Objects for CRUD operations for a table."""
    paths = {}

    try:
        table_name_plural = p.plural(table.name)
    except Exception:
        table_name_plural = f"{table.name}s"

    model_name = table.model_name
    pk_field_info = next((f for f in table.fields if f["is_pk"]), None)

    if table.is_m2m_through_table:
        logger.debug(f"Skipping path generation for M2M through table {table.name}")
        return {}

    if not pk_field_info:
        logger.warning(
            f"Table {table.name} has no primary key field identified in 'fields'. Skipping CRUD path generation."
        )
        return {}

    pk_schema = pk_field_info.get("openapi_schema", {"type": "integer"})
    tag_name = model_name
    schema_ref = f"#/components/schemas/{model_name}"
    input_schema_ref = f"#/components/schemas/{model_name}Input"
    patch_schema_ref = f"#/components/schemas/{model_name}PatchInput"

    # List and Create Path
    list_create_path = f"/{table_name_plural}"
    paths[list_create_path] = {
        "get": _generate_list_endpoint(table, model_name, table_name_plural, tag_name, schema_ref),
        "post": _generate_create_endpoint(model_name, tag_name, input_schema_ref),
    }

    # Detail Path
    detail_path = f"/{table_name_plural}/{{id}}"
    paths[detail_path] = {
        "parameters": [_create_path_parameter("id", f"The primary key of the {model_name}.", pk_schema)],
        "get": _generate_detail_endpoint(model_name, tag_name, schema_ref),
        "put": _generate_update_endpoint(model_name, tag_name, input_schema_ref),
        "patch": _generate_patch_endpoint(model_name, tag_name, patch_schema_ref),
        "delete": _generate_delete_endpoint(model_name, tag_name),
    }

    # Add constraint-based endpoints if enabled
    if config.get("enable_constraint_endpoints", False):
        constraint_paths = generate_endpoints_on_table_indexes_and_constraints(table, config)
        paths.update(constraint_paths)

    # Add M2M endpoints if enabled
    if config.get("enable_m2m_endpoints", False):
        m2m_paths = generate_m2m_endpoints(table, config)
        paths.update(m2m_paths)

    return paths


def generate_openapi_spec(
    ir_list: List[TableInfo], config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generates the complete OpenAPI specification dictionary."""
    logger.info("Generating OpenAPI specification...")

    if not ir_list:
        logger.warning("No tables provided for OpenAPI spec generation")
        return {}

    schemas = {}
    all_paths = {}
    all_tags = set()

    # Define common responses and error schema first
    error_schema_detail = {
        "ErrorDetail": {
            "type": "object",
            "properties": {
                "detail": {
                    "type": "string",
                    "description": "A human-readable error message.",
                },
                "code": {
                    "type": "string",
                    "description": "Machine-readable error code.",
                    "nullable": True
                },
                "errors": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "description": "Field-specific validation errors.",
                    "nullable": True
                }
            },
            "required": ["detail"],
        }
    }
    common_responses = {
        "NotFound": {
            "description": "The requested resource was not found.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorDetail"}
                }
            },
        },
        "InvalidInput": {
            "description": "Invalid input provided (e.g., validation error).",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorDetail"}
                }
            },  # Use ErrorDetail or a more specific validation error schema
        },
        "Error": {
            "description": "An unexpected server error occurred.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorDetail"}
                }
            },
        },
        "Unauthorized": {
            "description": "Authentication credentials were not provided or were invalid.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorDetail"}
                }
            },
        },
        "Forbidden": {
            "description": "Permission denied to perform this action.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorDetail"}
                }
            },
        },
    }

    # Generate schemas and paths for each table
    for table in ir_list:
        try:
            model_name = table.model_name
            all_tags.add(model_name)  # Add model name as a tag

            # Generate main output schema
            schema_obj = generate_openapi_schema_object(table, config)
            schemas[model_name] = schema_obj

            # Generate input schema (for POST/PUT)
            input_schema_obj = generate_openapi_input_schema(table, config)
            schemas[f"{model_name}Input"] = input_schema_obj

            # Generate PATCH input schema (all fields optional)
            patch_schema_obj = input_schema_obj.copy()  # Start from Input schema
            patch_schema_obj.pop("required", None)  # Remove 'required' list for PATCH
            schemas[f"{model_name}PatchInput"] = patch_schema_obj

            # Generate paths for the table
            table_paths = generate_paths_for_table(table, config)
            all_paths.update(table_paths)

        except Exception as e:
            logger.error(f"Error generating OpenAPI spec for table {table.name}: {e}")
            continue

    # Assemble the complete spec
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": config.get("openapi_title", "API"),
            "version": config.get("openapi_version", "1.0.0"),
            "description": config.get("openapi_description", ""),
            # Add contact, license later if needed
        },
        "servers": [
            # Use server URL from config, default to relative path
            {"url": config.get("openapi_server_url", "/"), "description": "API Server"}
        ],
        "tags": [
            {"name": tag, "description": f"Operations related to {tag}s"}
            for tag in sorted(list(all_tags))
        ],
        "paths": all_paths,
        "components": {
            "schemas": {
                **schemas,
                **error_schema_detail,
            },  # Combine model schemas and error schema
            "responses": common_responses,
            # Security schemes for authentication
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Authorization",
                    "description": "API key authentication"
                },
                "BasicAuth": {
                    "type": "http",
                    "scheme": "basic",
                    "description": "Basic HTTP authentication"
                },
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT Bearer token authentication"
                }
            } if config.get("enable_authentication", False) else {}
        },
        # Global security requirements
        "security": [
            {config.get("auth_scheme", "BearerAuth"): []}
        ] if config.get("enable_authentication", False) else []
    }
    logger.info("OpenAPI specification dictionary generated.")
    return spec


def save_openapi_spec(
    spec_dict: Dict[str, Any], output_dir: str, filename: str = "openapi.yaml"
):
    """Saves the OpenAPI spec dictionary to a YAML file in the output directory."""
    output_path = Path(output_dir) / filename
    # Ensure the output directory exists (important if running first time)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            # Use safe_dump, sort_keys=False to preserve order, allow_unicode for non-ASCII
            yaml.safe_dump(spec_dict, f, sort_keys=False, allow_unicode=True)
        logger.info(f"OpenAPI specification saved to {output_path}")
    except Exception as e:
        logger.error(f"Failed to save OpenAPI specification to {output_path}: {e}")
