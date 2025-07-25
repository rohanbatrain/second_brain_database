# Second Brain Database

A FastAPI-based database service for managing personal knowledge and information.

## Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager

### Installing uv

If you don't have uv installed:

```bash
# On macOS and Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd second_brain_database

# Install dependencies
uv sync

# Run the application
uv run uvicorn src.second_brain_database.main:app --reload
```

## Development

For development setup and detailed instructions, see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

### Quick Development Setup

```bash
# Install development dependencies
uv sync --extra dev

# Run development tools
make setup-dev
```

## Dependency Management

This project uses [uv](https://docs.astral.sh/uv/) for modern Python dependency management.

For comprehensive dependency management guidelines, see [docs/DEPENDENCY_MANAGEMENT.md](docs/DEPENDENCY_MANAGEMENT.md).

### Quick Reference

#### Adding Dependencies
```bash
# Production dependency
uv add "package-name>=version"

# Development dependency
uv add --group dev "package-name>=version"
```

#### Updating Dependencies
```bash
# Update all dependencies
uv sync --upgrade

# Update lock file
uv lock --upgrade
```

#### Installing Dependencies
```bash
# Production only
uv sync

# With development tools
uv sync --extra dev

# All optional dependencies
uv sync --all-extras
```

## Docker

```bash
# Build image
docker build -t second-brain-database .

# Run container
docker run -p 8000:8000 second-brain-database
```

## License

[Add your license information here]