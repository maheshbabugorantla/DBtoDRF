#!/usr/bin/env python
"""
End-to-end test using the Pagila database with the new CodeGen V2 system.

This script:
1. Connects to the Pagila database
2. Introspects the schema
3. Generates Django and MCP code using CodeGen V2
4. Validates the generated code
"""

import os
import sys
import logging
import shutil
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

def setup_django():
    """Configure Django settings for database introspection."""
    from drf_auto_generator.introspection_django import setup_django as _setup_django

    databases = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'pagila',
            'USER': 'postgres',
            'PASSWORD': '',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }
    _setup_django(databases, secret_key='test-secret-key')


def introspect_pagila():
    """Introspect the Pagila database schema."""
    from drf_auto_generator.introspection_django import introspect_schema_django

    logger.info("Introspecting Pagila database...")

    # Exclude partitioned payment tables and views
    exclude_tables = [
        'payment',  # Partitioned table
        'payment_p2022_01', 'payment_p2022_02', 'payment_p2022_03',
        'payment_p2022_04', 'payment_p2022_05', 'payment_p2022_06',
        'payment_p2022_07',
    ]

    tables = introspect_schema_django(
        db_alias='default',
        exclude_tables=exclude_tables,
    )

    logger.info(f"Found {len(tables)} tables")
    for t in tables:
        logger.info(f"  - {t.name} ({len(t.columns)} columns, {len(t.primary_key_columns)} PKs)")

    return tables


def build_intermediate_representation(tables):
    """Build the intermediate representation."""
    from drf_auto_generator.mapper import build_intermediate_representation

    logger.info("Building intermediate representation...")
    ir = build_intermediate_representation(tables)

    # Log relationships found
    for t in ir:
        if t.relationships:
            logger.info(f"  {t.name}: {len(t.relationships)} relationships")
            for rel in t.relationships:
                logger.debug(f"    - {rel.get('name')} -> {rel.get('target_table')} ({rel.get('type')})")

    return ir


def generate_with_codegen_v2(tables, output_dir):
    """Generate code using the new CodeGen V2 system."""
    from drf_auto_generator.codegen_v2.main import generate_from_tables

    logger.info(f"Generating code with CodeGen V2 to {output_dir}...")

    # Clean output directory
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    # Generate Django project
    django_dir = os.path.join(output_dir, 'django_project')
    results = generate_from_tables(
        tables=tables,
        output_dir=django_dir,
        project_name='pagila_api',
        app_name='dvdrental',
        database_name='pagila',
        generators=['django'],
    )

    django_files = results.get('django', [])
    logger.info(f"Generated {len(django_files)} Django files")

    # Generate MCP server
    mcp_dir = os.path.join(output_dir, 'mcp_server')
    results = generate_from_tables(
        tables=tables,
        output_dir=mcp_dir,
        project_name='pagila_mcp',
        app_name='server',
        database_name='pagila',
        generators=['mcp'],
        config={'server_name': 'pagila-mcp'},
    )

    mcp_files = results.get('mcp', [])
    logger.info(f"Generated {len(mcp_files)} MCP server files")

    return django_files, mcp_files


def validate_generated_code(output_dir):
    """Validate all generated Python files."""
    import ast

    logger.info("Validating generated Python code...")

    errors = []
    validated = 0

    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        code = f.read()
                    ast.parse(code)
                    validated += 1
                except SyntaxError as e:
                    errors.append((filepath, str(e)))
                    logger.error(f"Syntax error in {filepath}: {e}")

    logger.info(f"Validated {validated} Python files")

    if errors:
        logger.error(f"Found {len(errors)} files with syntax errors")
        return False

    return True


def print_sample_code(output_dir):
    """Print sample generated code for review."""
    logger.info("\n" + "="*60)
    logger.info("SAMPLE GENERATED CODE")
    logger.info("="*60)

    # Print models.py snippet
    models_path = os.path.join(output_dir, 'django_project', 'dvdrental', 'models.py')
    if os.path.exists(models_path):
        with open(models_path, 'r') as f:
            content = f.read()
        logger.info("\n--- dvdrental/models.py (first 100 lines) ---")
        print('\n'.join(content.split('\n')[:100]))

    # Print views.py snippet
    views_path = os.path.join(output_dir, 'django_project', 'dvdrental', 'views.py')
    if os.path.exists(views_path):
        with open(views_path, 'r') as f:
            content = f.read()
        logger.info("\n--- dvdrental/views.py (first 60 lines) ---")
        print('\n'.join(content.split('\n')[:60]))

    # Print MCP tools.py snippet
    tools_path = os.path.join(output_dir, 'mcp_server', 'tools.py')
    if os.path.exists(tools_path):
        with open(tools_path, 'r') as f:
            content = f.read()
        logger.info("\n--- mcp_server/tools.py (first 80 lines) ---")
        print('\n'.join(content.split('\n')[:80]))


def main():
    """Run the end-to-end test."""
    output_dir = '/tmp/pagila_codegen_test'

    logger.info("="*60)
    logger.info("PAGILA END-TO-END TEST WITH CODEGEN V2")
    logger.info("="*60)

    try:
        # Step 1: Setup Django
        logger.info("\nStep 1: Setting up Django...")
        setup_django()

        # Step 2: Introspect database
        logger.info("\nStep 2: Introspecting Pagila database...")
        raw_tables = introspect_pagila()

        # Step 3: Build IR
        logger.info("\nStep 3: Building intermediate representation...")
        tables = build_intermediate_representation(raw_tables)

        # Step 4: Generate code
        logger.info("\nStep 4: Generating code with CodeGen V2...")
        django_files, mcp_files = generate_with_codegen_v2(tables, output_dir)

        # Step 5: Validate
        logger.info("\nStep 5: Validating generated code...")
        is_valid = validate_generated_code(output_dir)

        # Step 6: Print samples
        print_sample_code(output_dir)

        # Summary
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)
        logger.info(f"Tables processed: {len(tables)}")
        logger.info(f"Django files generated: {len(django_files)}")
        logger.info(f"MCP files generated: {len(mcp_files)}")
        logger.info(f"All code valid: {is_valid}")
        logger.info(f"Output directory: {output_dir}")

        if is_valid:
            logger.info("\n✅ END-TO-END TEST PASSED!")
            return 0
        else:
            logger.error("\n❌ END-TO-END TEST FAILED - Syntax errors found")
            return 1

    except Exception as e:
        logger.exception(f"Test failed with error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
