# Submodule Release Workflows

This directory contains standardized CI/CD workflows for all Second Brain Database submodules.

## 📋 Quick Reference

### Workflow Files by Technology

| Technology | Submodules | Workflows |
|------------|-----------|-----------|
| **Next.js** | 10 | `docker-dev.yml`, `docker-prod.yml` |
| **Flutter** | 1 | `Release.yml` |
| **n8n (Node.js)** | 1 | `docker-dev.yml`, `docker-main.yml`, `release.yml` |
| **MkDocs** | 1 | `deploy-dev.yml`, `deploy-main.yml` |

## 🚀 Usage

### Creating a Development Build

Push to the `dev` branch:
```bash
git checkout dev
git add .
git commit -m "feat: new feature"
git push origin dev
```

**Result:** Docker image tagged as `:dev` pushed to both registries.

### Creating a Production Build  

Push to the `main` branch:
```bash
git checkout main
git add .
git commit -m "feat: new feature"
git push origin main
```

**Result:** Docker image tagged as `:latest` with multi-platform support.

### Creating a Release

Create and push a version tag:
```bash
git tag v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

**Result:** 
- Multi-platform Docker images with semantic version tags
- GitHub Release created automatically
- Security scan performed

## 🔍 Monitoring

**GitHub Actions:** `https://github.com/rohanbatrain/[repo]/actions`

**Docker Images:**
- Docker Hub: `https://hub.docker.com/r/rohanbatra/[repo]`
- GHCR: `https://github.com/rohanbatrain/[repo]/pkgs/container/[repo]`

## 🛠️ Maintenance Scripts

- **Update workflows:** `python3 scripts/update_nextjs_workflows.py`
- **Validate workflows:** `./scripts/validate_workflows.sh`

## 📚 Documentation

See [walkthrough.md](file:///Users/rohan/.gemini/antigravity/brain/7d6e4f8b-f275-4aa0-8586-23de794eec1e/walkthrough.md) for complete implementation details.
