# Family Invitations — Flutter integration guide

This document describes the backend contract for family invitations and how the Flutter app should integrate with it.

Status
- Date: 2025-10-23
- Backend branch: `adding-family-support`
- Contract decision: Option B — the server does NOT return the raw invitation token in the immediate POST response. The token is delivered via email to the invitee. The POST response includes authoritative metadata (invitation_id, created_at, expires_at, relationship_type, invitee/email/username where available).

Why this choice
- Security: tokens are secrets that grant acceptance rights. Not returning them in API responses reduces the attack surface (less chance of leaks via logs, proxies, or compromised front-ends).
- Privacy: token circulation is limited to the invitee's email channel and admin listing views (if implemented securely).

Summary of endpoints (relevant)

1) POST /family/{family_id}/invite
- Auth: authenticated user (must be family admin)
- Body: InviteMemberRequest
  - identifier: string (email or username)
  - relationship_type: string
  - identifier_type: optional ("email" | "username"), default: "email"

- Successful response (201): InvitationResponse (no token)
  - invitation_id: string
  - family_name: string
  - inviter_username: string
  - invitee_email?: string
  - invitee_username?: string
  - relationship_type: string
  - status: "pending"
  - expires_at: ISO8601 timestamp
  - created_at: ISO8601 timestamp

Example:
{
  "invitation_id": "inv_abcdef123456",
  "family_name": "Smith Family",
  "inviter_username": "alice",
  "invitee_email": "bob@example.com",
  "relationship_type": "child",
  "status": "pending",
  "expires_at": "2025-10-30T14:30:00Z",
  "created_at": "2025-10-23T14:30:00Z"
}

Notes for Flutter:
- The POST will not contain `invitation_token` — do not expect it.
- After sending the invite, the app should refresh the family invitations list (GET /family/{family_id}/invitations) to show the pending invitation.
- Redirects and link generation for the invitee happen via email. If your UX needs to show the raw link to the admin, coordinate with backend to provide a secure admin-only flow (see "Optional on-demand token flow" below).

2) GET /family/{family_id}/invitations
- Auth: authenticated user. Only admins will receive the list of invitations; non-admins get an empty list.
- Successful response (200): List<InvitationResponse>
- Each list item includes created_at and expires_at.

3) GET /family/my-invitations
- Auth: authenticated user
- Returns invitations where the current user is the invitee (matching invitee_user_id or invitee_email).
- Response items include `invitation_token` only in ReceivedInvitationResponse (used for email token accept/decline flows), because the receiver legitimately needs the token for the email link acceptance flow.

Security & operational guidance for Flutter team
- Always call APIs over HTTPS.
- Do not persist raw tokens on the client (in local storage, logging, analytics, or crash reports).
- When displaying created_at/expires_at, ensure proper timezone handling — treat timestamps as UTC and format for the device locale.
- Handle 403/403-like cases gracefully:
  - POST invite can return 403 with "INSUFFICIENT_PERMISSIONS" if the user is not admin.
  - POST invite can return 403 "MEMBER_LIMIT_EXCEEDED" when the family is full.
  - Frontend should show user-friendly messages for these codes.
- If you need to display an invitation link in the admin UI, request a secure change from backend (see optional flow). Avoid building URLs by concatenating tokens returned from non-secure channels.

Error handling examples
- 400 Invalid relationship: show the returned message and keep the form open for correction.
- 404 Family not found: show a recoverable error (family may have been deleted).
- 429 Rate limit exceeded: show a retry message with suggested cooldown (backend often returns retry information in detail payload).

UX recommendations
- After a successful invite, show a success toast and refresh the invitations list.
- If email delivery fails (server may return email_sent=false in the manager log), show a subtle notification to admins that delivery may be delayed.
- In the invitations list, order by created_at (newest first) and show human-friendly relative timestamps.

Optional on-demand token flow (future enhancement)
If the product team wants admins to copy an invite link immediately, backend can implement a secure on-demand flow:
- Admin-only endpoint: POST /family/{family_id}/invitations/{invitation_id}/reveal-token
- Requirements:
  - Only return token to the original inviter (authenticated check)
  - Require an explicit request flag or a second confirmation step from the UI
  - Log an audit event (but redact the token in logs)
  - Limit to one-time retrieval and short TTL
  - Optionally require 2FA for admin users before allowing reveal

If you want this, the Flutter team should design a small confirmation dialog ("Reveal invitation link — this token is sensitive, show only if you trust this device") before calling the endpoint.

Migration / backwards-compat notes
- Some older clients might have expected `created_at` to equal `expires_at` due to a bug; the backend is now fixed to return authoritative created_at. Ensure the Flutter app uses `created_at` (not `expires_at`) for display.

Contact & follow-up
- Backend owner: rohanbatra
- Repo: second_brain_database (branch: adding-family-support)

---
Document generated: 2025-10-23
