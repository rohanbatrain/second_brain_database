#!/bin/bash
Token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0dXNlckBleGFtcGxlLmNvbSIsInVzZXJuYW1lIjoidGVzdHVzZXIiLCJlbWFpbCI6InRlc3R1c2VyQGV4YW1wbGUuY29tIiwiZXhwIjoxNzQ4MzM5MDgwfQ.iV8Txdw-W3-NnxtlU61bj3ehK68fh-aBLArOhKtPRwA"
curl -X POST http://localhost:5000/admin/plan/update_plan \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $Token" \
-d '{
    "name": "Premium",
    "project_limit": 10
}'

