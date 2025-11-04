# Family Shop Integration & Testing Plan

## Staging & QA
- Use staging baseURL and API token with admin/member roles
- Provide sample `family_id`, `user_id` pairs and sample request entries
- Optionally provide a sandbox endpoint that auto-approves for end-to-end QA

## Test Data
- Example family wallet with balance
- Example purchase requests (pending, approved, denied)
- Example items (avatars, banners, etc.)

## Integration Steps
1. Scaffold new module and providers
2. Implement API service and models
3. Build UI screens and dialogs
4. Integrate WebSocket and polling
5. Map error codes and test error flows
6. Run end-to-end tests on staging
