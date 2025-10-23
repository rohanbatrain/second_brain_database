# Gemini Project Context: Second Brain Database

This document provides an overview of the "Second Brain Database" project, its structure, and development conventions to be used as a reference for AI-assisted development.

## Project Overview

The Second Brain Database is a Python-based backend service built with the **FastAPI** framework. Its primary purpose is to serve as a knowledge management system, allowing users to store, organize, and retrieve information efficiently.

The application is container-ready and uses **uv** for modern Python package management.

### Key Technologies

-   **Backend Framework**: FastAPI
-   **Database**: MongoDB (asynchronous via `motor`)
-   **Cache/Session Store**: Redis
-   **Package Management**: uv
-   **Containerization**: Docker

### Core Features

-   **Authentication**: JWT-based authentication with 2FA, permanent API tokens, and comprehensive session management.
-   **Family Management**: A system for managing family relationships, shared resources, and virtual SBD token accounts.
-   **User Customization**: Manages user profiles, avatars, banners, and themes.
-   **Digital Asset Management**: Includes a "Shop" feature for purchasing and managing digital assets.
-   **Monitoring**: Integrated with Prometheus for metrics and Loki for logging.

## Building and Running

The project uses a `Makefile` and `uv` to streamline development tasks.

### Initial Setup

To set up the development environment, install all necessary dependencies:

```bash
# Install production and development dependencies
uv sync --extra dev
```

### Running the Application

To run the FastAPI server for local development with hot-reloading:

```bash
# Run the development server
uv run uvicorn src.second_brain_database.main:app --reload
```

### Running Tests

The project uses `pytest` for testing. To run the entire test suite:

```bash
# Run tests using the Makefile
make test

# Or run directly with uv
uv run pytest
```

### Building with Docker

To build and run the application as a Docker container:

```bash
# 1. Build the Docker image
docker build -t second-brain-database .

# 2. Run the container
docker run -p 8000:8000 --env-file .env.development.example second-brain-database
```

## Development Conventions

### Code Style and Linting

The project enforces a strict code style to maintain quality and consistency.

-   **Formatter**: `black` for code formatting and `isort` for import sorting.
-   **Linters**: `flake8` and `pylint` for style and error checking.
-   **Type Checking**: `mypy` for static type analysis.
-   **Pre-commit Hooks**: A `.pre-commit-config.yaml` is configured to run these checks automatically before each commit.

**Key Commands:**

```bash
# Format all code
make format

# Run all linters (check only)
make lint

# Run linters and apply automatic fixes
make lint-fix

# Run static type checking
make check
```

### Dependency Management

Dependencies are managed using `uv` and are defined in `pyproject.toml`. The `uv.lock` file ensures reproducible builds.

-   **To add a production dependency**: `uv add "package-name"`
-   **To add a development dependency**: `uv add --group dev "package-name"`
-   **To sync dependencies after changes**: `uv sync --extra dev`

The `requirements.txt` file is not used for dependency management.

### Configuration

The application loads configuration from multiple sources with the following priority:

1.  Path from `SECOND_BRAIN_DATABASE_CONFIG_PATH` environment variable.
2.  `.sbd` file in the project root.
3.  `.env` file in the project root.
4.  Environment variables as a fallback.

For development, you can copy `.env.development.example` to `.env` and populate it with the required values.
