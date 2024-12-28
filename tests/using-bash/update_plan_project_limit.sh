#!/bin/bash
curl -X POST http://localhost:5000/admin/plan/update_plan \
-H "Content-Type: application/json" \
-d '{
    "name": "Plan Name",
    "project_limit": 10
}'
