# Dependency Management Quick Reference

This is a quick reference guide for common dependency management tasks. For comprehensive documentation, see [DEPENDENCY_MANAGEMENT.md](DEPENDENCY_MANAGEMENT.md).

## Quick Commands

### Installation
```bash
# Install all dependencies
uv sync

# Install with development tools
uv sync --extra dev

# Install all optional dependencies
uv sync --all-extras
```

### Adding Dependencies
```bash
# Add production dependency
uv add "package-name>=version"

# Add development dependency
uv add --group dev "package-name>=version"

# Add to specific group
uv add --group monitoring "package-name>=version"
```

### Updating Dependencies
```bash
# Update all dependencies
uv sync --upgrade

# Update lock file only
uv lock --upgrade
```

### Troubleshooting
```bash
# Fix version conflicts
uv sync --upgrade

# Reinstall everything
uv sync --reinstall

# Check dependency tree
uv tree

# Validate environment
make validate-dev
```

## Dependency Groups

| Group | Purpose | Install Command |
|-------|---------|-----------------|
| Production | Core runtime dependencies | `uv sync` |
| `dev` | Development tools | `uv sync --extra dev` |
| `monitoring` | Prometheus/observability | `uv sync --extra monitoring` |
| `docs` | Documentation tools | `uv sync --extra docs` |
| `test` | Extended testing | `uv sync --extra test` |
| `all` | All optional dependencies | `uv sync --all-extras` |

## Version Pinning Examples

```toml
# Restrictive (framework components)
"fastapi>=0.115.0,<0.116.0"

# Moderate (utilities)
"httpx>=0.25.0,<1.0.0"

# Flexible (development tools)
"black>=23.0.0,<25.0.0"

# Security-critical
"cryptography>=41.0.0,<42.0.0"
```

## Common Issues

### ModuleNotFoundError
```bash
uv sync --all-extras
make validate-dev
```

### Version Conflicts
```bash
uv sync --upgrade
uv tree
```

### Lock File Issues
```bash
rm uv.lock
uv lock
uv sync
```

### Environment Problems
```bash
uv venv --force
uv sync --reinstall
```

For detailed troubleshooting, see the [full documentation](DEPENDENCY_MANAGEMENT.md#troubleshooting).