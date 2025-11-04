# Frontend Update: Family SBD Account API Changes

**Date:** October 22, 2025
**Version:** 1.1.0
**Priority:** Medium
**Breaking Changes:** No

---

## 🎯 **Summary**

The Family SBD Account API endpoints have been enhanced to include user-friendly account names in addition to technical usernames. This improves the user experience by displaying meaningful account names instead of technical identifiers.

---

## 📋 **Changes Made**

### ✅ **Enhanced Response Fields**

Two key endpoints now include an `account_name` field alongside the existing `account_username`:

#### 1. Available Balance Endpoint
**Endpoint:** `GET /family/{family_id}/sbd-account/available-balance`

**New Response Structure:**
```json
{
  "account_username": "family_abc123_wallet",
  "account_name": "Family Vacation Fund",
  "available_balance": 150.00,
  "frozen": false,
  "permissions": { ... }
}
```

#### 2. Transaction History Endpoint
**Endpoint:** `GET /family/{family_id}/sbd-account/transactions`

**New Response Structure:**
```json
{
  "account_username": "family_abc123_wallet",
  "account_name": "Family Vacation Fund",
  "current_balance": 150.00,
  "transactions": [ ... ],
  "total_transactions": 25,
  "has_more": false
}
```

---

## 🔄 **Migration Guide**

### **Frontend Changes Required**

#### **Display Logic Update**
```typescript
// Before (showing technical username)
const displayName = account.account_username; // "family_abc123_wallet"

// After (showing user-friendly name with fallback)
const displayName = account.account_name || account.account_username;
```

#### **Component Updates**
Update any components that display family account information:

1. **Account Balance Cards** - Use `account_name` for titles
2. **Transaction Lists** - Show account name in headers
3. **Account Selection Dropdowns** - Display friendly names
4. **Settings Pages** - Use account names in labels

#### **Example Implementation**
```typescript
interface FamilyAccount {
  account_username: string;
  account_name?: string; // New field
  available_balance: number;
  // ... other fields
}

function AccountDisplay({ account }: { account: FamilyAccount }) {
  const displayName = account.account_name || account.account_username;

  return (
    <div className="account-card">
      <h3>{displayName}</h3>
      <p>Balance: ${account.available_balance}</p>
    </div>
  );
}
```

---

## 🔧 **Technical Details**

### **Fallback Logic**
- If `account_name` is not set (null/undefined/empty), fall back to `account_username`
- This ensures backward compatibility with existing accounts
- No breaking changes - existing frontend code will continue to work

### **Database Schema**
- New optional `name` field added to family SBD account documents
- Existing accounts will have `account_name` fall back to `account_username`
- Future accounts can have custom names set during creation

### **API Backward Compatibility**
- All existing fields remain unchanged
- New `account_name` field is optional in responses
- No changes to request schemas or authentication

---

## 🧪 **Testing Checklist**

### **Frontend Testing**
- [ ] Verify account names display correctly in balance views
- [ ] Test fallback to username when name is not set
- [ ] Confirm transaction history shows account names
- [ ] Check account selection UI uses friendly names
- [ ] Test with accounts that have names vs those that don't

### **API Integration Testing**
- [ ] Call both endpoints and verify `account_name` field presence
- [ ] Test with families that have custom account names
- [ ] Test with families using default username fallback
- [ ] Verify response structure matches documentation

---

## 📞 **Questions & Support**

If you encounter any issues with these changes:

1. **API Response Issues** - Check that you're accessing the new `account_name` field
2. **Display Problems** - Ensure fallback logic is implemented correctly
3. **Missing Names** - This is expected for existing accounts; names can be added later

**Contact:** Backend Team
**Documentation:** See API docs for complete response schemas

---

## 📈 **Benefits**

- **Better UX**: Users see meaningful account names instead of technical IDs
- **Flexibility**: Accounts can have custom names for different purposes
- **Backward Compatible**: Existing integrations continue to work
- **Future-Proof**: Foundation for account management features

---

**Next Steps:**
1. Update frontend components to use `account_name`
2. Test the changes in development environment
3. Deploy frontend changes alongside backend updates
4. Consider adding account name management UI in future releases

---

**Document Version:** 1.0
**Last Updated:** October 22, 2025</content>
<parameter name="filePath">/Users/rohan/Documents/repos/second_brain_database/docs/frontend_update_family_account_names.md