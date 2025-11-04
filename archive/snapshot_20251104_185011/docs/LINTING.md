# Code Quality and Linting Guide

This document describes the code quality standards and linting tools used in the Second Brain Database project.

## Overview

We use multiple complementary tools to ensure high code quality:

- **Black**: Code formatter for consistent styling
- **isort**: Import statement organizer
- **Pylint**: Comprehensive code quality analyzer
- **Mypy**: Static type checker
- **Flake8**: Additional style and error checking
- **Pre-commit**: Automated checks before commits

## Quick Start

### Installation

```bash
# Install development dependencies
make install-dev

# Install pre-commit hooks
make pre-commit
```

### Basic Usage

```bash
# Run all linting tools
make lint

# Run linting with auto-fix
make lint-fix

# Format code only
make format

# Run type checking only
make check

# Run pylint only
make pylint
```

## Tools Configuration

### Black (Code Formatter)

Black automatically formats Python code to ensure consistency.

**Configuration**: `pyproject.toml` under `[tool.black]`

**Key settings**:
- Line length: 120 characters
- Target Python version: 3.11
- Excludes: `.venv`, `build`, `dist`, etc.

**Usage**:
```bash
# Check formatting
black --check --diff src/

# Apply formatting
black src/
```

### isort (Import Organizer)

isort organizes import statements according to PEP 8 standards.

**Configuration**: `pyproject.toml` under `[tool.isort]`

**Key settings**:
- Profile: black (compatible with Black)
- Line length: 120 characters
- Multi-line output: 3 (vertical hanging indent)

**Usage**:
```bash
# Check import organization
isort --check-only --diff src/

# Apply import organization
isort src/
```

### Pylint (Code Quality)

Pylint performs comprehensive code quality analysis.

**Configuration**: `.pylintrc`

**Key features**:
- Code complexity analysis
- PEP 8 compliance checking
- Error and warning detection
- Code smell identification

**Usage**:
```bash
# Run pylint
pylint src/

# Run with specific output format
pylint --output-format=colorized src/
```

### Mypy (Type Checking)

Mypy performs static type checking to catch type-related errors.

**Configuration**: `pyproject.toml` under `[tool.mypy]`

**Key settings**:
- Python version: 3.11
- Gradual typing approach (some strict checks disabled initially)
- Ignore missing imports for third-party libraries

**Usage**:
```bash
# Run type checking
mypy src/

# Run with verbose output
mypy --verbose src/
```

### Flake8 (Style Checking)

Flake8 provides additional style and error checking.

**Configuration**: `.flake8`

**Key settings**:
- Line length: 120 characters
- Complexity limit: 10
- Compatible with Black formatting

**Usage**:
```bash
# Run flake8
flake8 src/

# Run with statistics
flake8 --statistics src/
```

## Pre-commit Hooks

Pre-commit hooks automatically run linting tools before each commit.

**Configuration**: `.pre-commit-config.yaml`

**Included hooks**:
- Black formatting
- isort import organization
- Flake8 style checking
- Mypy type checking
- General file checks (trailing whitespace, etc.)
- Security checks with Bandit
- Documentation checks with pydocstyle

**Usage**:
```bash
# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files

# Update hook versions
pre-commit autoupdate
```

## Automation Script

The `scripts/lint.py` script provides a unified interface for all linting tools.

**Features**:
- Run all tools or specific tools
- Automatic fixing where supported
- Colored output and progress indicators
- File and directory filtering

**Usage**:
```bash
# Run all tools
python scripts/lint.py

# Run with auto-fix
python scripts/lint.py --fix

# Run specific tool
python scripts/lint.py --tool black

# Skip specific tools
python scripts/lint.py --skip mypy

# Lint specific files
python scripts/lint.py src/main.py src/config.py
```

## Code Quality Standards

### Line Length
- Maximum 120 characters per line
- Consistent across all tools

### Import Organization
- Standard library imports first
- Third-party imports second
- Local imports last
- Alphabetical sorting within groups

### Code Complexity
- Maximum cyclomatic complexity: 10
- Maximum function arguments: 7
- Maximum local variables: 15

### Type Hints
- Gradual adoption of type hints
- Required for new code
- Use `Optional` for nullable values
- Import types from `typing` module

### Documentation
- Google-style docstrings
- Required for public functions and classes
- Include parameter and return type descriptions

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run linting
  run: |
    make ci-lint
    make ci-test
```

### Local Development

```bash
# Set up development environment
make dev-setup

# Run full quality check
make lint

# Quick format before commit
make format
```

## Troubleshooting

### Common Issues

1. **Black and Flake8 conflicts**
   - Solution: Use compatible configurations (already set up)

2. **Import order issues**
   - Solution: Run `isort` before `black`

3. **Type checking errors**
   - Solution: Add type hints or use `# type: ignore` comments

4. **Pylint false positives**
   - Solution: Use `# pylint: disable=specific-check` comments

### Performance

- Linting large codebases can be slow
- Use `--files-only` flag for specific files
- Consider running tools in parallel

### Configuration Updates

When updating tool configurations:

1. Update the relevant config file
2. Run tools on the entire codebase
3. Fix any new violations
4. Update documentation if needed

## Best Practices

1. **Run linting frequently** during development
2. **Fix issues immediately** rather than accumulating them
3. **Use auto-fix features** when available
4. **Understand the rules** rather than blindly following them
5. **Customize configurations** for project-specific needs
6. **Keep tools updated** to latest stable versions

## Integration with IDEs

### VS Code

Install extensions:
- Python
- Pylint
- Black Formatter
- isort

Configure settings.json:
```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "python.sortImports.args": ["--profile", "black"],
    "editor.formatOnSave": true
}
```

### PyCharm

1. Configure Black as external tool
2. Enable Pylint inspection
3. Configure isort as external tool
4. Set up file watchers for automatic formatting

## Metrics and Reporting

Track code quality metrics:
- Pylint score (target: > 8.0)
- Type coverage (target: > 80%)
- Complexity violations (target: 0)
- Test coverage (target: > 90%)

Generate reports:
```bash
# Pylint report
pylint --output-format=json src/ > pylint-report.json

# Coverage report
pytest --cov=src --cov-report=html

# Type coverage report
mypy --html-report mypy-report src/
```