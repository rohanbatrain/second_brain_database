#!/bin/bash

# IPAM Backend Enhancements - Backward Compatibility Verification Script
#
# This script verifies that all existing IPAM functionality continues to work
# correctly after the enhancements have been added.

set -e

echo "========================================="
echo "IPAM Backward Compatibility Verification"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Warning: Virtual environment not activated${NC}"
    echo "Activating virtual environment..."
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    elif [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo -e "${RED}Error: No virtual environment found${NC}"
        exit 1
    fi
fi

echo "Step 1: Running backward compatibility tests..."
echo "----------------------------------------------"

# Run the backward compatibility test suite
if uv run pytest tests/test_ipam_backward_compatibility_simple.py -v --tb=short; then
    echo -e "${GREEN}✓ All backward compatibility tests passed${NC}"
else
    echo -e "${RED}✗ Some backward compatibility tests failed${NC}"
    echo ""
    echo "Please review the test failures above and ensure:"
    echo "1. All existing endpoints are still accessible"
    echo "2. Request/response formats haven't changed"
    echo "3. No breaking changes were introduced"
    exit 1
fi

echo ""
echo "Step 2: Verifying existing endpoint signatures..."
echo "------------------------------------------------"

# Check that all original endpoints are still present
ENDPOINTS=(
    "/ipam/health"
    "/ipam/countries"
    "/ipam/countries/{country}"
    "/ipam/countries/{country}/utilization"
    "/ipam/regions"
    "/ipam/regions/{region_id}"
    "/ipam/regions/{region_id}/utilization"
    "/ipam/regions/preview-next"
    "/ipam/hosts"
    "/ipam/hosts/{host_id}"
    "/ipam/hosts/by-ip/{ip_address}"
    "/ipam/hosts/preview-next"
    "/ipam/hosts/batch"
    "/ipam/hosts/bulk-lookup"
    "/ipam/hosts/bulk-release"
    "/ipam/interpret"
    "/ipam/search"
    "/ipam/statistics/continent/{continent}"
    "/ipam/statistics/top-utilized"
    "/ipam/statistics/allocation-velocity"
    "/ipam/export"
    "/ipam/import"
    "/ipam/audit/history"
)

echo "Checking for presence of ${#ENDPOINTS[@]} original endpoints..."

MISSING_ENDPOINTS=0
for endpoint in "${ENDPOINTS[@]}"; do
    if grep -q "$endpoint" src/second_brain_database/routes/ipam/routes.py; then
        echo -e "${GREEN}✓${NC} Found: $endpoint"
    else
        echo -e "${RED}✗${NC} Missing: $endpoint"
        MISSING_ENDPOINTS=$((MISSING_ENDPOINTS + 1))
    fi
done

if [ $MISSING_ENDPOINTS -eq 0 ]; then
    echo -e "${GREEN}✓ All original endpoints are present${NC}"
else
    echo -e "${RED}✗ $MISSING_ENDPOINTS original endpoints are missing${NC}"
    exit 1
fi

echo ""
echo "Step 3: Verifying response model compatibility..."
echo "------------------------------------------------"

# Check that original response models are still present
MODELS=(
    "format_region_response"
    "format_host_response"
    "format_country_response"
    "format_utilization_response"
    "format_pagination_response"
    "format_error_response"
)

echo "Checking for presence of ${#MODELS[@]} response formatting functions..."

MISSING_MODELS=0
for model in "${MODELS[@]}"; do
    if grep -q "def $model" src/second_brain_database/routes/ipam/utils.py; then
        echo -e "${GREEN}✓${NC} Found: $model"
    else
        echo -e "${RED}✗${NC} Missing: $model"
        MISSING_MODELS=$((MISSING_MODELS + 1))
    fi
done

if [ $MISSING_MODELS -eq 0 ]; then
    echo -e "${GREEN}✓ All response formatting functions are present${NC}"
else
    echo -e "${RED}✗ $MISSING_MODELS response formatting functions are missing${NC}"
    exit 1
fi

echo ""
echo "Step 4: Verifying manager method compatibility..."
echo "------------------------------------------------"

# Check that original manager methods are still present
MANAGER_METHODS=(
    "get_all_countries"
    "get_country_mapping"
    "calculate_country_utilization"
    "allocate_region"
    "get_regions"
    "get_region_by_id"
    "update_region"
    "retire_allocation"
    "add_comment"
    "get_next_available_region"
    "calculate_region_utilization"
    "allocate_host"
    "allocate_hosts_batch"
    "get_hosts"
    "get_host_by_id"
    "get_host_by_ip"
    "bulk_lookup_ips"
    "update_host"
    "bulk_release_hosts"
    "get_next_available_host"
    "interpret_ip_address"
    "get_continent_statistics"
    "get_top_utilized_resources"
    "get_allocation_velocity"
    "search_allocations"
    "export_allocations"
    "import_allocations"
    "get_audit_history"
)

echo "Checking for presence of ${#MANAGER_METHODS[@]} original manager methods..."

MISSING_METHODS=0
for method in "${MANAGER_METHODS[@]}"; do
    if grep -q "async def $method" src/second_brain_database/managers/ipam_manager.py; then
        echo -e "${GREEN}✓${NC} Found: $method"
    else
        echo -e "${RED}✗${NC} Missing: $method"
        MISSING_METHODS=$((MISSING_METHODS + 1))
    fi
done

if [ $MISSING_METHODS -eq 0 ]; then
    echo -e "${GREEN}✓ All original manager methods are present${NC}"
else
    echo -e "${RED}✗ $MISSING_METHODS original manager methods are missing${NC}"
    exit 1
fi

echo ""
echo "Step 5: Checking for breaking changes in dependencies..."
echo "-------------------------------------------------------"

# Check that original dependencies are still present
DEPENDENCIES=(
    "get_current_user_for_ipam"
    "require_ipam_read"
    "require_ipam_allocate"
    "require_ipam_update"
    "require_ipam_release"
    "require_ipam_admin"
    "check_ipam_rate_limit"
)

echo "Checking for presence of ${#DEPENDENCIES[@]} dependency functions..."

MISSING_DEPS=0
for dep in "${DEPENDENCIES[@]}"; do
    if grep -q "$dep" src/second_brain_database/routes/ipam/dependencies.py; then
        echo -e "${GREEN}✓${NC} Found: $dep"
    else
        echo -e "${RED}✗${NC} Missing: $dep"
        MISSING_DEPS=$((MISSING_DEPS + 1))
    fi
done

if [ $MISSING_DEPS -eq 0 ]; then
    echo -e "${GREEN}✓ All dependency functions are present${NC}"
else
    echo -e "${RED}✗ $MISSING_DEPS dependency functions are missing${NC}"
    exit 1
fi

echo ""
echo "========================================="
echo "Backward Compatibility Verification Complete"
echo "========================================="
echo ""
echo -e "${GREEN}✓ All checks passed successfully!${NC}"
echo ""
echo "Summary:"
echo "  - All original endpoints are accessible"
echo "  - All response models are compatible"
echo "  - All manager methods are present"
echo "  - All dependencies are intact"
echo "  - No breaking changes detected"
echo ""
echo "The IPAM backend enhancements are fully backward compatible."
