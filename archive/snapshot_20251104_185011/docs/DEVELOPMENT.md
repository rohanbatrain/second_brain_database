# Development Environment Setup

This document explains how to set up and use the development environment for the Second Brain Database project.

## Prerequisites

- Python 3.9 or higher
- [uv](https://docs.astral.sh/uv/) package manager

### Installing uv

If you don't have uv installed, you can install it using:

```bash
# On macOS and Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Quick Setup

### Option 1: Automated Setup (Recommended)

Run the automated setup script:

```bash
# Complete development environment setup
make setup-dev

# Or run the script directly
uv run python scripts/setup_dev_environment.py
```

This will:
- Install all development dependencies
- Validate the installation
- Show you available commands

### Option 2: Manual Setup

```bash
# Install development dependencies
uv sync --extra dev

# Validate installation
make validate-dev
```

## Development Tools

The following development tools are available:

### Code Quality Tools

- **pylint**: Code quality and style checker
- **black**: Code formatter
- **isort**: Import sorter
- **mypy**: Static type checker
- **pre-commit**: Git hooks for code quality

### Testing Tools

- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting
- **pytest-asyncio**: Async testing support

## Available Commands

### Using uv directly

```bash
# Code formatting
uv run black src/ tests/
uv run isort src/ tests/

# Code quality checks
uv run pylint src/
uv run mypy src/

# Testing
uv run pytest
uv run pytest --cov=src --cov-report=html
```

### Using Makefile

```bash
# Development setup
make setup-dev          # Complete development environment setup
make install-dev        # Install development dependencies only
make validate-dev       # Validate development environment

# Code quality
make format             # Format code with black and isort
make lint               # Run all linting tools
make lint-fix           # Run linting tools with auto-fix
make check              # Run type checking with mypy
make pylint             # Run pylint only

# Testing
make test               # Run tests
make test-cov           # Run tests with coverage

# Utilities
make clean              # Clean up temporary files
make help               # Show all available commands
```

## Development Workflow

1. **Set up the environment** (first time only):
   ```bash
   make setup-dev
   ```

2. **Before making changes**:
   ```bash
   # Format your code
   make format
   
   # Run quality checks
   make lint
   ```

3. **Run tests**:
   ```bash
   make test
   ```

4. **Before committing**:
   ```bash
   # Final checks
   make lint
   make test
   ```

## Configuration

The application uses a flexible configuration system that supports multiple sources:

### Configuration Priority (in order)
1. `SECOND_BRAIN_DATABASE_CONFIG_PATH` environment variable (points to config file)
2. `.sbd` file in project root
3. `.env` file in project root  
4. **Environment variables only** (fallback)

### Environment Variable Fallback

If no configuration file is found, the application will automatically fall back to loading all configuration from environment variables. This is particularly useful for:

- **Docker deployments**: Set environment variables in containers
- **CI/CD environments**: Configure via pipeline environment variables
- **Cloud deployments**: Use cloud provider environment variable services
- **Development**: Quick setup without creating config files

#### Required Environment Variables

When using environment variable fallback, ensure these are set:

```bash
# Core application settings
SECRET_KEY=your-secret-key-here
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=your_database_name
REDIS_URL=redis://localhost:6379

# Security settings
FERNET_KEY=your-fernet-key-here
TURNSTILE_SITEKEY=your-turnstile-sitekey
TURNSTILE_SECRET=your-turnstile-secret

# Optional settings (have defaults)
DEBUG=true
HOST=127.0.0.1
PORT=8000
```

#### Testing Environment Fallback

You can test the environment variable fallback by running:

```bash
# Run the environment fallback test
uv run python tests/test_env_fallback_simple.py

# Or use pytest
uv run pytest tests/test_config_fallback.py -v
```

## Dependency Management

This project uses [uv](https://docs.astral.sh/uv/) for modern Python dependency management. All dependencies are declared in `pyproject.toml` and locked in `uv.lock`.

For comprehensive dependency management guidelines, troubleshooting, and best practices, see [DEPENDENCY_MANAGEMENT.md](DEPENDENCY_MANAGEMENT.md).

### Adding New Dependencies

#### Production Dependencies
```bash
# Method 1: Add directly with uv
uv add "package-name>=version"

# Method 2: Edit pyproject.toml [project.dependencies] section, then sync
uv sync
```

#### Development Dependencies
```bash
# Method 1: Add to dev group directly
uv add --group dev "package-name>=version"

# Method 2: Edit pyproject.toml [project.optional-dependencies.dev] section, then sync
uv sync --extra dev
```

#### Optional Dependencies (monitoring, docs, etc.)
```bash
# Add to specific optional group
uv add --group monitoring "prometheus-client>=0.20.0"
uv add --group docs "mkdocs>=1.5.0"
```

### Updating Dependencies
```bash
# Update all dependencies and regenerate lock file
uv sync --upgrade

# Update specific dependency
uv add "package-name>=new-version"

# Update lock file only (without installing)
uv lock --upgrade
```

### Dependency Groups

The project uses the following dependency groups:

- **Production**: Core runtime dependencies (in `[project.dependencies]`)
- **dev**: Development tools (linting, testing, formatting)
- **monitoring**: Prometheus and observability tools
- **docs**: Documentation generation tools

### Installing Specific Groups
```bash
# Install only production dependencies
uv sync

# Install with development tools
uv sync --extra dev

# Install with multiple groups
uv sync --extra dev --extra monitoring

# Install all optional dependencies
uv sync --all-extras
```

### Lock File Management

The `uv.lock` file contains exact versions for reproducible builds:

- **Always commit** `uv.lock` to version control
- **Never edit** `uv.lock` manually
- **Regenerate** with `uv lock` when adding/updating dependencies

### Migration from pip/requirements.txt

This project has migrated from `requirements.txt` to `uv` and `pyproject.toml`:

- ❌ **Don't use**: `pip install -r requirements.txt`
- ✅ **Use instead**: `uv sync`
- ❌ **Don't use**: `pip install package`
- ✅ **Use instead**: `uv add package`

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure you've installed dependencies with `uv sync --extra dev`
2. **Tool not found**: Validate your environment with `make validate-dev`
3. **Version conflicts**: Try `uv sync --upgrade` to resolve conflicts

### Getting Help

- Run `make help` to see all available commands
- Run `make validate-dev` to check your environment
- Check the [uv documentation](https://docs.astral.sh/uv/) for uv-specific issues

## Configuration

Development tools are configured in `pyproject.toml`:

- **black**: Code formatting settings
- **isort**: Import sorting configuration
- **mypy**: Type checking configuration
- **pytest**: Testing configuration
- **coverage**: Coverage reporting settings

You can modify these configurations in the `[tool.*]` sections of `pyproject.toml`.