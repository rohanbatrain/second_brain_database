#!/bin/bash
# Automated rollout script for CI/CD enforcement to MkDocs submodule
# Usage: ./rollout-mkdocs.sh

set -e

echo "🚀 CI/CD Enforcement Rollout for MkDocs Submodule"
echo "=================================================="

SUBMODULE="sbd-mkdocs"
SUBMODULE_PATH="submodules/$SUBMODULE"
TEMPLATE_DIR=".github/shared-configs/templates/mkdocs"

echo ""
echo "📦 Processing: $SUBMODULE"
echo "-----------------------------------"

# Check if submodule exists
if [ ! -d "$SUBMODULE_PATH" ]; then
    echo "❌ Directory not found: $SUBMODULE_PATH"
    exit 1
fi

cd "$SUBMODULE_PATH"

# Check for uncommitted changes
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "⚠️  Uncommitted changes detected. Please commit or stash them first."
    exit 1
fi

# Create feature branch
echo "🔀 Creating feature branch..."
git checkout -b feat/ci-cd-enforcement 2>/dev/null || git checkout feat/ci-cd-enforcement

# Copy configuration files
echo "📄 Copying configuration files..."
cp "../../$TEMPLATE_DIR/.pre-commit-config.yaml" .
cp "../../$TEMPLATE_DIR/.yamllint.yaml" .

# Copy GitHub Actions workflows
echo "⚙️  Copying GitHub Actions workflows..."
mkdir -p .github/workflows
cp "../../$TEMPLATE_DIR/ci.yml" .github/workflows/
cp "../../.github/shared-configs/templates/nextjs/pr-labeler.yml" .github/workflows/

# Create .markdownlint.json
echo "📝 Creating .markdownlint.json..."
cat > .markdownlint.json << 'EOF'
{
  "default": true,
  "MD013": false,
  "MD033": false,
  "MD041": false
}
EOF

# Create CONTRIBUTING.md
echo "📝 Creating CONTRIBUTING.md..."
cat > CONTRIBUTING.md << 'EOF'
# Contributing to SBD Documentation

## 🚀 Quick Start

```bash
git clone <repo-url>
cd sbd-mkdocs
pip install -r requirements.txt
mkdocs serve
```

## 📝 Branch Naming Convention

**Format**: `<type>/<name>`

**Allowed Types**: `feat/`, `fix/`, `docs/`, `chore/`

## 💬 Commit Message Format

**Format**: `<type>: <message>`

Examples:
- ✅ `docs: add API documentation`
- ✅ `fix: correct installation steps`

## 🔨 Development Workflow

```bash
# Create feature branch
git checkout -b docs/my-documentation

# Edit documentation
# docs/**/*.md

# Preview locally
mkdocs serve

# Build and verify
mkdocs build --strict

# Commit
git add .
git commit -m "docs: add my documentation"

# Push
git push origin docs/my-documentation
```

## 🔄 Pull Request Process

PR titles must follow: `<type>: <message>`

Automated CI checks:
- ✅ Branch name validation
- ✅ PR title validation
- ✅ Markdown linting
- ✅ YAML linting
- ✅ MkDocs strict build

All checks must pass before merge!
EOF

# Install pre-commit (if available)
if command -v pre-commit &> /dev/null; then
    echo "🪝 Installing pre-commit hooks..."
    pre-commit install || true
else
    echo "⚠️  pre-commit not found. Install with: pip install pre-commit"
fi

# Git add all changes
echo "✅ Staging changes..."
git add .

# Commit
echo "💾 Committing changes..."
git commit -m "chore: add comprehensive CI/CD enforcement setup

- Add pre-commit hooks (markdown lint, YAML lint, mkdocs build)
- Add GitHub Actions workflows (CI, PR labeler)
- Add CONTRIBUTING.md guide
- Add linting configurations" || echo "⚠️  Nothing to commit or commit failed"

echo ""
echo "✅ MkDocs submodule completed!"
echo ""
echo "Next steps:"
echo "  1. cd $SUBMODULE_PATH"
echo "  2. Review changes: git show"
echo "  3. Push branch: git push -u origin feat/ci-cd-enforcement"
echo "  4. Create PR on GitHub"
echo "  5. Configure branch protection (see BRANCH_PROTECTION_GUIDE.md)"
echo ""

cd - > /dev/null
