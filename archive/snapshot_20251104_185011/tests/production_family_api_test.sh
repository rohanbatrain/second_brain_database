#!/bin/bash

# Production Family Management API Test Suite
# This script performs comprehensive end-to-end testing of the family management system
# using real API calls to validate production readiness

set -e  # Exit on any error

# Configuration
BASE_URL="http://localhost:8000"
TEST_USER_EMAIL="test_family_user@example.com"
TEST_USER_USERNAME="test_family_user"
TEST_USER_PASSWORD="TestPassword123!"
INVITEE_EMAIL="invitee@example.com"
INVITEE_USERNAME="invitee_user"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TOTAL_TESTS=0

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    ((TESTS_PASSED++))
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    ((TESTS_FAILED++))
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

test_endpoint() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_status="$5"
    local headers="$6"
    
    ((TOTAL_TESTS++))
    log_info "Testing: $test_name"
    
    if [ -n "$headers" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BASE_URL$endpoint" \
                   -H "Content-Type: application/json" \
                   -H "$headers" \
                   -d "$data" 2>/dev/null || echo -e "\n000")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BASE_URL$endpoint" \
                   -H "Content-Type: application/json" \
                   -d "$data" 2>/dev/null || echo -e "\n000")
    fi
    
    # Split response and status code
    body=$(echo "$response" | head -n -1)
    status=$(echo "$response" | tail -n 1)
    
    if [ "$status" = "$expected_status" ]; then
        log_success "$test_name - Status: $status"
        echo "$body"
        return 0
    else
        log_error "$test_name - Expected: $expected_status, Got: $status"
        echo "Response: $body"
        return 1
    fi
}

# Global variables for test data
ACCESS_TOKEN=""
FAMILY_ID=""
INVITATION_ID=""
INVITEE_TOKEN=""

echo "=========================================="
echo "Family Management API Production Test Suite"
echo "=========================================="

# Test 1: Health Check
log_info "=== HEALTH CHECK ==="
test_endpoint "Health Check" "GET" "/health" "" "200"

# Test 2: User Registration
log_info "=== USER MANAGEMENT ==="
test_endpoint "User Registration" "POST" "/auth/register" \
    "{\"username\":\"$TEST_USER_USERNAME\",\"email\":\"$TEST_USER_EMAIL\",\"password\":\"$TEST_USER_PASSWORD\"}" \
    "201"

# Test 3: User Login
login_response=$(test_endpoint "User Login" "POST" "/auth/login" \
    "{\"username\":\"$TEST_USER_USERNAME\",\"password\":\"$TEST_USER_PASSWORD\"}" \
    "200")

# Extract access token
ACCESS_TOKEN=$(echo "$login_response" | jq -r '.access_token' 2>/dev/null || echo "")
if [ -z "$ACCESS_TOKEN" ] || [ "$ACCESS_TOKEN" = "null" ]; then
    log_error "Failed to extract access token from login response"
    exit 1
fi
log_success "Access token extracted successfully"

# Test 4: Register invitee user
test_endpoint "Invitee Registration" "POST" "/auth/register" \
    "{\"username\":\"$INVITEE_USERNAME\",\"email\":\"$INVITEE_EMAIL\",\"password\":\"$TEST_USER_PASSWORD\"}" \
    "201"

# Login invitee to get token
invitee_login_response=$(test_endpoint "Invitee Login" "POST" "/auth/login" \
    "{\"username\":\"$INVITEE_USERNAME\",\"password\":\"$TEST_USER_PASSWORD\"}" \
    "200")

INVITEE_TOKEN=$(echo "$invitee_login_response" | jq -r '.access_token' 2>/dev/null || echo "")

# Test 5: Family Creation
log_info "=== FAMILY CREATION ==="
family_response=$(test_endpoint "Create Family" "POST" "/family/create" \
    "{\"name\":\"Test Production Family\"}" \
    "201" \
    "Authorization: Bearer $ACCESS_TOKEN")

FAMILY_ID=$(echo "$family_response" | jq -r '.family_id' 2>/dev/null || echo "")
if [ -z "$FAMILY_ID" ] || [ "$FAMILY_ID" = "null" ]; then
    log_error "Failed to extract family_id from creation response"
    exit 1
fi
log_success "Family created with ID: $FAMILY_ID"

# Test 6: Get User Families
log_info "=== FAMILY RETRIEVAL ==="
test_endpoint "Get User Families" "GET" "/family/my-families" \
    "" \
    "200" \
    "Authorization: Bearer $ACCESS_TOKEN"

# Test 7: Get Family Members
test_endpoint "Get Family Members" "GET" "/family/$FAMILY_ID/members" \
    "" \
    "200" \
    "Authorization: Bearer $ACCESS_TOKEN"

# Test 8: Family Limits Check
test_endpoint "Check Family Limits" "GET" "/family/limits" \
    "" \
    "200" \
    "Authorization: Bearer $ACCESS_TOKEN"

# Test 9: Family Invitation
log_info "=== FAMILY INVITATIONS ==="
invitation_response=$(test_endpoint "Send Family Invitation" "POST" "/family/$FAMILY_ID/invite" \
    "{\"identifier\":\"$INVITEE_EMAIL\",\"relationship_type\":\"sibling\",\"identifier_type\":\"email\"}" \
    "201" \
    "Authorization: Bearer $ACCESS_TOKEN")

INVITATION_ID=$(echo "$invitation_response" | jq -r '.invitation_id' 2>/dev/null || echo "")
if [ -z "$INVITATION_ID" ] || [ "$INVITATION_ID" = "null" ]; then
    log_warning "Could not extract invitation_id, continuing with other tests"
else
    log_success "Invitation created with ID: $INVITATION_ID"
fi

# Test 10: Accept Invitation (if we have invitation ID)
if [ -n "$INVITATION_ID" ] && [ "$INVITATION_ID" != "null" ]; then
    test_endpoint "Accept Family Invitation" "POST" "/family/invitations/$INVITATION_ID/respond" \
        "{\"action\":\"accept\"}" \
        "200" \
        "Authorization: Bearer $INVITEE_TOKEN"
fi

# Test 11: SBD Token Integration
log_info "=== SBD TOKEN INTEGRATION ==="
test_endpoint "Get Family SBD Balance" "GET" "/family/$FAMILY_ID/sbd/balance" \
    "" \
    "200" \
    "Authorization: Bearer $ACCESS_TOKEN"

# Test 12: Token Request Creation
token_request_response=$(test_endpoint "Create Token Request" "POST" "/family/$FAMILY_ID/sbd/request-tokens" \
    "{\"amount\":100,\"reason\":\"Test token request\",\"urgency\":\"medium\"}" \
    "201" \
    "Authorization: Bearer $ACCESS_TOKEN")

# Test 13: Family Notifications
log_info "=== NOTIFICATION SYSTEM ==="
test_endpoint "Get Family Notifications" "GET" "/family/$FAMILY_ID/notifications" \
    "" \
    "200" \
    "Authorization: Bearer $ACCESS_TOKEN"

test_endpoint "Get Notification Preferences" "GET" "/family/notifications/preferences" \
    "" \
    "200" \
    "Authorization: Bearer $ACCESS_TOKEN"

# Test 14: Family Health Monitoring
log_info "=== HEALTH MONITORING ==="
test_endpoint "Family Health Check" "GET" "/family/health" \
    "" \
    "200" \
    "Authorization: Bearer $ACCESS_TOKEN"

test_endpoint "Family Admin Health Check" "GET" "/family/admin/health" \
    "" \
    "200" \
    "Authorization: Bearer $ACCESS_TOKEN"

# Test 15: Security and Rate Limiting
log_info "=== SECURITY TESTING ==="
# Test rate limiting by making multiple rapid requests
for i in {1..3}; do
    test_endpoint "Rate Limit Test $i" "GET" "/family/limits" \
        "" \
        "200" \
        "Authorization: Bearer $ACCESS_TOKEN"
done

# Test 16: Error Handling
log_info "=== ERROR HANDLING ==="
test_endpoint "Invalid Family ID" "GET" "/family/invalid_family_id/members" \
    "" \
    "404" \
    "Authorization: Bearer $ACCESS_TOKEN"

test_endpoint "Unauthorized Access" "GET" "/family/$FAMILY_ID/members" \
    "" \
    "401" \
    ""

# Test 17: Performance Testing
log_info "=== PERFORMANCE TESTING ==="
start_time=$(date +%s%N)
test_endpoint "Performance Test - Family Retrieval" "GET" "/family/my-families" \
    "" \
    "200" \
    "Authorization: Bearer $ACCESS_TOKEN"
end_time=$(date +%s%N)
duration=$(( (end_time - start_time) / 1000000 ))
log_info "Response time: ${duration}ms"

if [ $duration -lt 1000 ]; then
    log_success "Performance test passed - Response time under 1000ms"
    ((TESTS_PASSED++))
else
    log_error "Performance test failed - Response time over 1000ms: ${duration}ms"
    ((TESTS_FAILED++))
fi
((TOTAL_TESTS++))

# Test 18: Concurrent User Testing
log_info "=== CONCURRENT ACCESS TESTING ==="
# Test concurrent access to the same family
for i in {1..3}; do
    (test_endpoint "Concurrent Test $i" "GET" "/family/$FAMILY_ID/members" \
        "" \
        "200" \
        "Authorization: Bearer $ACCESS_TOKEN") &
done
wait

# Test 19: Data Validation
log_info "=== DATA VALIDATION ==="
test_endpoint "Invalid Family Name" "POST" "/family/create" \
    "{\"name\":\"\"}" \
    "422" \
    "Authorization: Bearer $ACCESS_TOKEN"

test_endpoint "Invalid Relationship Type" "POST" "/family/$FAMILY_ID/invite" \
    "{\"identifier\":\"test@example.com\",\"relationship_type\":\"invalid_type\",\"identifier_type\":\"email\"}" \
    "422" \
    "Authorization: Bearer $ACCESS_TOKEN"

# Test 20: Cleanup and Final Validation
log_info "=== CLEANUP AND VALIDATION ==="
# Verify family still exists and is accessible
test_endpoint "Final Family Validation" "GET" "/family/$FAMILY_ID/members" \
    "" \
    "200" \
    "Authorization: Bearer $ACCESS_TOKEN"

# Summary
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo "Total Tests: $TOTAL_TESTS"
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"
echo "Success Rate: $(( TESTS_PASSED * 100 / TOTAL_TESTS ))%"

if [ $TESTS_FAILED -eq 0 ]; then
    log_success "ALL TESTS PASSED! Family Management System is production ready."
    exit 0
else
    log_error "$TESTS_FAILED tests failed. Review the failures above."
    exit 1
fi