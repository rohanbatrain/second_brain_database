#!/bin/bash
# Branch name validation script
# Enforces conventional branch naming patterns

BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)

# Allowed patterns
PATTERN="^(feat|fix|perf|refactor|docs|chore|hotfix|release)\/[a-z0-9._-]+$"

if [[ ! $BRANCH_NAME =~ $PATTERN ]]; then
    echo "❌ ERROR: Invalid branch name: '$BRANCH_NAME'"
    echo ""
    echo "Branch names must follow the pattern:"
    echo "  <type>/<name>"
    echo ""
    echo "Allowed types:"
    echo "  • feat/<name>       - New features"
    echo "  • fix/<name>        - Bug fixes"
    echo "  • perf/<name>       - Performance improvements"
    echo "  • refactor/<name>   - Code refactoring"
    echo "  • docs/<name>       - Documentation changes"
    echo "  • chore/<name>      - Maintenance tasks"
    echo "  • hotfix/<name>     - Critical fixes"
    echo "  • release/<version> - Release preparation"
    echo ""
    echo "Examples:"
    echo "  ✅ feat/user-authentication"
    echo "  ✅ fix/login-bug"
    echo "  ✅ docs/api-documentation"
    echo "  ❌ feature/new-thing (wrong type)"
    echo "  ❌ random-branch-name (no type)"
    echo ""
    exit 1
fi

echo "✅ Branch name '$BRANCH_NAME' is valid"
exit 0
