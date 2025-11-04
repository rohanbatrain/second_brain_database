# Family Shop & Wallet Integration: Technical Requirements & Codebase Plan

**Date:** 2025-10-23
**Status:** Sprint-Ready Requirements & Architecture

---

## 1. Overview
A new, fully separate Family Shop module will be implemented in the Flutter app. This module enables family members to purchase all shop items using a shared family wallet, with admin approval flows and real-time updates. The design is modular, scalable, and aligns with the production-ready guide.

---

## 2. Key Requirements

### UI/UX
- Dedicated entry point (tab/menu) for Family Shop.
- Separate screens for family members and admins.
- UI mirrors current shop for consistency, with clear family wallet branding.

### Feature Scope
- Supports all item types: avatars, banners, themes, bundles, currency.
- Only family wallet can be used for purchases in the family shop.

### Permissions
- Only family members can access the family shop.
- Admin features (approval/denial) are visible only to family admins.

### Notifications
- In-app real-time notifications (WebSocket) for purchase requests and approvals/denials.

---

## 3. Codebase Issues & Gaps
- Existing shop logic is single-user only; no family wallet, purchase request, or admin approval flows.
- No models for family wallet, purchase requests, or payment options.
- No real-time (WebSocket/polling) logic for purchase request updates.
- Error handling is not centralized for new flows.
- State management (Riverpod) is present, but not for family shop or wallet.
- No UI for family shop, admin dashboard, or approval dialogs.

---

## 4. Architecture & Folder Structure

```
lib/
  screens/
    family_shop/
      family_shop_screen.dart         # Main family shop UI
      admin_dashboard_screen.dart     # Admin-only dashboard
      purchase_request_dialog.dart    # Dialog for approval/denial
      ... (tabs/widgets for item types)
  providers/
    family_shop_provider.dart         # API and state logic
    family_wallet_provider.dart       # Wallet state, permissions
    purchase_request_notifier.dart    # Purchase request state
  models/
    family_shop/
      purchase_request.dart           # Data model
      payment_option.dart             # Data model
      ...
  utils/
    family_shop_error_mapper.dart     # Central error code mapping
```

---

## 5. API Service Layer
- Use `dio` for all new endpoints.
- Service classes for:
  - Payment options (`GET /shop/payment-options`)
  - Purchase (`POST /shop/purchase`)
  - Purchase requests (list, approve, deny)
  - Owned items (`GET /avatars/owned`)

---

## 6. State Management
- Riverpod notifiers/providers for:
  - Family shop state (items, payment options)
  - Purchase requests (list, status)
  - Real-time updates (WebSocket/polling)
  - Wallet state (balance, permissions)

---

## 7. UI Flows
- Family shop screen (mirrors existing shop, adds family wallet logic)
- Purchase dialogs (approval, error, success)
- Admin dashboard (pending requests, approve/deny)
- Notification system (real-time and fallback)

---

## 8. Real-Time Updates
- WebSocket integration for family events.
- Polling fallback for reliability.

---

## 9. Error Handling
- Centralized error code to UI message mapping for all new flows.

---

## 10. Integration & QA
- Staging config, test data, and sandbox endpoints for end-to-end testing.

---

## 11. Next Steps
1. Scaffold folder/file structure and stubs.
2. Define models for all new data types.
3. Implement API service with `dio`.
4. Set up Riverpod providers/notifiers.
5. Draft UI screens and dialogs.
6. Integrate WebSocket and polling.
7. Centralize error handling.
8. Prepare QA plan and test data.

---

**This document is the single source of truth for the Family Shop sprint.**
