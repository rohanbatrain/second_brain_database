#!/bin/bash
#
# Set DOCKER_HUB_TOKEN secret across all submodule repositories
#

# Check if DOCKER_HUB_TOKEN is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <DOCKER_HUB_TOKEN>"
    echo ""
    echo "Example:"
    echo "  $0 dckr_pat_xxxxxxxxxxxxxxxxxxxx"
    exit 1
fi

DOCKER_HUB_TOKEN="$1"

# All submodule repositories
REPOS=(
    "rohanbatrain/sbd-nextjs-blog-platform"
    "rohanbatrain/sbd-nextjs-chat"
    "rohanbatrain/sbd-nextjs-cluster-dashboard"
    "rohanbatrain/sbd-nextjs-digital-shop"
    "rohanbatrain/sbd-nextjs-family-hub"
    "rohanbatrain/sbd-nextjs-ipam"
    "rohanbatrain/sbd-nextjs-landing-page"
    "rohanbatrain/sbd-nextjs-memex"
    "rohanbatrain/sbd-nextjs-myaccount"
    "rohanbatrain/sbd-nextjs-raunak-ai"
    "rohanbatrain/sbd-nextjs-university-clubs-platform"
    "rohanbatrain/sbd-flutter-emotion_tracker"
    "rohanbatrain/n8n-nodes-second-brain-database"
    "rohanbatrain/sbd-mkdocs"
)

echo "Setting DOCKER_HUB_TOKEN secret for ${#REPOS[@]} repositories..."
echo ""

SUCCESS_COUNT=0
FAIL_COUNT=0

for repo in "${REPOS[@]}"; do
    echo "📦 Setting secret for $repo..."
    
    if gh secret set DOCKER_HUB_TOKEN --repo "$repo" --body "$DOCKER_HUB_TOKEN"; then
        echo "  ✓ Success"
        ((SUCCESS_COUNT++))
    else
        echo "  ✗ Failed"
        ((FAIL_COUNT++))
    fi
done

echo ""
echo "======================================"
echo "Summary"
echo "======================================"
echo "✓ Success: $SUCCESS_COUNT repositories"
echo "✗ Failed: $FAIL_COUNT repositories"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo "✓ All secrets set successfully!"
else
    echo "⚠ Some secrets failed to set. Check your GitHub CLI authentication and repository access."
fi
