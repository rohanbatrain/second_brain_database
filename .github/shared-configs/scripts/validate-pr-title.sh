#!/bin/bash
# PR title validation script
# Enforces conventional PR title format

PR_TITLE="$1"

if [ -z "$PR_TITLE" ]; then
    echo "❌ ERROR: PR title not provided"
    exit 1
fi

# Allowed patterns: type: message or type(scope): message
PATTERN="^(feat|fix|perf|refactor|docs|chore|hotfix|release)(\(.+\))?: .+$"

if [[ ! $PR_TITLE =~ $PATTERN ]]; then
    echo "❌ ERROR: Invalid PR title: '$PR_TITLE'"
    echo ""
    echo "PR titles must follow the Conventional Commits format:"
    echo "  <type>: <message>"
    echo "  or"
    echo "  <type>(<scope>): <message>"
    echo ""
    echo "Allowed types:"
    echo "  • feat:       New features"
    echo "  • fix:        Bug fixes"
    echo "  • perf:       Performance improvements"
    echo "  • refactor:   Code refactoring"
    echo "  • docs:       Documentation changes"
    echo "  • chore:      Maintenance tasks"
    echo "  • hotfix:     Critical fixes"
    echo "  • release:    Release preparation"
    echo ""
    echo "Examples:"
    echo "  ✅ feat: Add user authentication"
    echo "  ✅ fix(api): Resolve login timeout issue"
    echo "  ✅ docs: Update API documentation"
    echo "  ❌ Added new feature (no type prefix)"
    echo "  ❌ feat - new thing (wrong separator)"
    echo ""
    exit 1
fi

echo "✅ PR title '$PR_TITLE' is valid"
exit 0
