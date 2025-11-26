#!/bin/bash
# Script to push all CI/CD enforcement branches and create PRs
# Usage: ./push-and-create-prs.sh

set -e

echo "🚀 Pushing CI/CD Enforcement Branches & Creating PRs"
echo "====================================================="

SUBMODULES=(
    "sbd-nextjs-blog-platform"
    "sbd-nextjs-chat"
    "sbd-nextjs-digital-shop"
    "sbd-nextjs-family-hub"
    "sbd-nextjs-ipam"
    "sbd-nextjs-landing-page"
    "sbd-nextjs-memex"
    "sbd-nextjs-myaccount"
    "sbd-nextjs-raunak-ai"
    "sbd-nextjs-university-clubs-platform"
    "sbd-flutter-emotion_tracker"
    "n8n-nodes-second-brain-database"
)

PR_BODY="## 🎯 Changes

This PR implements comprehensive CI/CD enforcement for code quality and workflow standardization.

### ✅ Local Enforcement (Git Hooks)
- **Pre-commit**: Linting, formatting, secret scanning
- **Commit-msg**: Conventional commits validation
- **Pre-push**: Branch naming, type checking, lint validation

### ✅ Remote Enforcement (GitHub Actions)
- **CI Workflow**: Branch/PR validation, linting, type checking, building, testing
- **PR Auto-Labeler**: Automatic labels based on branch type
- **Release Please**: Automated versioning & changelog generation

### 📚 Documentation
- **CONTRIBUTING.md**: Complete developer workflow guide

### 🔗 Related
- Main repo: https://github.com/rohanbatrain/second_brain_database
- Documentation: See BRANCH_PROTECTION_GUIDE.md in main repo

---

**Note**: After merging, configure branch protection rules using the automated script in the main repo."

for SUBMODULE in "${SUBMODULES[@]}"; do
    SUBMODULE_PATH="submodules/$SUBMODULE"
    
    echo ""
    echo "📦 Processing: $SUBMODULE"
    echo "-----------------------------------"
    
    if [ ! -d "$SUBMODULE_PATH" ]; then
        echo "  ⚠️ Directory not found, skipping"
        continue
    fi
    
    cd "$SUBMODULE_PATH"
    
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" != "feat/ci-cd-enforcement" ]; then
        echo "  ⚠️ Not on feat/ci-cd-enforcement branch (on: $CURRENT_BRANCH), skipping"
        cd - > /dev/null
        continue
    fi
    
    # Push branch
    echo "  🔼 Pushing branch..."
    if git push -u origin feat/ci-cd-enforcement 2>&1 | grep -q "up-to-date"; then
        echo "  ✅ Already up-to-date"
    elif git push -u origin feat/ci-cd-enforcement; then
        echo "  ✅ Pushed successfully"
    else
        echo "  ⚠️ Push failed"
        cd - > /dev/null
        continue
    fi
    
    # Create PR
    echo "  📝 Creating PR..."
    if gh pr list --head feat/ci-cd-enforcement --state open | grep -q "feat/ci-cd-enforcement"; then
        echo "  ℹ️  PR already exists"
    else
        if gh pr create \
            --title "chore: Add comprehensive CI/CD enforcement setup" \
            --body "$PR_BODY" \
            --label "chore" 2>&1; then
            echo "  ✅ PR created"
        else
            echo "  ⚠️ PR creation failed (may need manual creation)"
        fi
    fi
    
    cd - > /dev/null
done

echo ""
echo "====================================================="
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "  1. Review PRs on GitHub"
echo "  2. Run branch protection setup: ./scripts/setup-branch-protection.sh"
echo "  3. Merge PRs after review"
echo "  4. Test Release Please automation"
echo ""
