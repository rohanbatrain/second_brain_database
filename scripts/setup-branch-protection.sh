#!/bin/bash
# Setup branch protection for all submodules using GitHub CLI
# Usage: ./setup-branch-protection.sh

set -e

echo "🔒 GitHub Branch Protection Setup"
echo "=================================="

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed"
    echo "Install: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub CLI"
    echo "Run: gh auth login"
    exit 1
fi

SUBMODULES=(
    "sbd-nextjs-blog-platform"
    "sbd-nextjs-chat"
    "sbd-nextjs-cluster-dashboard"
    "sbd-nextjs-digital-shop"
    "sbd-nextjs-family-hub"
    "sbd-nextjs-ipam"
    "sbd-nextjs-landing-page"
    "sbd-nextjs-memex"
    "sbd-nextjs-myaccount"
    "sbd-nextjs-raunak-ai"
    "sbd-nextjs-university-clubs-platform"
    "sbd-flutter-emotion_tracker"
    "sbd-mkdocs"
    "n8n-nodes-second-brain-database"
)

echo ""
echo "This will configure branch protection for:"
for repo in "${SUBMODULES[@]}"; do
    echo "  • rohanbatrain/$repo"
done
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted."
    exit 1
fi

for REPO in "${SUBMODULES[@]}"; do
    echo ""
    echo "🔒 Protecting main branch: rohanbatrain/$REPO"
    
    # Create branch protection rule
    gh api \
        --method PUT \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "/repos/rohanbatrain/$REPO/branches/main/protection" \
        -f "required_status_checks[strict]=true" \
        -f "required_status_checks[checks][][context]=validate-branch" \
        -f "required_status_checks[checks][][context]=validate-pr-title" \
        -f "required_status_checks[checks][][context]=lint" \
        -f "required_status_checks[checks][][context]=type-check" \
        -f "required_status_checks[checks][][context]=build" \
        -f "required_pull_request_reviews[required_approving_review_count]=1" \
        -f "required_pull_request_reviews[dismiss_stale_reviews]=true" \
        -f "enforce_admins=true" \
        -f "restrictions=null" \
        2>/dev/null && echo "  ✅ Protected" || echo "  ⚠️  Already protected or error occurred"
done

echo ""
echo "=================================="
echo "✅ Branch protection setup complete!"
echo ""
echo "Verify at: https://github.com/rohanbatrain/<REPO>/settings/branches"
