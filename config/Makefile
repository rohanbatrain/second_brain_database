# Makefile for Second Brain Database development tasks

.PHONY: help lint lint-fix format check test install-dev clean

# Default target
help:
	@echo "Available commands:"
	@echo "  lint          - Run all linting tools (check only)"
	@echo "  lint-fix      - Run linting tools with auto-fix where possible"
	@echo "  format        - Format code with black and isort"
	@echo "  check         - Run type checking with mypy"
	@echo "  pylint        - Run pylint code quality checks"
	@echo "  test          - Run tests with pytest"
	@echo "  install-dev   - Install development dependencies with uv"
	@echo "  setup-dev     - Complete development environment setup"
	@echo "  validate-dev  - Validate development environment"
	@echo "  pre-commit    - Install pre-commit hooks"
	@echo "  clean         - Clean up temporary files"

# Linting commands
lint:
	@echo "🔍 Running all linting tools..."
	python scripts/lint.py

lint-fix:
	@echo "🔧 Running linting tools with auto-fix..."
	python scripts/lint.py --fix

format:
	@echo "🎨 Formatting code..."
	python scripts/lint.py --tool black --fix
	python scripts/lint.py --tool isort --fix

check:
	@echo "🔍 Running type checks..."
	python scripts/lint.py --tool mypy

pylint:
	@echo "🔍 Running pylint..."
	python scripts/lint.py --tool pylint

# Testing
test:
	@echo "🧪 Running tests..."
	python -m pytest

test-cov:
	@echo "🧪 Running tests with coverage..."
	python -m pytest --cov=src --cov-report=html --cov-report=term

# Development setup
install-dev:
	@echo "📦 Installing development dependencies..."
	uv sync --extra dev

setup-dev:
	@echo "🚀 Setting up development environment..."
	uv run python scripts/setup_dev_environment.py

validate-dev:
	@echo "✅ Validating development environment..."
	uv run python scripts/validate_dev_environment.py

pre-commit:
	@echo "🪝 Installing pre-commit hooks..."
	pre-commit install

# Cleanup
clean:
	@echo "🧹 Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .coverage

# Quick development workflow
dev-setup: setup-dev pre-commit
	@echo "✅ Development environment setup complete!"

# CI/CD commands
ci-lint:
	@echo "🤖 Running CI linting checks..."
	python scripts/lint.py --skip mypy

ci-test:
	@echo "🤖 Running CI tests..."
	python -m pytest --cov=src --cov-report=xml

# File-specific linting
lint-file:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make lint-file FILE=path/to/file.py"; \
	else \
		echo "🔍 Linting $(FILE)..."; \
		python scripts/lint.py $(FILE); \
	fi

# Directory-specific linting
lint-dir:
	@if [ -z "$(DIR)" ]; then \
		echo "Usage: make lint-dir DIR=path/to/directory"; \
	else \
		echo "🔍 Linting $(DIR)..."; \
		python scripts/lint.py $(DIR); \
	fi