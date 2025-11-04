# Account Switcher & Profile Control

Summary
-------
This document describes the new compact account control (avatar + display name) and profile switcher UI added to the app, and what files were created/changed.

User-visible behavior
---------------------
- The sidebar footer now shows a compact Account control instead of a plain "Logout" button.
- Tapping the Account control opens a profile switcher sheet.
- The sheet lists available profiles and a "Logout" action. Selecting a profile switches the current profile in memory; tapping Logout signs the user out and returns to the auth flow.

Files added
-----------
- `lib/models/profile.dart` — Profile model (id, displayName, email, avatarUrl).
- `lib/providers/profiles_provider.dart` — Minimal ProfilesNotifier that holds a list of profiles and the selected profile. It reads a fallback display name from secure storage and exposes switch/add/logout methods.
- `lib/widgets/account_button.dart` — The compact avatar + account-name widget that opens the profile sheet.
- `lib/widgets/profile_switcher_sheet.dart` — Modal bottom sheet listing profiles and containing the Logout button.

Files modified
--------------
- `lib/widgets/sidebar_widget.dart` — Replaced the previous logout button in the footer with the new `AccountButton` control. The detailed logout confirmation dialog previously in the sidebar was removed, as logout is now handled by the profile sheet.
- `lib/providers/family/family_provider.dart` — Defensive change: treat 403 from admin-only pending-token-requests endpoint as empty pending list for non-admins.
- `lib/screens/settings/account/family/sbd_account_screen.dart` — Safer defaults for missing spending permissions (avoid misleading default true values).

Provider contracts
------------------
- `profilesProvider` (StateNotifierProvider<ProfilesNotifier, ProfilesState>)
  - state: { profiles: List<Profile>, current: Profile? }
  - methods: `switchTo(profileId)`, `addProfile(profile)`, `logout()`
  - Persistence: minimal; writes keys `'profiles_list'` and `'current_profile_id'` to secure storage (placeholder behavior).

Notes for backend/dev
---------------------
- No backend changes were required for the profile switcher UI. The family/SBD API defensive change relates to client-side handling of 403 responses and was implemented to avoid showing page-level errors to non-admin users.

How to test locally
-------------------
1. Run the app and open the sidebar.
2. Tap the account control in the footer — the profile switcher sheet should appear.
3. Verify profiles load (default profile is created from secure storage user data if present).
4. Tap "Logout" inside the sheet — you should be navigated back to the auth flow.

Next steps / TODOs
------------------
- Persist `profiles_list` as JSON in secure storage and load it reliably.
- Add UI polish: avatar images, initials fallback styling, animations.
- Add widget tests for `AccountButton` and `ProfileSwitcherSheet` (switching + logout flows).
- Consider moving the profile persistence to a dedicated storage model and adding backend sync if multi-device support is desired.

