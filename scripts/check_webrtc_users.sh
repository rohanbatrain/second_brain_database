#!/bin/bash

# Manual WebRTC Test User Verification Script
# This script helps you verify the emails and get JWT tokens

API_URL="http://localhost:8000"

echo "🔍 WebRTC Test User Status Check"
echo "================================="
echo ""

# Check if users can login (should fail if not verified)
echo "👤 Checking User 1 (webrtc_user1):"
response1=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"webrtc_user1","password":"TestPass123!"}')

if echo "$response1" | grep -q "Email not verified"; then
    echo "   ❌ Email not verified"
elif echo "$response1" | grep -q "access_token"; then
    echo "   ✅ Email verified - can login"
    USER1_TOKEN=$(echo "$response1" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('access_token', ''))" 2>/dev/null)
else
    echo "   ❓ Unexpected response: $response1"
fi

echo ""
echo "👤 Checking User 2 (webrtc_user2):"
response2=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"webrtc_user2","password":"TestPass456!"}')

if echo "$response2" | grep -q "Email not verified"; then
    echo "   ❌ Email not verified"
elif echo "$response2" | grep -q "access_token"; then
    echo "   ✅ Email verified - can login"
    USER2_TOKEN=$(echo "$response2" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('access_token', ''))" 2>/dev/null)
else
    echo "   ❓ Unexpected response: $response2"
fi

echo ""
echo "🔧 Manual Verification Instructions"
echo "==================================="
echo ""
echo "If emails are not verified, you need to:"
echo ""
echo "1. 📧 Check your email server logs for verification emails"
echo "2. 🔗 Click the verification links, OR"
echo "3. 🛠️  Use the verification tokens from the database"
echo ""
echo "To get verification tokens from database, run:"
echo "   mongosh --eval 'db.users.find({username:{\$in:[\"webrtc_user1\",\"webrtc_user2\"]}}, {username:1, verification_token:1, is_verified:1})'"
echo ""
echo "Then verify manually:"
echo "   curl -X POST $API_URL/auth/verify-email -H 'Content-Type: application/json' -d '{\"token\": \"YOUR_TOKEN\"}'"
echo ""

# If both users are verified, show tokens
if [ -n "$USER1_TOKEN" ] && [ -n "$USER2_TOKEN" ]; then
    echo "🎉 Both users verified! Here are your JWT tokens:"
    echo ""
    echo "USER 1 TOKEN (webrtc_user1):"
    echo "$USER1_TOKEN"
    echo ""
    echo "USER 2 TOKEN (webrtc_user2):"
    echo "$USER2_TOKEN"
    echo ""
    echo "🌐 Ready for WebRTC testing!"
    echo "   Open webrtc_test.html in TWO browser windows"
    echo "   Paste the tokens and test video chat!"
else
    echo "⏳ Waiting for email verification..."
    echo "   Run this script again after verifying emails"
fi