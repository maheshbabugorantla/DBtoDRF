# 🤝 Contributing to DRF Auto Generator

Thank you for your interest in contributing to DRF Auto Generator! We welcome contributions from developers of all skill levels. This guide will help you get started.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style](#code-style)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

## 📜 Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to [maheshbabugorantla@gmail.com](mailto:maheshbabugorantla@gmail.com).

### Our Standards

- **Be respectful** of differing viewpoints and experiences
- **Accept constructive criticism** gracefully
- **Focus on what is best** for the community and project
- **Show empathy** towards other community members

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Database software (PostgreSQL, MySQL, SQLite, etc.) for testing

### Areas Where We Need Help

- 🐛 **Bug Fixes** - Help us squash bugs and improve stability
- ✨ **New Features** - Implement features from our roadmap
- 📚 **Documentation** - Improve guides, tutorials, and API docs
- 🧪 **Testing** - Add tests, improve coverage, test edge cases
- 🎨 **User Experience** - Improve CLI interface, error messages
- 🌐 **Database Support** - Add support for new database backends
- 🔧 **Performance** - Optimize code generation speed and output quality

## 💻 Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/drf-auto-generator.git
cd drf-auto-generator

# Add upstream remote
git remote add upstream https://github.com/maheshbabugorantla/drf-auto-generator.git
```

### 2. Set Up Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### 3. Verify Setup

```bash
# Run tests to ensure everything works
python -m pytest tests/ -v

# Test the CLI
python -m drf_auto_generator.cli --help
```

## 🔄 How to Contribute

### 🐛 Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include:

- **Clear title** and description
- **Steps to reproduce** the behavior
- **Expected behavior** description
- **Actual behavior** description
- **Environment details** (OS, Python version, database)
- **Configuration file** (sanitized)
- **Error messages** and stack traces

### 💡 Suggesting Features

Feature suggestions are welcome! Please:

- **Check existing issues** to avoid duplicates
- **Describe the problem** the feature would solve
- **Explain the proposed solution** in detail
- **Consider backwards compatibility**
- **Provide implementation ideas** if possible

### 🔧 Contributing Code

1. **Find an issue** to work on or create one
2. **Comment on the issue** to let others know you're working on it
3. **Create a branch** from `main`
4. **Make your changes** following our guidelines
5. **Add/update tests** for your changes
6. **Update documentation** if needed
7. **Submit a pull request**

## 🏗️ Development Workflow

### Branch Naming

Use descriptive branch names:

```bash
# Bug fixes
git checkout -b fix/relationship-detection-error

# New features  
git checkout -b feature/mysql-support

# Documentation
git checkout -b docs/installation-guide

# Refactoring
git checkout -b refactor/ast-generation-cleanup
```

### Commit Messages

Follow the [Conventional Commits](https://conventionalcommits.org/) specification:

```bash
# Format: <type>(<scope>): <description>

feat(cli): add --no-color flag for CI environments
fix(relationships): resolve many-to-many detection bug
docs(readme): add MySQL configuration example
test(models): add composite primary key tests
refactor(mapper): simplify relationship analysis logic
```

Types:
- `feat`: New features
- `fix`: Bug fixes
- `docs`: Documentation changes
- `test`: Adding or updating tests
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `ci`: CI/CD changes

## 🧪 Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_models.py -v

# Run with coverage
python -m pytest tests/ --cov=drf_auto_generator --cov-report=html

# Run integration tests
python -m pytest tests/test_integration.py -v --slow

# Test with different databases
python -m pytest tests/ -v -k "postgres"
python -m pytest tests/ -v -k "mysql"
```

### Writing Tests

We use pytest for testing. Please include tests for:

- **New features** - Test all functionality
- **Bug fixes** - Test the specific scenario
- **Edge cases** - Test boundary conditions
- **Error handling** - Test failure scenarios

```python
# Example test structure
def test_relationship_detection():
    """Test that foreign key relationships are detected correctly."""
    # Arrange
    table_info = create_test_table_with_fk()
    
    # Act
    relationships = analyzer.analyze_relationships([table_info])
    
    # Assert
    assert len(relationships) == 1
    assert relationships[0].relationship_type == RelationshipType.MANY_TO_ONE
```

### Database Testing

For database-specific tests, use fixtures:

```python
@pytest.fixture
def postgres_db():
    """Provide PostgreSQL database for testing."""
    # Setup logic
    yield db_connection
    # Cleanup logic

def test_postgres_introspection(postgres_db):
    """Test PostgreSQL-specific introspection."""
    # Test implementation
```

## 🎨 Code Style

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line length**: 88 characters (Black default)
- **Type hints**: Required for all public functions
- **Docstrings**: Required for all public classes and functions
- **Import order**: Use `isort` for consistent imports

### Code Formatting

```bash
# Format code with Black
black drf_auto_generator/ tests/

# Sort imports
isort drf_auto_generator/ tests/

# Lint with Ruff
ruff check drf_auto_generator/ tests/

# Type checking
mypy drf_auto_generator/
```

### Docstring Style

Use Google-style docstrings:

```python
def analyze_relationships(self, tables: List[TableInfo]) -> List[RelationshipInfo]:
    """Analyze relationships across all tables.
    
    Args:
        tables: List of table information objects.
        
    Returns:
        List of discovered relationship information.
        
    Raises:
        ValueError: If tables list is empty.
    """
```

## 📚 Documentation

### Types of Documentation

- **Code comments** - Explain complex logic
- **Docstrings** - Document public APIs
- **README updates** - Keep installation/usage current
- **Examples** - Add configuration examples
- **Tutorials** - Step-by-step guides

### Documentation Updates

When making changes that affect users:

1. **Update docstrings** for modified functions
2. **Add examples** for new features
3. **Update README.md** if needed
4. **Add changelog entries** for significant changes

## 📤 Submitting Changes

### Pull Request Process

1. **Update your branch** with latest main:
   ```bash
   git checkout main
   git pull upstream main
   git checkout your-feature-branch
   git rebase main
   ```

2. **Run the full test suite**:
   ```bash
   python -m pytest tests/ -v
   black drf_auto_generator/ tests/
   ruff check drf_auto_generator/ tests/
   mypy drf_auto_generator/
   ```

3. **Create pull request** with:
   - Clear title and description
   - Link to related issues
   - List of changes made
   - Screenshots if UI-related

### Pull Request Template

```markdown
## Description
Brief description of changes made.

## Related Issues
Fixes #123
Closes #456

## Changes Made
- [ ] Added feature X
- [ ] Fixed bug Y
- [ ] Updated documentation

## Testing
- [ ] All tests pass
- [ ] Added new tests for changes
- [ ] Tested manually with sample database

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Changelog updated (if needed)
```

## 🔄 Release Process

### Version Numbering

We use [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0) - Breaking changes
- **MINOR** (0.2.0) - New features, backwards compatible
- **PATCH** (0.1.1) - Bug fixes, backwards compatible

### Release Checklist

For maintainers preparing releases:

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md** with new features/fixes
3. **Run full test suite** on multiple databases
4. **Create release branch** and pull request
5. **Tag release** after merge
6. **Publish to PyPI** (automated via GitHub Actions)
7. **Create GitHub release** with changelog

## 🆘 Getting Help

### Communication Channels

- **GitHub Issues** - Bug reports and feature requests
- **GitHub Discussions** - Questions and community discussions
- **Email** - [maheshbabugorantla@gmail.com](mailto:maheshbabugorantla@gmail.com) for security issues

### Development Questions

If you're stuck on implementation details:

1. **Check existing code** for similar patterns
2. **Look at tests** for usage examples
3. **Read documentation** and docstrings
4. **Ask in GitHub Discussions** for help

## 🏆 Recognition

Contributors will be:

- **Listed in CONTRIBUTORS.md** file
- **Mentioned in release notes** for significant contributions
- **Added to GitHub contributors** list automatically
- **Acknowledged in project documentation**

## 📈 Project Metrics

Help us track project health:

- **Code coverage** - Aim for >90%
- **Test reliability** - All tests should pass consistently
- **Documentation coverage** - All public APIs documented
- **Performance** - Generation should be fast and efficient

---

Thank you for contributing to DRF Auto Generator! Your efforts help make database-to-API generation accessible to developers worldwide. 🚀

**Questions?** Don't hesitate to ask in [GitHub Discussions](https://github.com/maheshbabugorantla/drf-auto-generator/discussions) or open an issue.