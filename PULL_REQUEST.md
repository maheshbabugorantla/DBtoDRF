# Pull Request: CodeGen V2 with CodeBuilder Pattern and Multi-Generator Support

**Branch:** `claude/explore-code-generation-alternatives-SzanJ`
**Base:** `main`

---

## Summary

This PR introduces **CodeGen V2**, a complete rewrite of the code generation architecture that replaces the cumbersome AST-based approach with a cleaner, more maintainable system.

### Key Features

- **CodeBuilder Pattern**: Context managers for Python code generation with automatic indentation handling
- **Pydantic IR (Intermediate Representation)**: Type-safe schema definitions that can be serialized to YAML
- **Plugin Architecture**: Extensible generator system supporting multiple output formats
- **Three Generators**:
  - `django` - Django REST Framework project (models, serializers, views, urls, admin)
  - `mcp` - MCP Server for AI assistants (Claude, etc.)
  - `toolbox` - Google MCP Toolbox for Databases YAML configuration

### New Files

```
drf_auto_generator/codegen_v2/
├── __init__.py           # Module exports
├── schema.py             # Pydantic IR models (DatabaseSchema, TableSchema, etc.)
├── code_builder.py       # CodeBuilder with context managers
├── base.py               # Plugin architecture (CodeGenerator, GeneratorRegistry)
├── converter.py          # Legacy TableInfo to new schema converter
├── main.py               # Main entry points and convenience functions
├── django/               # Django REST Framework generator
│   ├── models.py         # Django models generator
│   ├── serializers.py    # DRF serializers generator
│   ├── views.py          # DRF viewsets generator
│   ├── urls.py           # URL routing generator
│   ├── admin.py          # Django admin generator
│   ├── project.py        # Project files (settings, wsgi, etc.)
│   └── generator.py      # Main Django generator
├── mcp/                  # MCP Server generator
│   └── generator.py      # Generates server.py, tools.py, resources.py, database.py
└── toolbox/              # Google MCP Toolbox generator
    └── generator.py      # Generates tools.yaml, docker-compose.yaml, README.md
```

### Bug Fixes

- Fixed invalid `max_length` on non-text fields (DateTimeField, AutoField, etc.)
- Fixed model name singularization ("Address" was becoming "Addres")
- Added `managed=False` for legacy database support
- Proper pluralization for `verbose_name_plural`

---

## Test Plan

### Prerequisites

```bash
# Clone and checkout the branch
git clone https://github.com/maheshbabugorantla/DBtoDRF.git
cd DBtoDRF
git fetch origin claude/explore-code-generation-alternatives-SzanJ
git checkout claude/explore-code-generation-alternatives-SzanJ

# Create virtual environment
uv venv --python 3.11 .venv && source .venv/bin/activate

# Install dependencies
make build_for_postgres
```

### 1. Run Unit Tests (30 tests)

```bash
python -m pytest tests/test_codegen_v2.py -v
```

**Expected:** All 30 tests pass

### 2. Test CodeBuilder Pattern

```bash
python -c "
from drf_auto_generator.codegen_v2 import PythonCodeBuilder

b = PythonCodeBuilder()
with b.class_('MyModel', bases=['models.Model']):
    with b.method('__str__', returns='str'):
        b.return_('self.name')

print(b.build())
"
```

**Expected output:**
```python
class MyModel(models.Model):
    def __str__(self) -> str:
        return self.name
```

### 3. Test Google Toolbox Generator

```bash
python -c "
from drf_auto_generator.codegen_v2 import DatabaseSchema, TableSchema, ColumnSchema, IndexSchema, FieldType
from drf_auto_generator.codegen_v2.toolbox import ToolboxGenerator

schema = DatabaseSchema(
    tables=[
        TableSchema(
            name='orders',
            primary_key_columns=['order_id'],
            columns=[
                ColumnSchema(name='order_id', field_type=FieldType.AUTO, primary_key=True),
                ColumnSchema(name='customer_id', field_type=FieldType.INTEGER),
                ColumnSchema(name='status', field_type=FieldType.CHAR, max_length=20),
            ],
            indexes=[
                IndexSchema(name='idx_customer', fields=['customer_id']),
                IndexSchema(name='idx_status', fields=['status']),
            ],
        ),
    ],
    database_name='testdb',
)

generator = ToolboxGenerator(schema)
files = generator.generate()

print('=== tools.yaml (first 50 lines) ===')
print('\n'.join(files['tools.yaml'].split('\n')[:50]))
"
```

**Expected:** YAML with:
- `sources` section with database connection
- `tools` section including `filter_orders_by_customer_id`, `filter_orders_by_status`
- `toolsets` section with `read_only`, `full_crud`, `orders_tools`

### 4. Test Django Generator (Singularization Fix)

```bash
python -c "
from drf_auto_generator.codegen_v2 import DatabaseSchema, TableSchema, ColumnSchema, FieldType
from drf_auto_generator.codegen_v2.django import DjangoGenerator

schema = DatabaseSchema(
    tables=[
        TableSchema(
            name='address',  # Tests singularization exception
            primary_key_columns=['id'],
            columns=[
                ColumnSchema(name='id', field_type=FieldType.AUTO, primary_key=True),
                ColumnSchema(name='street', field_type=FieldType.CHAR, max_length=255),
                ColumnSchema(name='last_update', field_type=FieldType.DATETIME),  # No max_length!
            ],
        ),
    ],
    database_name='testdb',
)

generator = DjangoGenerator(schema)
files = generator.generate()
print(files['api/models.py'])
"
```

**Expected:**
- Model name is `Address` (not `Addres`)
- `last_update = models.DateTimeField()` without `max_length`
- `managed = False` in Meta class

### 5. Test MCP Server Generator

```bash
python -c "
from drf_auto_generator.codegen_v2 import DatabaseSchema, TableSchema, ColumnSchema, FieldType
from drf_auto_generator.codegen_v2.mcp import MCPServerGenerator

schema = DatabaseSchema(
    tables=[
        TableSchema(
            name='users',
            primary_key_columns=['id'],
            columns=[
                ColumnSchema(name='id', field_type=FieldType.AUTO, primary_key=True),
                ColumnSchema(name='email', field_type=FieldType.EMAIL, max_length=255),
            ],
        ),
    ],
    database_name='testdb',
)

generator = MCPServerGenerator(schema)
files = generator.generate()
print('Generated files:', list(files.keys()))
print()
print('=== server.py (first 30 lines) ===')
print('\n'.join(files['server.py'].split('\n')[:30]))
"
```

**Expected:**
- Files: `server.py`, `tools.py`, `resources.py`, `database.py`, `__init__.py`, `pyproject.toml`, `README.md`
- Valid Python code with MCP server setup

### 6. End-to-End Test with Pagila (Optional, requires PostgreSQL)

```bash
# Start PostgreSQL with Pagila database
cd examples/simple_blog
docker-compose up -d

# Wait for database to be ready
docker-compose ps  # Should show "healthy"

# Run E2E test
cd ../..
python test_pagila_e2e.py
```

---

## Breaking Changes

None - this is a new module (`codegen_v2`) that doesn't affect the existing `drf-generate` CLI.

---

## Commits in this PR

1. `feat: Add CodeGen V2 with CodeBuilder pattern and MCP server support`
2. `test: Add end-to-end test with Pagila database for CodeGen V2`
3. `fix: Resolve field options and model name generation issues in CodeGen V2`
4. `feat: Add Google MCP Toolbox for Databases generator`
5. `feat: Add index-based filter tools to Toolbox generator`
6. `docs: Add CodeGen V2 documentation to README`

---

## Documentation

- Updated README.md with CodeGen V2 usage examples
- Each generator includes inline documentation
- Generated README.md files for MCP and Toolbox outputs

---

## How to Create This PR

```bash
# Using GitHub CLI
gh pr create \
  --title "feat: Add CodeGen V2 with CodeBuilder pattern and multi-generator support" \
  --body-file PULL_REQUEST.md \
  --base main \
  --head claude/explore-code-generation-alternatives-SzanJ

# Or manually on GitHub:
# 1. Go to https://github.com/maheshbabugorantla/DBtoDRF/compare/main...claude/explore-code-generation-alternatives-SzanJ
# 2. Click "Create pull request"
# 3. Copy the content from this file as the PR description
```
