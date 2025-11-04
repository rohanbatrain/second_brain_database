# Dependency Management Guide

This document provides comprehensive guidelines for managing dependencies in the Second Brain Database project using [uv](https://docs.astral.sh/uv/).

## Overview

The project has migrated from `requirements.txt` to modern dependency management using:
- **pyproject.toml**: Dependency declarations and project configuration
- **uv.lock**: Exact version pinning for reproducible builds
- **uv**: Package manager and virtual environment tool

This guide covers:
- Adding and managing dependencies with uv
- Version pinning strategies and best practices
- Optional dependency groups and their purposes
- Troubleshooting common dependency issues
- Migration from legacy dependency management

## Dependency Structure

### Production Dependencies
Located in `[project.dependencies]` section of `pyproject.toml`. These are the core runtime dependencies required for the application to function:

```toml
dependencies = [
    # Web Framework and ASGI Server
    "fastapi>=0.115.0,<0.116.0",
    "uvicorn[standard]>=0.34.0,<0.35.0",
    
    # Database and Storage
    "motor>=3.7.0,<4.0.0",  # MongoDB async driver
    "pymongo>=4.10.0,<5.0.0",  # MongoDB driver (used by motor)
    "redis>=5.0.0,<6.0.0",  # Redis client
    
    # Data Validation and Settings
    "pydantic>=2.11.0,<3.0.0",
    "pydantic-settings>=2.9.0,<3.0.0",
    "python-dotenv>=1.1.0,<2.0.0",
    "email-validator>=2.0.0,<3.0.0",
    
    # Authentication and Security
    "python-jose[cryptography]>=3.3.0,<4.0.0",  # JWT handling
    "bcrypt>=4.0.0,<5.0.0",  # Password hashing
    "cryptography>=41.0.0,<42.0.0",  # Cryptographic operations
    "pyotp>=2.8.0,<3.0.0",  # TOTP/HOTP library for 2FA
    
    # HTTP Client
    "httpx>=0.25.0,<1.0.0",  # HTTP client for external API calls
    "aiohttp>=3.8.0,<4.0.0",  # Alternative HTTP client
    
    # QR Code Generation
    "qrcode[pil]>=7.4.0,<8.0.0",  # QR code generation with PIL support
    
    # Monitoring and Metrics
    "prometheus-fastapi-instrumentator>=7.0.0,<8.0.0",
]
```

### Optional Dependencies
Located in `[project.optional-dependencies]` section. These are organized into logical groups for different use cases:

#### Development Tools (`dev`)
Essential tools for code development, testing, and quality assurance:
```toml
dev = [
    # Code Quality and Linting
    "pylint>=3.3.0,<4.0.0",
    "black>=23.0.0,<25.0.0",
    "isort>=5.12.0,<6.0.0",
    "mypy>=1.5.0,<2.0.0",
    
    # Testing Framework
    "pytest>=7.4.0,<8.0.0",
    "pytest-cov>=4.1.0,<5.0.0",
    "pytest-asyncio>=0.21.0,<1.0.0",
    
    # Pre-commit Hooks
    "pre-commit>=3.4.0,<4.0.0",
    
    # Development Tools
    "python-multipart>=0.0.6,<1.0.0",  # For form data handling in development
]
```

#### Monitoring Tools (`monitoring`)
Advanced monitoring and observability tools:
```toml
monitoring = [
    # Prometheus and Observability
    "prometheus-client>=0.20.0,<1.0.0",
    
    # Optional Grafana Integration
    "grafana-api>=1.0.0,<2.0.0",
]
```

#### Documentation Tools (`docs`)
Tools for generating and maintaining project documentation:
```toml
docs = [
    # Documentation Generation
    "mkdocs>=1.5.0,<2.0.0",
    "mkdocs-material>=9.0.0,<10.0.0",
    
    # API Documentation
    "jsonschema>=4.0.0,<5.0.0",  # For OpenAPI schema validation
]
```

#### Testing Tools (`test`)
Extended testing dependencies for comprehensive test suites:
```toml
test = [
    # Extended Testing Dependencies
    "pytest>=7.4.0,<8.0.0",
    "pytest-cov>=4.1.0,<5.0.0",
    "pytest-asyncio>=0.21.0,<1.0.0",
    "httpx>=0.25.0,<1.0.0",  # For testing HTTP clients
    "jsonschema>=4.0.0,<5.0.0",  # For API response validation in tests
]
```

#### All Dependencies (`all`)
Convenience group that includes all optional dependencies:
```toml
all = [
    # Include all optional dependencies
    "second_brain_database[dev,monitoring,docs,test]",
]
```

## Version Pinning Strategy

### Production Dependencies

#### Critical Framework Dependencies
For core framework components, use restrictive pinning to prevent breaking changes:
```toml
"fastapi>=0.115.0,<0.116.0"  # Pin minor version for API stability
"uvicorn[standard]>=0.34.0,<0.35.0"  # Pin minor version for server stability
"pydantic>=2.11.0,<3.0.0"  # Pin major version for data model compatibility
```

#### Database and Storage Dependencies
Database drivers should be pinned to prevent connection issues:
```toml
"motor>=3.7.0,<4.0.0"  # MongoDB async driver - pin major version
"pymongo>=4.10.0,<5.0.0"  # MongoDB driver - pin major version
"redis>=5.0.0,<6.0.0"  # Redis client - pin major version
```

#### Security-Critical Dependencies
Security packages require more restrictive pinning:
```toml
"cryptography>=41.0.0,<42.0.0"  # Pin major version for security
"bcrypt>=4.0.0,<5.0.0"  # Pin major version for password hashing
"python-jose[cryptography]>=3.3.0,<4.0.0"  # Pin major version for JWT
```

#### Utility Dependencies
Less critical utilities can have more flexible versioning:
```toml
"httpx>=0.25.0,<1.0.0"  # HTTP client - allow minor updates
"python-dotenv>=1.1.0,<2.0.0"  # Environment variables - allow minor updates
"email-validator>=2.0.0,<3.0.0"  # Email validation - allow minor updates
```

### Development Dependencies

Development tools can have more flexible versioning while maintaining compatibility:
```toml
"pytest>=7.4.0,<8.0.0"  # Testing framework - pin major version
"black>=23.0.0,<25.0.0"  # Code formatter - allow multiple major versions
"pylint>=3.3.0,<4.0.0"  # Linter - pin major version
"mypy>=1.5.0,<2.0.0"  # Type checker - pin major version
```

### Version Constraint Guidelines

#### Constraint Types
1. **Exact pinning**: `==1.2.3` - Use only for known problematic packages
2. **Compatible release**: `~=1.2.3` - Equivalent to `>=1.2.3, <1.3.0`
3. **Minimum version**: `>=1.2.3` - Use for packages with good backward compatibility
4. **Version range**: `>=1.2.3,<2.0.0` - Recommended for most dependencies

#### When to Use Each Strategy
- **Exact pinning**: Only when a specific version is required due to bugs or compatibility issues
- **Major version pinning**: For all production dependencies to prevent breaking changes
- **Minor version pinning**: For critical framework components (FastAPI, database drivers)
- **Flexible pinning**: For development tools and utilities

#### Security Considerations
- Pin security-critical packages to specific major versions
- Allow patch updates for security fixes: `>=41.0.0,<42.0.0`
- Monitor security advisories and update promptly
- Use `uv sync --upgrade` regularly to get security patches

## Common Tasks

### Adding Dependencies

#### Production Dependency
```bash
# Method 1: Direct addition (recommended)
uv add "package-name>=version"

# Method 2: Manual edit + sync
# 1. Edit pyproject.toml [project.dependencies]
# 2. Run: uv sync
```

#### Development Dependency
```bash
# Method 1: Add to dev group
uv add --group dev "package-name>=version"

# Method 2: Manual edit + sync
# 1. Edit pyproject.toml [project.optional-dependencies.dev]
# 2. Run: uv sync --extra dev
```

#### Optional Group Dependency
```bash
# Add to monitoring group
uv add --group monitoring "prometheus-client>=0.20.0"

# Add to docs group
uv add --group docs "mkdocs-material>=9.0.0"
```

### Removing Dependencies
```bash
# Remove production dependency
uv remove "package-name"

# Remove from specific group
uv remove --group dev "package-name"
```

### Updating Dependencies

#### Update All Dependencies
```bash
# Update and install
uv sync --upgrade

# Update lock file only
uv lock --upgrade
```

#### Update Specific Dependency
```bash
# Update to latest compatible version
uv add "package-name"

# Update to specific version
uv add "package-name>=new-version"
```

### Installing Dependencies

#### Production Only
```bash
uv sync
```

#### With Development Tools
```bash
uv sync --extra dev
```

#### With Multiple Groups
```bash
uv sync --extra dev --extra monitoring
```

#### All Optional Dependencies
```bash
uv sync --all-extras
```

## Lock File Management

### uv.lock File
- Contains exact versions for all dependencies
- **Must be committed** to version control
- Ensures reproducible builds across environments
- **Never edit manually**

### Regenerating Lock File
```bash
# After adding/removing dependencies
uv lock

# Force regeneration with updates
uv lock --upgrade
```

### Using Lock File
```bash
# Install exact versions from lock file
uv sync --frozen

# Install in CI/CD (production)
uv sync --frozen --no-dev
```

## Troubleshooting

### Common Issues and Solutions

#### Version Conflicts

**Symptoms:**
- `uv sync` fails with version conflict errors
- Dependencies cannot be resolved
- Error messages about incompatible version requirements

**Solutions:**
```bash
# 1. Try automatic resolution with upgrade
uv sync --upgrade

# 2. Check dependency tree to understand conflicts
uv tree

# 3. View detailed conflict information
uv sync --verbose

# 4. Force highest compatible versions (use carefully)
uv sync --resolution=highest

# 5. Reset and try fresh installation
uv sync --reinstall
```

**Advanced Resolution:**
```bash
# Check which packages are causing conflicts
uv tree --show-duplicates

# Examine specific package requirements
uv show package-name

# Test resolution without installing
uv lock --dry-run
```

#### Missing Dependencies

**Symptoms:**
- `ModuleNotFoundError` when running the application
- Import errors for specific packages
- Application fails to start

**Solutions:**
```bash
# 1. Install all dependency groups
uv sync --all-extras

# 2. Install specific groups
uv sync --extra dev --extra monitoring

# 3. Check what's currently installed
uv pip list

# 4. Verify environment setup
make validate-dev

# 5. Reinstall from scratch
uv sync --reinstall
```

**Debugging Steps:**
```bash
# Check if package is in pyproject.toml
grep -r "package-name" pyproject.toml

# Verify virtual environment is active
uv run python -c "import sys; print(sys.prefix)"

# Test specific import
uv run python -c "import package_name"
```

#### Lock File Issues

**Symptoms:**
- `uv.lock` is corrupted or missing
- Inconsistent installations across environments
- Lock file conflicts in version control

**Solutions:**
```bash
# 1. Regenerate lock file
rm uv.lock
uv lock

# 2. Force lock file update
uv lock --upgrade

# 3. Reset environment completely
rm -rf .venv uv.lock
uv sync

# 4. Sync with existing lock file
uv sync --frozen
```

#### Environment Issues

**Symptoms:**
- Commands not found after installation
- Wrong Python version being used
- Virtual environment not activated

**Solutions:**
```bash
# 1. Check uv installation
uv --version

# 2. Verify Python version
uv run python --version

# 3. Check virtual environment location
uv venv --show-path

# 4. Recreate virtual environment
uv venv --force

# 5. Use uv run for commands
uv run python src/second_brain_database/main.py
```

#### Platform-Specific Issues

**Symptoms:**
- Dependencies fail to install on specific OS
- Binary compatibility issues
- Missing system dependencies

**Solutions:**
```bash
# 1. Check platform-specific requirements
uv sync --verbose

# 2. Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install build-essential python3-dev

# 3. Install system dependencies (macOS)
brew install python@3.11

# 4. Use platform-specific constraints
# Add to pyproject.toml:
# [tool.uv]
# constraint-dependencies = ["package==version ; sys_platform == 'darwin'"]
```

### Dependency Conflicts

#### Understanding Conflicts

**Common Conflict Scenarios:**
1. **Transitive dependencies**: Package A and B both depend on C, but require different versions
2. **Version ranges**: Overlapping but incompatible version constraints
3. **Python version**: Package requires different Python version than specified
4. **Platform constraints**: Package not available for current platform

#### Resolution Strategies

**1. Automatic Resolution**
```bash
# Let uv resolve automatically (recommended first step)
uv sync --upgrade
```

**2. Manual Constraint Adjustment**
```toml
# Example: Resolve conflict between FastAPI and Pydantic
dependencies = [
    "fastapi>=0.115.0,<0.116.0",
    "pydantic>=2.11.0,<3.0.0",  # Explicit constraint
    # ... other dependencies
]
```

**3. Override Problematic Dependencies**
```toml
# Force specific version for problematic package
dependencies = [
    "package-a",
    "package-b", 
    "conflicting-package==1.2.3",  # Force specific version
]
```

**4. Use Dependency Groups**
```toml
# Separate conflicting dependencies into different groups
[project.optional-dependencies]
group-a = ["package-a", "dependency-x>=1.0"]
group-b = ["package-b", "dependency-x>=2.0"]
```

#### Conflict Resolution Examples

**Example 1: Pydantic Version Conflict**
```bash
# Problem: FastAPI requires pydantic>=2.0, other package requires pydantic<2.0
# Solution: Update the conflicting package or find alternative

# Check which packages depend on pydantic
uv tree | grep pydantic

# Update to compatible versions
uv add "conflicting-package>=newer-version"
```

**Example 2: Cryptography Version Conflict**
```bash
# Problem: Multiple packages require different cryptography versions
# Solution: Find common compatible version

# Check requirements
uv show cryptography
uv tree | grep cryptography

# Set explicit constraint
# In pyproject.toml:
# "cryptography>=41.0.0,<42.0.0"
```

### Performance Issues

#### Slow Installation

**Symptoms:**
- `uv sync` takes very long time
- Network timeouts during installation
- Large dependency trees

**Solutions:**
```bash
# 1. Use parallel installation (default in uv)
uv sync --verbose

# 2. Use local cache
uv sync --offline  # Use only cached packages

# 3. Reduce dependency scope
uv sync --no-dev  # Skip development dependencies

# 4. Use pre-built wheels
# Ensure pip index includes wheel packages
```

#### Large Virtual Environments

**Symptoms:**
- Virtual environment takes too much disk space
- Slow application startup
- Memory usage issues

**Solutions:**
```bash
# 1. Audit installed packages
uv pip list --format=freeze | wc -l

# 2. Remove unused dependencies
uv remove unused-package

# 3. Use minimal dependency groups
uv sync --extra dev  # Only install what you need

# 4. Clean up cache
uv cache clean
```

### Security Issues

#### Vulnerable Dependencies

**Symptoms:**
- Security scanner reports vulnerabilities
- Outdated packages with known issues
- Dependency confusion attacks

**Solutions:**
```bash
# 1. Update all dependencies
uv sync --upgrade

# 2. Check for security updates
uv pip list --outdated

# 3. Pin secure versions explicitly
# In pyproject.toml, update vulnerable packages

# 4. Use security scanning tools
# pip-audit (install separately)
uv run pip-audit
```

#### Supply Chain Security

**Best Practices:**
```bash
# 1. Always commit uv.lock for reproducible builds
git add uv.lock

# 2. Verify package integrity
uv sync --frozen  # Use exact versions from lock file

# 3. Use trusted package indexes only
# Configure in pyproject.toml if needed

# 4. Regular security updates
uv sync --upgrade  # Run weekly/monthly
```

### Development Environment Issues

#### IDE Integration Problems

**Symptoms:**
- IDE cannot find installed packages
- Linting tools not working
- Type checking fails

**Solutions:**
```bash
# 1. Ensure IDE uses correct Python interpreter
uv run which python

# 2. Install development tools
uv sync --extra dev

# 3. Configure IDE to use uv environment
# Point IDE to: $(uv venv --show-path)/bin/python

# 4. Restart IDE after environment changes
```

#### Testing Issues

**Symptoms:**
- Tests cannot import application modules
- Test dependencies missing
- Inconsistent test results

**Solutions:**
```bash
# 1. Install test dependencies
uv sync --extra test

# 2. Run tests with uv
uv run pytest

# 3. Check test environment
uv run python -m pytest --version

# 4. Validate test configuration
make test  # Use project Makefile
```

### Getting Help

#### Diagnostic Commands
```bash
# Check uv version and configuration
uv --version
uv config list

# Show detailed environment information
uv info

# Check virtual environment status
uv venv list

# Show dependency tree
uv tree

# Validate project configuration
uv check
```

#### When to Seek Help
1. **Persistent conflicts**: After trying automatic resolution and manual constraints
2. **Platform-specific issues**: When problems occur only on specific operating systems
3. **Performance problems**: When installation or runtime performance is severely impacted
4. **Security concerns**: When dealing with vulnerable dependencies or supply chain issues

#### Resources for Help
- [uv GitHub Issues](https://github.com/astral-sh/uv/issues)
- [uv Documentation](https://docs.astral.sh/uv/)
- [Python Packaging Discourse](https://discuss.python.org/c/packaging/)
- Project maintainers and team members

## Best Practices

### Version Constraints
- Use `>=` for minimum versions
- Use `<` for maximum major versions
- Be more restrictive for security-critical packages
- Allow patch updates for stability

### Dependency Groups
- Keep production dependencies minimal
- Separate development tools from production
- Use optional groups for features that aren't always needed

### Lock File
- Always commit uv.lock
- Regenerate after dependency changes
- Use `--frozen` in production deployments

### Security
- Regularly update dependencies: `uv sync --upgrade`
- Monitor security advisories
- Pin security-critical packages more strictly

## Migration Guide

### From requirements.txt
1. **Audit**: Review existing requirements.txt
2. **Categorize**: Separate production vs development dependencies
3. **Convert**: Move to appropriate pyproject.toml sections
4. **Install**: Run `uv sync` to generate lock file
5. **Test**: Validate application works with new setup
6. **Cleanup**: Remove requirements.txt

### From pip
Replace pip commands with uv equivalents:

| pip command | uv equivalent |
|-------------|---------------|
| `pip install package` | `uv add package` |
| `pip install -r requirements.txt` | `uv sync` |
| `pip install -e .` | `uv sync` |
| `pip list` | `uv pip list` |
| `pip freeze` | `uv pip freeze` |

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Install uv
  run: curl -LsSf https://astral.sh/uv/install.sh | sh

- name: Install dependencies
  run: uv sync --frozen --extra dev

- name: Run tests
  run: uv run pytest
```

### Docker Integration
```dockerfile
# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
```

## Validation and Testing

### Validating Dependency Setup

After making changes to dependencies, always validate the setup:

```bash
# Validate development environment
make validate-dev

# Test core imports
uv run python -c "import fastapi, uvicorn, motor, redis, pydantic; print('✅ Core dependencies OK')"

# Test application startup
uv run python src/second_brain_database/main.py --help

# Run basic tests
uv run pytest tests/ -v
```

### Continuous Integration

Ensure your CI/CD pipeline validates dependencies:

```yaml
# Example GitHub Actions step
- name: Validate Dependencies
  run: |
    uv sync --frozen --extra dev
    make validate-dev
    uv run pytest
```

### Dependency Auditing

Regularly audit dependencies for security and maintenance:

```bash
# Check for outdated packages
uv pip list --outdated

# Update dependencies (test thoroughly)
uv sync --upgrade

# Check dependency tree for conflicts
uv tree

# Validate after updates
make validate-dev
```

## Resources

- [uv Documentation](https://docs.astral.sh/uv/)
- [pyproject.toml Specification](https://peps.python.org/pep-0621/)
- [Python Packaging Guide](https://packaging.python.org/)
- [Dependency Management Quick Reference](DEPENDENCY_QUICK_REFERENCE.md)