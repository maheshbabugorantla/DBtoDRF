# This is a Makefile for the drf-auto-generator project.
# Makefile for managing Python dependencies with uv + pyproject.toml
# It is used to install the project and run tests.

PYPROJECT := pyproject.toml
REQUIREMENTS_TXT_FILE := requirements.txt

.PHONY: install compile clean

compile:
	@echo "Compiling dependencies... from $(PYPROJECT)"
	uv pip compile $(PYPROJECT) > $(REQUIREMENTS_TXT_FILE)
	@echo "Dependencies compiled successfully to $(REQUIREMENTS_TXT_FILE)"

build_for_postgres:
	@echo "Building project for postgres"
	uv pip install -e './[postgres,dev]'
	@echo "Project built successfully for postgres"

# build_for_sqlite:
# 	@echo "Building project for sqlite"
# 	uv pip install -e './[sqlite,dev]'
# 	@echo "Project built successfully for sqlite"

# build_for_mysql:
# 	@echo "Building project for mysql"
# 	uv pip install -e './[mysql,dev]'
# 	@echo "Project built successfully for mysql"

clean:
	@echo "Cleaning up dependencies..."
	@uv sync --clean
	@echo "Dependencies cleaned up successfully"

.PHONY: test
test:
	pytest
