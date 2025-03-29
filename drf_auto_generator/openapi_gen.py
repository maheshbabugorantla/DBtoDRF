import logging
import yaml
from pathlib import Path
from typing import List, Dict, Any
import inflect

# Import from the new Django introspection module
from .introspection_django import TableInfo
from .mapper import clean_field_name


logger = logging.getLogger(__name__)
p = inflect.engine()


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
        target_model_name = rel_info["target_model_name"]

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

            properties[rel_name] = {
                "type": "array",
                "items": item_schema,
                "readOnly": True,  # Reverse relations are typically read-only in list/detail views
                "description": f"Related {p.plural(target_model_name)}",
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


def generate_paths_for_table(
    table: TableInfo, config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generates OpenAPI Path Item Objects for CRUD operations for a table."""
    paths = {}
    # Use inflect for more reliable pluralization, fallback to simple 's'
    try:
        table_name_plural = p.plural(table.name)
    except Exception:
        table_name_plural = f"{table.name}s"

    model_name = table.model_name
    pk_field_info = next((f for f in table.fields if f["is_pk"]), None)

    if not pk_field_info:
        logger.warning(
            f"Table {table.name} has no primary key field identified in 'fields'. Skipping CRUD path generation."
        )
        return {}

    pk_name = pk_field_info["name"]
    pk_schema = pk_field_info.get(
        "openapi_schema", {"type": "integer"}
    )  # Get PK schema

    tag_name = model_name  # Use model name for tag
    schema_ref = f"#/components/schemas/{model_name}"
    input_schema_ref = f"#/components/schemas/{model_name}Input"
    patch_schema_ref = (
        f"#/components/schemas/{model_name}PatchInput"  # Separate schema for PATCH
    )

    # --- List and Create Path ---
    list_create_path = f"/{table_name_plural}"
    paths[list_create_path] = {
        # --- GET (List) ---
        "get": {
            "tags": [tag_name],
            "summary": f"List {p.plural(model_name)}",
            "operationId": f"list{p.plural(model_name)}",
            # TODO: Add parameters for pagination (page, page_size), filtering, ordering
            "parameters": [
                # Example pagination params (if using PageNumberPagination)
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
                # TODO: Add 'ordering', 'search' based on ViewSet filter_backends
            ],
            "responses": {
                "200": {
                    "description": f"Successfully retrieved list of {p.plural(model_name)}.",
                    "content": {
                        "application/json": {
                            # Schema should reflect pagination structure if used
                            "schema": {
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
                        }
                    },
                },
                "default": {
                    "$ref": "#/components/responses/Error"
                },  # Generic error response
            },
        },
        # --- POST (Create) ---
        "post": {
            "tags": [tag_name],
            "summary": f"Create a new {model_name}",
            "operationId": f"create{model_name}",
            "requestBody": {
                "description": f"{model_name} object to create.",
                "required": True,
                "content": {
                    "application/json": {"schema": {"$ref": input_schema_ref}},
                    "application/x-www-form-urlencoded": {
                        "schema": {"$ref": input_schema_ref}
                    },
                    "multipart/form-data": {
                        "schema": {"$ref": input_schema_ref}
                    },  # If file uploads possible
                },
            },
            "responses": {
                "201": {
                    "description": f"{model_name} created successfully.",
                    "content": {"application/json": {"schema": {"$ref": schema_ref}}},
                },
                "400": {"$ref": "#/components/responses/InvalidInput"},
                "default": {"$ref": "#/components/responses/Error"},
            },
        },
    }

    # --- Detail, Update, Partial Update, Delete Path ---
    detail_path = f"/{table_name_plural}/{{{pk_name}}}"
    paths[detail_path] = {
        # Common path parameter
        "parameters": [
            {
                "name": pk_name,
                "in": "path",
                "required": True,
                "description": f"The primary key of the {model_name}.",
                "schema": pk_schema,  # Use the specific schema determined for the PK
            }
        ],
        # --- GET (Retrieve) ---
        "get": {
            "tags": [tag_name],
            "summary": f"Retrieve a specific {model_name}",
            "operationId": f"retrieve{model_name}",
            "responses": {
                "200": {
                    "description": f"Details of {model_name}.",
                    "content": {"application/json": {"schema": {"$ref": schema_ref}}},
                },
                "404": {"$ref": "#/components/responses/NotFound"},
                "default": {"$ref": "#/components/responses/Error"},
            },
        },
        # --- PUT (Update) ---
        "put": {
            "tags": [tag_name],
            "summary": f"Update a {model_name}",
            "operationId": f"update{model_name}",
            "requestBody": {
                "description": f"{model_name} object to update.",
                "required": True,
                "content": {
                    "application/json": {"schema": {"$ref": input_schema_ref}},
                    "application/x-www-form-urlencoded": {
                        "schema": {"$ref": input_schema_ref}
                    },
                    "multipart/form-data": {"schema": {"$ref": input_schema_ref}},
                },
            },
            "responses": {
                "200": {
                    "description": f"{model_name} updated successfully.",
                    "content": {"application/json": {"schema": {"$ref": schema_ref}}},
                },
                "400": {"$ref": "#/components/responses/InvalidInput"},
                "404": {"$ref": "#/components/responses/NotFound"},
                "default": {"$ref": "#/components/responses/Error"},
            },
        },
        # --- PATCH (Partial Update) ---
        "patch": {
            "tags": [tag_name],
            "summary": f"Partially update a {model_name}",
            "operationId": f"partialUpdate{model_name}",
            "requestBody": {
                "description": f"Fields to partially update for a {model_name}. All fields are optional.",
                "required": True,  # Body required, but fields inside are optional
                "content": {
                    # Use a specific schema for PATCH where fields are not required
                    "application/json": {"schema": {"$ref": patch_schema_ref}}
                },
            },
            "responses": {
                "200": {
                    "description": f"{model_name} partially updated successfully.",
                    "content": {"application/json": {"schema": {"$ref": schema_ref}}},
                },
                "400": {"$ref": "#/components/responses/InvalidInput"},
                "404": {"$ref": "#/components/responses/NotFound"},
                "default": {"$ref": "#/components/responses/Error"},
            },
        },
        # --- DELETE ---
        "delete": {
            "tags": [tag_name],
            "summary": f"Delete a {model_name}",
            "operationId": f"delete{model_name}",
            "responses": {
                "204": {
                    "description": f"{model_name} deleted successfully."
                },  # No content
                "404": {"$ref": "#/components/responses/NotFound"},
                "default": {"$ref": "#/components/responses/Error"},
            },
        },
    }

    # TODO: Add nested paths if relation_style is 'nested' based on RelationshipInfo

    return paths


def generate_openapi_spec(
    ir_list: List[TableInfo], config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generates the complete OpenAPI specification dictionary."""
    logger.info("Generating OpenAPI specification...")
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
                # Optionally add 'code', 'errors' (for validation field errors)
                # 'errors': { 'type': 'object', 'additionalProperties': {'type': 'array', 'items': {'type': 'string'}}}
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

        # Generate CRUD paths for the table
        table_paths = generate_paths_for_table(table, config)
        all_paths.update(table_paths)

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
            # TODO: Add securitySchemes if implementing auth (e.g., bearer token, basic auth)
            # 'securitySchemes': {
            #     'ApiKeyAuth': {'type': 'apiKey', 'in': 'header', 'name': 'Authorization'},
            #     'BasicAuth': {'type': 'http', 'scheme': 'basic'},
            # }
        },
        # TODO: Add global security requirement if applicable
        # 'security': [ {'ApiKeyAuth': []} ]
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
