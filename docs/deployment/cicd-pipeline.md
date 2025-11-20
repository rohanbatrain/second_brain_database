# CI/CD Pipeline Documentation

Complete guide to the Second Brain Database Continuous Integration and Continuous Deployment pipeline.

## Overview

Our CI/CD pipeline automates testing, building, and deploying all components of the Second Brain Database using GitHub Actions.

## Pipeline Stages

```
┌─────────────┐      ┌──────────┐      ┌──────────┐      ┌────────────┐
│   Code      │──────▶│  Build   │──────▶│   Test   │──────▶│  Deploy    │
│   Push      │      │          │      │          │      │            │
└─────────────┘      └──────────┘      └──────────┘      └────────────┘
                           │                 │                   │
                           │                 │                   │
                        Lint             Unit Tests          Production
                        Type Check       Integration        Staging
                        Compile          E2E Tests          Preview
```

## GitHub Actions Workflows

### 1. Test Workflow

**Trigger**: Push to any branch, Pull Request

**File**: `.github/workflows/test.yml`

```yaml
name: Test

on:
  push:
    branches: ['**']
  pull_request:
    branches: [main, development]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --extra dev
      
      - name: Run linters
        run: |
          uv run flake8
          uv run pylint src/
          uv run mypy src/
      
      - name: Run tests
        run: |
          uv run pytest --cov=src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  test-frontend:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        app: [sbd-nextjs-digital-shop, sbd-nextjs-university-clubs-platform, sbd-nextjs-blog-platform, sbd-nextjs-family-hub]
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: submodules/${{ matrix.app }}/package-lock.json
      
      - name: Install dependencies
        working-directory: submodules/${{ matrix.app }}
        run: npm ci
      
      - name: Run linters
        working-directory: submodules/${{ matrix.app }}
        run: npm run lint
      
      - name: Run type check
        working-directory: submodules/${{ matrix.app }}
        run: npm run type-check
      
      - name: Run unit tests
        working-directory: submodules/${{ matrix.app }}
        run: npm test
      
      - name: Build
        working-directory: submodules/${{ matrix.app }}
        run: npm run build
```

### 2. E2E Test Workflow

**Trigger**: Scheduled (nightly), Manual dispatch

**File**: `.github/workflows/e2e.yml`

```yaml
name: E2E Tests

on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM daily
  workflow_dispatch:

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        app: [sbd-nextjs-digital-shop, sbd-nextjs-family-hub]
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install dependencies
        working-directory: submodules/${{ matrix.app }}
        run: npm ci
      
      - name: Install Playwright
        working-directory: submodules/${{ matrix.app }}
        run: npx playwright install --with-deps
      
      - name: Run E2E tests
        working-directory: submodules/${{ matrix.app }}
        run: npm run test:e2e
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report-${{ matrix.app }}
          path: submodules/${{ matrix.app }}/playwright-report/
```

### 3. Build & Deploy Workflow

**Trigger**: Push to `main`, `development`, Tagged releases

**File**: `.github/workflows/deploy.yml`

```yaml
name: Build and Deploy

on:
  push:
    branches: [main, development]
    tags:
      - 'v*'

jobs:
  build-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ghcr.io/secondbraindatabase/backend:latest
            ghcr.io/secondbraindatabase/backend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
  
  deploy-frontend:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        app:
          - name: sbd-nextjs-digital-shop
            vercel-org: ${{ secrets.VERCEL_ORG_ID }}
            vercel-project: ${{ secrets.VERCEL_PROJECT_SHOP }}
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ matrix.app.vercel-org }}
          vercel-project-id: ${{ matrix.app.vercel-project }}
          working-directory: submodules/${{ matrix.app.name }}
          vercel-args: ${{ github.ref == 'refs/heads/main' && '--prod' || '' }}
```

## Environment-Specific Deployments

### Development
- **Trigger**: Push to `development` branch
- **Backend**: Deployed to dev.api.secondbraindatabase.com
- **Frontend**: Deployed to preview URLs

### Staging
- **Trigger**: Push to `staging` branch
- **Backend**: Deployed to staging.api.secondbraindatabase.com
- **Frontend**: Deployed to staging subdomains
- **Database**: Staging database with production-like data

### Production
- **Trigger**: Push to `main` branch or tagged release
- **Backend**: Deployed to api.secondbraindatabase.com
- **Frontend**: Deployed to production domains
- **Database**: Production database with backups

## Secrets Management

### Required Secrets

```bash
# GitHub Secrets (Settings → Secrets and variables → Actions)
VERCEL_TOKEN=<vercel-deploy-token>
VERCEL_ORG_ID=<vercel-organization-id>
VERCEL_PROJECT_SHOP=<project-id-for-shop>
VERCEL_PROJECT_CLUBS=<project-id-for-clubs>
VERCEL_PROJECT_BLOG=<project-id-for-blog>
VERCEL_PROJECT_FAMILY=<project-id-for-family>

# Production environment variables
MONGODB_URL=<production-mongodb-url>
REDIS_URL=<production-redis-url>
JWT_SECRET=<production-jwt-secret>
SENTRY_DSN=<sentry-error-tracking>
```

## Branch Protection Rules

### Main Branch
- ✅ Require pull request before merging
- ✅ Require status checks to pass
  - test-backend
  - test-frontend (all apps)
  - build (all apps)
- ✅ Require linear history
- ✅ Require signatures on commits
- ❌ Allow force pushes
- ❌ Allow deletions

### Development Branch
- ✅ Require pull request
- ✅ Require 1 approval
- ✅ Require status checks
- ❌ Require linear history

## Deployment Rollback

### Automatic Rollback

```yaml
- name: Health check
  run: |
    response=$(curl -s -o /dev/null -w "%{http_code}" https://api.secondbraindatabase.com/health)
    if [ $response != "200" ]; then
      echo "Health check failed, rolling back"
      exit 1
    fi

- name: Rollback on failure
  if: failure()
  run: |
    # Revert to previous deployment
    vercel rollback --token=${{ secrets.VERCEL_TOKEN }}
```

### Manual Rollback

```bash
# List deployments
vercel list

# Rollback to specific deployment
vercel rollback deployment-url --token=$VERCEL_TOKEN
```

## Monitoring Integration

### Sentry Error Tracking

```yaml
- name: Create Sentry Release
  run: |
    curl https://sentry.io/api/0/organizations/$SENTRY_ORG/releases/ \
      -X POST \
      -H "Authorization: Bearer ${{ secrets.SENTRY_AUTH_TOKEN }}" \
      -H "Content-Type: application/json" \
      -d "{\"version\": \"${{ github.sha }}\",\"projects\": [\"backend\"]}"
```

### Datadog Metrics

```yaml
- name: Send deployment metric
  run: |
    curl -X POST "https://api.datadoghq.com/api/v1/events" \
      -H "Content-Type: application/json" \
      -H "DD-API-KEY: ${{ secrets.DATADOG_API_KEY }}" \
      -d @- << EOF
    {
      "title": "Deployment",
      "text": "Deployed ${{ github.sha }} to production",
      "tags": ["environment:production","service:backend"]
    }
    EOF
```

## Performance Budgets

Fail build if thresholds exceeded:

```yaml
- name: Check bundle size
  run: |
    npm run build
    npx size-limit
```

**size-limit.json**:
```json
[
  {
    "path": ".next/static/**/*.js",
    "limit": "300 kB"
  }
]
```

## Caching Strategy

### Docker Layer Caching
```yaml
cache-from: type=gha
cache-to: type=gha,mode=max
```

### NPM Dependencies
```yaml
- uses: actions/cache@v3
  with:
    path: ~/.npm
    key: ${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}
```

### Python Dependencies
```yaml
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

## Notifications

### Slack Integration

```yaml
- name: Notify Slack
  if: always()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    text: 'Deployment ${{ job.status }}'
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## Best Practices

1. **Fast Feedback**: Run quick tests first (linting, unit tests)
2. **Parallel Execution**: Test multiple apps concurrently
3. **Fail Fast**: Stop on first critical error
4. **Cache Aggressively**: Reduce build times
5. **Monitor Always**: Track deployment success rates
6. **Automated Rollback**: Revert bad deployments automatically

---

**Last Updated**: November 2024  
**Maintained by**: DevOps Team  
**Support**: devops@secondbraindatabase.com
