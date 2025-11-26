# GitHub Workflows Archive - 2025-11-26

This archive contains the original GitHub Actions workflows that were removed from the `.github/workflows/` directory to disable the CI/CD pipeline.

## Archived Workflows

- `dev.yml`: Build and push Docker dev image on pushes to `dev` branch
- `docker-build-prod.yml`: Production Docker build with multi-platform support, security scanning, triggered on `main` branch and `v*` tags
- `docker-test-dev.yml`: Docker dev environment testing on PRs and pushes to `dev`
- `docker-test-test.yml`: Docker test suite on PRs to `main` and pushes to `test` branch
- `main.yml`: Build and push Docker latest image on pushes to `main` branch
- `pypi.yml`: Build, push Docker image, and publish to PyPI on version branches (`v[0-9]+.[0-9]+.[0-9]+`)

## Restoration Instructions

To restore these workflows:

1. Copy the desired workflow files from this archive back to `.github/workflows/`
2. Commit and push the changes
3. Ensure any required secrets (e.g., `DOCKER_HUB_TOKEN`, `PYPI_API_TOKEN`) are configured in the repository settings

## Purpose

These workflows were archived to temporarily disable the CI/CD pipeline while allowing for future reference and potential restoration. The user plans to recreate them manually later.