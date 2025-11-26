#!/bin/bash
# Automated rollout script for CI/CD enforcement to Next.js submodules
# Usage: ./rollout-nextjs.sh

set -e

echo "🚀 CI/CD Enforcement Rollout for Next.js Submodules"
echo "=================================================="

# Define Next.js submodules
NEXTJS_SUBMODULES=(
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
    "n8n-nodes-second-brain-database"
)

# Base path to templates
TEMPLATE_DIR=".github/shared-configs/templates/nextjs"

# Function to deploy to a single submodule
deploy_to_submodule() {
    local submodule=$1
    local submodule_path="submodules/$submodule"
    
    echo ""
    echo "📦 Processing: $submodule"
    echo "-----------------------------------"
    
    # Check if submodule exists
    if [ ! -d "$submodule_path" ]; then
        echo "⚠️  Directory not found: $submodule_path (skipping)"
        return
    fi
    
    cd "$submodule_path"
    
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        echo "⚠️  Uncommitted changes detected in $submodule (skipping)"
        cd - > /dev/null
        return
    fi
    
    # Create feature branch
    echo "🔀 Creating feature branch..."
    git checkout -b feat/ci-cd-enforcement 2>/dev/null || git checkout feat/ci-cd-enforcement
    
    # Copy configuration files
    echo "📄 Copying configuration files..."
    cp "../../$TEMPLATE_DIR/.pre-commit-config.yaml" .
    cp "../../$TEMPLATE_DIR/commitlint.config.js" .
    
    # Copy CONTRIBUTING.md (update repo name)
sed "s/SBD Next.js Cluster Dashboard/${submodule}/g" \
        "../../submodules/sbd-nextjs-cluster-dashboard/CONTRIBUTING.md" > CONTRIBUTING.md
    
    # Copy GitHub Actions workflows
    echo "⚙️  Copying GitHub Actions workflows..."
    mkdir -p .github/workflows
    cp "../../$TEMPLATE_DIR/ci.yml" .github/workflows/
    cp "../../$TEMPLATE_DIR/pr-labeler.yml" .github/workflows/
    cp "../../$TEMPLATE_DIR/release-please.yml" .github/workflows/
    
    # Setup Husky hooks
    echo "🪝 Setting up Husky hooks..."
    mkdir -p .husky
    cp "../../$TEMPLATE_DIR/husky-commit-msg" .husky/commit-msg
    cp "../../$TEMPLATE_DIR/husky-pre-push" .husky/pre-push
    chmod +x .husky/*
    
    # Update package.json
    echo "📝 Updating package.json..."
    
    # Backup package.json
    cp package.json package.json.bak
    
    # Use Node.js to update package.json
    node -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));

// Update scripts
pkg.scripts = pkg.scripts || {};
pkg.scripts.lint = pkg.scripts.lint || 'next lint';
if (pkg.scripts.lint === 'eslint') {
    pkg.scripts.lint = 'next lint --max-warnings=0';
}
if (!pkg.scripts.lint.includes('--max-warnings')) {
    pkg.scripts.lint = pkg.scripts.lint + ' --max-warnings=0';
}
pkg.scripts['lint:fix'] = 'next lint --fix';
pkg.scripts['type-check'] = 'tsc --noEmit';
pkg.scripts.prepare = 'husky || true';

// Update devDependencies
pkg.devDependencies = pkg.devDependencies || {};
pkg.devDependencies['@commitlint/cli'] = '^19.0.0';
pkg.devDependencies['@commitlint/config-conventional'] = '^19.0.0';
pkg.devDependencies['husky'] = '^9.0.11';

// Write back
fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
"
    
    # Install dependencies
    echo "📦 Installing dependencies..."
    npm install
    
    # Initialize Husky
    echo "🎣 Initializing Husky..."
    npm run prepare || true
    
    # Git add all changes
    echo "✅ Staging changes..."
    git add .
    
    # Commit
    echo "💾 Committing changes..."
    git commit -m "chore: add comprehensive CI/CD enforcement setup

- Add pre-commit hooks (ESLint, Prettier, secret scanning)
- Add commit message validation (commitlint)
- Add branch name and type checking in pre-push hook
- Add GitHub Actions workflows (CI, PR labeler, Release Please)
- Add CONTRIBUTING.md guide
- Update package.json with required scripts and dependencies" || echo "⚠️  Nothing to commit or commit failed"
    
    echo "✅ $submodule completed!"
    
    cd - > /dev/null
}

# Main execution
echo ""
echo "This script will deploy CI/CD enforcement to the following submodules:"
for submodule in "${NEXTJS_SUBMODULES[@]}"; do
    echo "  • $submodule"
done
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted."
    exit 1
fi

# Deploy to each submodule
for submodule in "${NEXTJS_SUBMODULES[@]}"; do
    deploy_to_submodule "$submodule"
done

echo ""
echo "=================================================="
echo "✅ Rollout complete!"
echo ""
echo "Next steps:"
echo "  1. Review changes in each submodule"
echo "  2. Test the hooks and CI workflows"
echo "  3. Push branches: for dir in submodules/*/; do (cd \$dir && git push -u origin feat/ci-cd-enforcement); done"
echo "  4. Create PRs for each submodule"
echo "  5. Configure branch protection rules (see BRANCH_PROTECTION_GUIDE.md)"
echo ""
