#!/bin/bash

# This script is used to create a plan in the system.
# If the response status is 201, it indicates that the plan was added successfully.
# Example of a successful response:
# {
#   "message": "Plan 'Premium' added successfully.",
#   "plan_id": "676fc988e511d1b3ba39f764",
#   "status": "success"
# }
# If the response status is forbidden, it indicates that the user does not have the required privileges.
# Example of a forbidden response:
# {
#   "message": "You do not have the required privileges.",
#   "status": "forbidden"
# }


TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0dXNlckBleGFtcGxlLmNvbSIsInVzZXJuYW1lIjoidGVzdHVzZXIiLCJlbWFpbCI6InRlc3R1c2VyQGV4YW1wbGUuY29tIiwiZXhwIjoxNzQ4MzM5MDgwfQ.iV8Txdw-W3-NnxtlU61bj3ehK68fh-aBLArOhKtPRwA"

curl -X POST http://localhost:5000/admin/plan/create_plan \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "name": "Premium",
        "team_limit": 10,
        "project_limit": 5,
        "task_limit_per_project": 50,
        "description": "Premium plan with extended features"
    }'


