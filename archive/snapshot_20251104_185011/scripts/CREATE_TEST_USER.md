Create test user and permanent token

This repo includes a small helper script: `scripts/create_test_user.py`.

What it does
- Registers a new user by calling POST /auth/register on the server.
- Uses the returned JWT access token to call POST /auth/permanent-tokens and create a permanent token.

Usage
1. Ensure the server is running and reachable (default examples use http://localhost:8001).
2. Run the script (zsh / macOS):

```bash
python3 scripts/create_test_user.py \
  --base-url http://localhost:8001 \
  --username test_user \
  --email test_user@example.com \
  --password 'TestPass123!' \
  --token-desc 'local dev token' \
  --ip-restrictions 127.0.0.1/32
```

Output
- The script prints the registration response and the permanent token JSON. The permanent token value is returned only once by the server — copy and store it in a secure place.

Security notes
- Do NOT commit generated tokens to version control.
- Use `--ip-restrictions` for safety in local/testing environments.
- Avoid running this against production systems.

If you want, I can run the script for you now (if your local server is running). If yes, tell me the base URL to use or confirm http://localhost:8001 and whether to run it now and what username/email/password to use.