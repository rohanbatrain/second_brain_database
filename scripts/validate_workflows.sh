#!/bin/bash
#
# Workflow Validation Script
# Checks that all required workflow files exist across all submodules

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUBMODULES_DIR="$BASE_DIR/submodules"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SUCCESS_COUNT=0
FAIL_COUNT=0

echo "======================================"
echo "Workflow Validation Report"
echo "======================================"
echo ""

# Next.js submodules
NEXTJS_SUBMODULES=(
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
)

echo "Checking Next.js submodules..."
echo "------------------------------"
for submodule in "${NEXTJS_SUBMODULES[@]}"; do
  echo "📦 $submodule"
  
  # Check docker-dev.yml
  if [ -f "$SUBMODULES_DIR/$submodule/.github/workflows/docker-dev.yml" ]; then
    echo -e "  ${GREEN}✓${NC} docker-dev.yml exists"
    ((SUCCESS_COUNT++))
  else
    echo -e "  ${RED}✗${NC} docker-dev.yml MISSING"
    ((FAIL_COUNT++))
  fi
  
  # Check docker-prod.yml
  if [ -f "$SUBMODULES_DIR/$submodule/.github/workflows/docker-prod.yml" ]; then
    echo -e "  ${GREEN}✓${NC} docker-prod.yml exists"
    ((SUCCESS_COUNT++))
    
    # Verify it includes Docker Hub
    if grep -q "REGISTRY_DOCKERHUB" "$SUBMODULES_DIR/$submodule/.github/workflows/docker-prod.yml"; then
      echo -e "  ${GREEN}✓${NC} Docker Hub support configured"
      ((SUCCESS_COUNT++))
    else
      echo -e "  ${YELLOW}⚠${NC} Docker Hub support NOT configured"
      ((FAIL_COUNT++))
    fi
    
    # Verify semver tagging
    if grep -q "type=semver" "$SUBMODULES_DIR/$submodule/.github/workflows/docker-prod.yml"; then
      echo -e "  ${GREEN}✓${NC} Semantic versioning configured"
      ((SUCCESS_COUNT++))
    else
      echo -e "  ${YELLOW}⚠${NC} Semantic versioning NOT configured"
      ((FAIL_COUNT++))
    fi
  else
    echo -e "  ${RED}✗${NC} docker-prod.yml MISSING"
    ((FAIL_COUNT++))
  fi
  
  echo ""
done

echo ""
echo "Checking Flutter submodule..."
echo "------------------------------"
echo "📦 sbd-flutter-emotion_tracker"

if [ -f "$SUBMODULES_DIR/sbd-flutter-emotion_tracker/.github/workflows/Release.yml" ]; then
  echo -e "  ${GREEN}✓${NC} Release.yml exists"
  ((SUCCESS_COUNT++))
  
  # Verify tag-based trigger
  if grep -q "tags:" "$SUBMODULES_DIR/sbd-flutter-emotion_tracker/.github/workflows/Release.yml"; then
    echo -e "  ${GREEN}✓${NC} Tag-based releases configured"
    ((SUCCESS_COUNT++))
  else
    echo -e "  ${YELLOW}⚠${NC} Still using branch-based releases"
    ((FAIL_COUNT++))
  fi
else
  echo -e "  ${RED}✗${NC} Release.yml MISSING"
  ((FAIL_COUNT++))
fi

echo ""
echo "Checking n8n Node.js submodule..."
echo "------------------------------"
echo "📦 n8n-nodes-second-brain-database"

for workflow in "docker-dev" "docker-main" "release"; do
  if [ -f "$SUBMODULES_DIR/n8n-nodes-second-brain-database/.github/workflows/${workflow}.yml" ]; then
    echo -e "  ${GREEN}✓${NC} ${workflow}.yml exists"
    ((SUCCESS_COUNT++))
  else
    echo -e "  ${RED}✗${NC} ${workflow}.yml MISSING"
    ((FAIL_COUNT++))
  fi
done

echo ""
echo "Checking MkDocs submodule..."
echo "------------------------------"
echo "📦 sbd-mkdocs"

for workflow in "deploy-dev" "deploy-main"; do
  if [ -f "$SUBMODULES_DIR/sbd-mkdocs/.github/workflows/${workflow}.yml" ]; then
    echo -e "  ${GREEN}✓${NC} ${workflow}.yml exists"
    ((SUCCESS_COUNT++))
  else
    echo -e "  ${RED}✗${NC} ${workflow}.yml MISSING"
    ((FAIL_COUNT++))
  fi
done

echo ""
echo "======================================"
echo "Summary"
echo "======================================"
echo -e "${GREEN}Success:${NC} $SUCCESS_COUNT checks passed"
echo -e "${RED}Failed:${NC} $FAIL_COUNT checks failed"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
  echo -e "${GREEN}✓ All workflows are properly configured!${NC}"
  exit 0
else
  echo -e "${RED}✗ Some workflows are missing or misconfigured!${NC}"
  exit 1
fi
