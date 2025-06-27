# Trusted IP Lockdown: Usage Guide

## What is Trusted IP Lockdown?

Trusted IP Lockdown is a security feature designed for users who access their accounts from static IP addresses or through a consistent VPN endpoint. When enabled, it restricts sensitive account actions (such as login, password changes, or other protected operations) to only the IP addresses you explicitly trust. This helps prevent unauthorized access, even if your password or token is compromised, by ensuring only requests from your approved IPs are allowed.

**Who should use this?**
- Users with a static home or office IP address.
- Users who always connect through a specific VPN endpoint.
- Anyone who wants to add an extra layer of protection to their account by limiting access to known, trusted locations.

**Why is this here?**
- To provide an additional, IP-based layer of security beyond passwords and 2FA.
- To help prevent account takeovers from new or unexpected locations.
- To give you control over which networks/devices can access your account, especially useful for high-security or compliance needs.

---

## 1. Initiate Lockdown Request

**Endpoint:**
`POST /auth/trusted-ips/lockdown-request`

**Headers:**
- `Authorization: Bearer <your_access_token>`

**Body Example:**
```json
{
  "action": "enable",  // or "disable"
  "trusted_ips": ["127.0.0.1", "::1"]  // List of IPs allowed to confirm
}
```

**What happens:**
- A confirmation code is emailed to you (visible in the console in development).
- The code is valid for 15 minutes.
- You must confirm from one of the provided IPs.

**Possible errors:**
- `400`: Invalid action or missing/invalid trusted_ips list.
- `429`: Rate limit exceeded (max 5 requests/hour).
- `500`: Email sending failed.

---

## 2. Confirm Lockdown

**Endpoint:**
`POST /auth/trusted-ips/lockdown-confirm`

**Headers:**
- `Authorization: Bearer <your_access_token>`

**Body Example:**
```json
{
  "code": "<the_code_from_email>"
}
```

**What happens:**
- If the code and your IP match, lockdown is enabled/disabled and trusted IPs are set.

**Possible errors:**
- `400`: No pending action, code expired, or invalid code.
- `403`: Confirmation must be from one of the allowed IPs.
- `429`: Rate limit exceeded (max 10 requests/hour).

**Troubleshooting:**
- If you get a "Confirmation must be from one of the allowed IPs" error, check your current IP (see below) and ensure it matches one in `trusted_ips`.
- For localhost, FastAPI may see your IP as `127.0.0.1` (IPv4) or `::1` (IPv6). Use the one shown in logs or by a helper endpoint.

---

## 3. Check Lockdown Status

**Endpoint:**
`GET /auth/trusted-ips/lockdown-status`

**Headers:**
- `Authorization: Bearer <your_access_token>`

**Response Example:**
```json
{
  "trusted_ip_lockdown": true,  // or false
  "your_ip": "127.0.0.1"      // The IP address of your current request
}
```

This allows you to verify both the lockdown status and the IP address the backend sees for your request. Use this IP when adding to your trusted IPs list if needed.

---

## 4. (Optional) Find Your Current IP

If you’re unsure which IP to add to `trusted_ips`, you can:
- Check the logs (look for `request_ip` in the log output).
- Add a temporary endpoint to echo your IP:
    ```python
    @router.get("/my-ip")
    async def my_ip(request: Request):
        return {"ip": request.client.host}
    ```
- Or use `curl` to test:
    ```sh
    curl -H "Authorization: Bearer <token>" http://localhost:8000/auth/my-ip
    ```

---

## Why does disabling Trusted IP Lockdown require specifying trusted IPs again?

When you disable Trusted IP Lockdown, you are <b>not</b> asked to provide a list of IPs allowed to confirm the disable action. Instead, for maximum security, the system only allows confirmation from one of your <b>already trusted IPs</b> as stored in your account. This prevents attackers from attempting to override or learn your trusted IPs, and ensures that only a device or network you previously trusted can disable lockdown.

- **No override possible:** The backend ignores any IPs submitted by the user when disabling. Only the IPs already stored as trusted in your account are eligible to confirm the disable action.
- **Prevents session hijack:** Even if your session is compromised, an attacker cannot disable lockdown unless they are connecting from a previously trusted IP.
- **No information leak:** Attackers cannot learn or enumerate your trusted IPs by attempting to disable lockdown.

**In summary:**
> Disabling Trusted IP Lockdown can only be confirmed from a previously trusted IP. You cannot specify or override the set of allowed IPs at disable time. This ensures that only you, from a location you previously trusted, can complete the disable process—even if your session is compromised elsewhere.

**Frontend/UI tip:**
- When presenting the disable form, simply inform the user: "To disable Trusted IP Lockdown, you must confirm from a device or network that is already trusted. For your security, you cannot specify new IPs at this step."
- If confirmation fails, guide the user to check their current IP and compare it to their trusted IPs list (if visible in the UI).

---

## Error Handling Summary

- **400 Bad Request:** Invalid action, missing/invalid trusted_ips, no pending action, code expired, or invalid code.
- **403 Forbidden:** Confirmation from disallowed IP.
- **429 Too Many Requests:** Rate limit exceeded.
- **500 Internal Server Error:** Email sending or unexpected error.

---

## Example curl Commands

**Request code:**
```sh
curl -X POST http://localhost:8000/auth/trusted-ips/lockdown-request \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"action":"enable","trusted_ips":["127.0.0.1"]}'
```

**Confirm lockdown:**
```sh
curl -X POST http://localhost:8000/auth/trusted-ips/lockdown-confirm \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"code":"<code_from_email>"}'
```

**Check status:**
```sh
curl -H "Authorization: Bearer <token>" http://localhost:8000/auth/trusted-ips/lockdown-status
```

---

## Frontend Guidance

- Always use the `Authorization` header (never query params) for authentication.
- Show clear error messages to users based on the error codes above.
- Guide users to check their current IP if confirmation fails.

---

