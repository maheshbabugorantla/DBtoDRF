# 🚀 Generate Django RESTful API from a relational database schema

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Django](https://img.shields.io/badge/django-5.2+-green.svg)](https://djangoproject.com)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**Automatically generate a complete Django REST Framework API from your existing database schema using Django's powerful introspection capabilities.**

Transform your database into a production-ready REST API in seconds, not hours. DRF Auto Generator analyzes your database schema and creates models, serializers, views, URLs, admin interfaces, and comprehensive API documentation - all with proper relationships, constraints, and best practices.

---

## ✨ Features

### 🏗️ **Complete API Generation**

- **Django Models** with proper field types, relationships, and constraints
- **DRF Serializers** with nested relationships and validation
- **ViewSets & Views** with CRUD operations and filtering
- **URL Configuration** with RESTful routing
- **Admin Interface** with inline editing and search
- **OpenAPI Documentation** with Swagger UI integration

### 🎯 **Smart Database Analysis**

- **Relationship Detection** - Automatically identifies Foreign Keys, Many-to-Many, and One-to-One relationships
- **Constraint Mapping** - Preserves unique constraints, indexes, and check constraints
- **Accurate Data Type Mapping** - Maps database types to appropriate Django fields
- **Primary Key Handling** - Supports simple and composite primary keys

### 🛠️ Database Support

| Database | Status | Notes |
|----------|--------|-------|
| **PostgreSQL** | ✅ Full Support | Recommended for production |
| **MySQL/MariaDB** | 🔄 Planned | Next Release |
| **SQLite** | 🔄 Planned | Right after MySQL support |
| **SQL Server** | 🔄 Planned | Future release |
| **Oracle** | 🔄 Planned | Future release |

---

## 🚦 Quick Start

### 🚀 Quick Start with Simple Blog Demo

The easiest way to try DRF Auto Generator is with our pre-configured blog example:

1. [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

    ```bash
    $ curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2. Test the api generation tool

```bash
# Clone the repository (if you haven't already)
git clone https://github.com/maheshbabugorantla/DBtoDRF.git
cd DBtoDRF

# Setup the virtualenv for the project using uv
uv venv --python 3.12 .venv && source .venv/bin/activate

# Install the tool
make build_for_postgres

# Navigate to the simple blog example
cd examples/simple_blog

# Start PostgreSQL with sample blog data
docker-compose -f docker-compose.yml up -d --build

# Keep running the below command until the STATUS show the database as healthy
docker-compose -f docker-compose.yml ps
NAME                IMAGE                COMMAND                  SERVICE             CREATED             STATUS                    PORTS
simple_blog_db      postgres:17-alpine   "docker-entrypoint.s…"   postgres            17 minutes ago      Up 17 minutes (healthy)   0.0.0.0:5432->5432/tcp

# Wait for database to be ready (check with docker-compose ps)

# Generate the Django REST API
drf-generate -c simple_blog_db_config.yaml

# Navigate to generated project and run it
cd simple_blog_api
uv venv .venv && source .venv/bin/activate
(.venv) uv pip install -r requirements.txt
(.venv) python manage.py runserver 8000 # If there is already service running on port 8000. Please choose a different port

# Replace the port number if other than 8000
Navigate to http://127.0.0.1:8000/api/schema/swagger-ui/#/
```
---

## 📖 Documentation

### Configuration Options

Create a YAML configuration file with the following options:

```yaml
# Database Configuration (Required)
databases:
  default:
    ENGINE: 'django.db.backends.postgresql'  # Database backend
    NAME: 'mydb'                            # Database name
    USER: 'user'                            # Database user
    PASSWORD: 'password'                    # Database password
    HOST: 'localhost'                       # Database host
    PORT: '5432'                           # Database port

# Output Configuration
output_dir: "./generated_api"              # Output directory
project_name: "myapi_django"               # Django project name
app_name: "api"                           # Django app name


exclude_tables:                           # Exclude these tables
  - django_migrations
  - django_admin_log
  - django_content_type
  - django_session
  - auth_group
  - auth_group_permissions
  - auth_user_user_permissions
  - authtoken_token
  - auth_permission
  - auth_user
  - auth_user_groups

# API Documentation
openapi_title: "My API"                   # API title
openapi_version: "1.0.0"                 # API version
openapi_description: "Generated API"      # API description
openapi_server_url: "http://localhost:8000/api/"  # Server URL

# Advanced Options
relation_style: "pk"                      # Relationship style (pk, link, nested)
add_whitenoise: false                     # Add WhiteNoise for static files
generate_schemathesis_tests: true         # Generate property-based tests
```

### Command Line Options

```bash
drf-generate [OPTIONS]

Options:
  -c, --config PATH          Configuration file path (required)
  -v, --verbose              Enable verbose logging
  --no-color                 Disable colored logging output
  --help                     Show help message
```

### Examples

#### PostgreSQL with Custom Schema

For your own database, create a configuration file:

```yaml
# config-postgres.yaml
databases:
  default:
    ENGINE: 'django.db.backends.postgresql'
    NAME: 'your_database'
    USER: 'your_user'
    PASSWORD: 'your_password'
    HOST: 'localhost'
    PORT: '5432'

output_dir: "./my_api"
project_name: "my_api_django"
app_name: "api"

openapi_title: "My Database API"
openapi_description: "Auto-generated API from database schema"
```

```bash
# Generate API from your database
drf-generate -c config-postgres.yaml -v
```

## 🏛️ Generated Project Structure

```
my_api/
├── manage.py                          # Django management script
├── requirements.txt                   # Python dependencies
├── .env                              # Environment variables template
├── .gitignore                        # Git ignore rules
├── openapi.yaml                      # OpenAPI specification
├── my_api_django/                    # Django project
│   ├── __init__.py
│   ├── settings.py                   # Django settings
│   ├── urls.py                       # Root URL configuration
│   ├── wsgi.py                       # WSGI application
│   └── asgi.py                       # ASGI application
└── api/                              # Django app
    ├── __init__.py
    ├── apps.py                       # App configuration
    ├── models.py                     # Django models
    ├── serializers.py                # DRF serializers
    ├── views.py                      # DRF views
    ├── urls.py                       # App URL configuration
    ├── admin.py                      # Django admin
    ├── migrations/                   # Database migrations
    │   └── __init__.py
    └── tests/                        # Generated tests
        ├── __init__.py
        ├── test_schemathesis_integration.py  # Property-based API tests
        ├── test_api_users.py         # Per-model tests
        └── README.md                 # Testing documentation
```

---

## ⚡ Advanced Usage

### CodeGen V2: Next-Generation Code Generation

CodeGen V2 is a new, cleaner code generation architecture that provides:

- **CodeBuilder Pattern** - Context managers for Python code generation with automatic indentation
- **Pydantic IR** - Type-safe Intermediate Representation for database schemas
- **Plugin Architecture** - Extensible generators for different output formats
- **Multiple Outputs** - Django REST Framework, MCP Servers, Google Toolbox

#### Available Generators

| Generator | Output | Description |
|-----------|--------|-------------|
| `django` | Python | Django REST Framework project (models, serializers, views, urls) |
| `mcp` | Python | MCP Server for AI assistants (Claude, etc.) |
| `toolbox` | YAML | Google MCP Toolbox for Databases configuration |

#### Using CodeGen V2 Programmatically

```python
from drf_auto_generator.codegen_v2 import (
    DatabaseSchema, TableSchema, ColumnSchema, IndexSchema,
    FieldType, RelationshipType
)
from drf_auto_generator.codegen_v2.main import generate_from_tables

# Generate Django + MCP Server + Toolbox config
results = generate_from_tables(
    tables=introspected_tables,
    output_dir="./output",
    project_name="my_api",
    database_name="mydb",
    generators=["django", "mcp", "toolbox"],
)
```

### Google MCP Toolbox for Databases

Generate YAML configuration for [Google's MCP Toolbox](https://github.com/googleapis/genai-toolbox):

```python
from drf_auto_generator.codegen_v2.main import generate_toolbox_config

generate_toolbox_config(
    tables=tables,
    output_dir="./toolbox",
    database_name="pagila",
    db_kind="postgresql",  # postgresql, mysql, alloydb, cloudsql-postgres, bigquery
)
```

**Generated tools include:**
- `list_{table}` - Paginated listing
- `get_{table}` - Get by primary key
- `search_{table}` - Text search on indexed text fields
- `filter_{table}_by_{column}` - Filter by indexed columns (auto-detected)
- `create_{table}`, `update_{table}`, `delete_{table}` - CRUD operations
- `describe_schema` - Schema introspection

**Toolsets for access control:**
- `read_only` - Safe for most AI agents
- `full_crud` - All operations including mutations
- `{table}_tools` - All tools for a specific table

### MCP Server Generation

Generate a Python MCP server for AI assistants:

```python
from drf_auto_generator.codegen_v2.main import generate_mcp_server

generate_mcp_server(
    tables=tables,
    output_dir="./mcp_server",
    server_name="my-db-mcp",
    database_name="mydb",
)
```

### Custom Field Mapping

The generator intelligently maps database types to Django fields:

| Database Type | Django Field | Notes |
|---------------|--------------|-------|
| `varchar(n)` | `CharField(max_length=n)` | Character fields |
| `text` | `TextField()` | Large text |
| `integer` | `IntegerField()` | Integers |
| `bigint` | `BigIntegerField()` | Large integers |
| `decimal(p,s)` | `DecimalField(max_digits=p, decimal_places=s)` | Precise decimals |
| `boolean` | `BooleanField()` | True/False |
| `date` | `DateField()` | Dates |
| `timestamp` | `DateTimeField()` | Date/time |
| `json/jsonb` | `JSONField()` | JSON data (PostgreSQL) |

### Relationship Handling

The generator automatically detects and creates:

- **Foreign Keys** → `ForeignKey` fields with proper `on_delete` behavior
- **Many-to-Many** → `ManyToManyField` with automatic through table detection
- **One-to-One** → `OneToOneField` relationships
- **Self-referential** → Self-referencing relationships with appropriate `related_name`

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Setup

```bash
# Clone the repository
git clone https://github.com/maheshbabugorantla/drf-auto-generator.git
cd drf-auto-generator

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=drf_auto_generator --cov-report=html

# Run specific test categories
python -m pytest tests/test_models.py -v
python -m pytest tests/test_serializers.py -v
python -m pytest tests/test_views.py -v
```

### Code Quality

```bash
# Format code
black drf_auto_generator/ tests/

# Lint code
ruff check drf_auto_generator/ tests/

# Type checking
mypy drf_auto_generator/
```

### Contribution Guidelines

1. **Fork the repository** and create a feature branch
2. **Write tests** for new functionality
3. **Follow code style** (Black formatting, type hints)
4. **Update documentation** for new features
5. **Submit a Pull Request** with a clear description

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📄 License

This project is licensed under the **Apache License 2.0** - see the [LICENSE](LICENSE) file for details.

---

## 🎉 Acknowledgments

- **Django Team** - For the amazing ORM and introspection capabilities
- **Django REST Framework** - For the excellent API framework

---

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=maheshbabugorantla/drf-auto-generator&type=Date)](https://star-history.com/#maheshbabugorantla/drf-auto-generator&Date)

---

**Made with ❤️ by [Mahesh Babu Gorantla](https://github.com/maheshbabugorantla)**
