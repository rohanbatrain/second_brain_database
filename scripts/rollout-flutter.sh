#!/bin/bash
# Automated rollout script for CI/CD enforcement to Flutter submodule
# Usage: ./rollout-flutter.sh

set -e

echo "🚀 CI/CD Enforcement Rollout for Flutter Submodule"
echo "=================================================="

SUBMODULE="sbd-flutter-emotion_tracker"
SUBMODULE_PATH="submodules/$SUBMODULE"
TEMPLATE_DIR=".github/shared-configs/templates/flutter"

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

# Copy GitHub Actions workflows
echo "⚙️  Copying GitHub Actions workflows..."
mkdir -p .github/workflows
cp "../../$TEMPLATE_DIR/ci.yml" .github/workflows/
cp "../../.github/shared-configs/templates/nextjs/pr-labeler.yml" .github/workflows/

# Create CONTRIBUTING.md
echo "📝 Creating CONTRIBUTING.md..."
cat > CONTRIBUTING.md << 'EOF'
# Contributing to SBD Flutter Emotion Tracker

## 🚀 Quick Start

```bash
git clone <repo-url>
cd sbd-flutter-emotion_tracker
flutter pub get
```

## 📝 Branch Naming Convention

**Format**: `<type>/<name>`

**Allowed Types**: `feat/`, `fix/`, `perf/`, `refactor/`, `docs/`, `chore/`, `hotfix/`, `release/`

## 💬 Commit Message Format

**Format**: `<type>: <message>`

Examples:
- ✅ `feat: add emotion tracking UI`
- ✅ `fix(db): resolve data persistence issue`

## 🔨 Development Workflow

```bash
# Create feature branch
git checkout -b feat/my-feature

# Develop
flutter run

# Format code
dart format .

# Analyze
dart analyze

# Test
flutter test

# Commit
git add .
git commit -m "feat: add my feature"

# Push
git push origin feat/my-feature
```

## 🔄 Pull Request Process

PR titles must follow: `<type>: <message>`

Automated CI checks:
- ✅ Branch name validation
- ✅ PR title validation
- ✅ Dart format check
- ✅ Dart analyze
- ✅ Flutter tests
- ✅ APK build verification

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

- Add pre-commit hooks (dart format, analyze, secret scanning)
- Add GitHub Actions workflows (CI, PR labeler)
- Add CONTRIBUTING.md guide" || echo "⚠️  Nothing to commit or commit failed"

echo ""
echo "✅ Flutter submodule completed!"
echo ""
echo "Next steps:"
echo "  1. cd $SUBMODULE_PATH"
echo "  2. Review changes: git show"
echo "  3. Push branch: git push -u origin feat/ci-cd-enforcement"
echo "  4. Create PR on GitHub"
echo "  5. Configure branch protection (see BRANCH_PROTECTION_GUIDE.md)"
echo ""

cd - > /dev/null
