# Family SBD Account API Changes

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
**Endpoint:** `GET /family/{family_id}/sbd-account`

**New Response Structure:**
```json
{
  "account_id": "fam-acct_123",
  "account_username": "family_vacation_fund_123",
  "account_name": "Vacation Fund",
  "family_id": "family_123",
  "balance": 1000,
  "currency": "SBD",
  "is_frozen": false,
  "freeze_reason": null,
  "member_permissions": {
    "user_1": {
      "daily_limit": 100,
      "weekly_limit": 500,
      "can_send": true,
      "can_request": true
    }
  },
  "updated_at": "2025-10-22T10:00:00Z"
}
```

#### 2. Transaction History Endpoint
**Endpoint:** `GET /family/{family_id}/sbd-account/transactions`

**New Response Structure:**
```json
{
  "account_username": "family_vacation_fund_123",
  "account_name": "Vacation Fund",
  "current_balance": 1000,
  "transactions": [
    {
      "transaction_id": "tx_678",
      "type": "transfer",
      "amount": 50,
      "currency": "SBD",
      "from_user": "user_2",
      "to_user": "user_x",
      "status": "succeeded",
      "created_at": "2025-10-22T10:05:00Z"
    }
  ],
  "total_transactions": 25,
  "has_more": false
}
```

#### 3. Account Name Update Endpoint
**Endpoint:** `PUT /family/{family_id}/sbd-account/name`

**Request:**
```json
{
  "account_name": "Summer Vacation Fund"
}
```

**Response:**
```json
{
  "account_id": "fam-acct_123",
  "account_username": "family_vacation_fund_123",
  "account_name": "Summer Vacation Fund",
  "updated_at": "2025-10-22T10:10:00Z"
}
```

---

## 🔄 **Migration Guide**

### **Frontend Changes Required**

#### **Display Logic Update**
```typescript
// Before (showing technical username)
const displayName = account.account_username; // "family_vacation_fund_123"

// After (showing user-friendly name with fallback)
const displayName = account.account_name || account.account_username;
```

#### **Component Updates**
Update any components that display family account information:

1. **Account Balance Cards** - Use `account_name` for titles
2. **Transaction Lists** - Show account name in headers
3. **Account Selection Dropdowns** - Display friendly names
4. **Settings Pages** - Use account names in labels

#### **QR Code Generation**
```typescript
// QR codes should encode the technical username
const qrData = `sbd:${account.account_username}`;
```

#### **Example Implementation**
```typescript
interface FamilyAccount {
  account_username: string;
  account_name?: string; // New field
  balance: number;
  // ... other fields
}

function AccountDisplay({ account }: { account: FamilyAccount }) {
  const displayName = account.account_name || account.account_username;

  return (
    <div className="account-card">
      <h3>{displayName}</h3>
      <p>Balance: ${account.balance}</p>
    </div>
  );
}
```

---

## 🔧 **Technical Details**

### **Database Schema Changes**
```sql
-- Add new columns to family_sbd_accounts table
ALTER TABLE family_sbd_accounts
ADD COLUMN account_username VARCHAR(255) UNIQUE NOT NULL,
ADD COLUMN account_name VARCHAR(255);

-- Create index for performance
CREATE INDEX idx_family_sbd_accounts_username ON family_sbd_accounts(account_username);
```

### **Account Username Generation**
- Pattern: `family_{sanitized_name}_{family_id}` or `family_{family_id}`
- Example: `family_vacation_fund_123`
- Auto-generated on account creation
- Immutable once created

### **Account Name Management**
- Optional field that can be set by family admins
- Can be updated via the name update endpoint
- Used for display purposes only

### **Fallback Logic**
- If `account_name` is not set (null/undefined/empty), fall back to `account_username`
- This ensures backward compatibility with existing accounts
- No breaking changes - existing frontend code will continue to work

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
- [ ] Test QR code generation uses account_username
- [ ] Verify QR scanning handles both old and new formats

### **API Integration Testing**
- [ ] Call both endpoints and verify `account_name` field presence
- [ ] Test with families that have custom account names
- [ ] Test with families using default username fallback
- [ ] Verify response structure matches documentation
- [ ] Test account name update endpoint (admin only)

### **Database Testing**
- [ ] Verify account_username generation for new accounts
- [ ] Test account_name updates are persisted
- [ ] Confirm unique constraint on account_username
- [ ] Test migration of existing accounts

---

## 📞 **Questions & Support**

If you encounter any issues with these changes:

1. **API Response Issues** - Check that you're accessing the new `account_name` field
2. **Display Problems** - Ensure fallback logic is implemented correctly
3. **Missing Names** - This is expected for existing accounts; names can be added later
4. **QR Code Issues** - Ensure QR codes use `account_username` for encoding

**Contact:** Backend Team
**Documentation:** See API docs for complete response schemas

---

## 📈 **Benefits**

- **Better UX**: Users see meaningful account names instead of technical IDs
- **Flexibility**: Accounts can have custom names for different purposes
- **Backward Compatible**: Existing integrations continue to work
- **Future-Proof**: Foundation for account management features

---

## 🚀 **Implementation Status**

### **Frontend Changes** ✅
- Updated SBDAccount model to include accountUsername and accountName fields
- Added displayName and qrUsername helper methods
- Updated QR code generation to use account username
- Updated QR scanning to handle both old and new formats
- Updated all display text to use account display name
- Updated app bar and balance cards to show friendly names

### **Backend Changes** 🔄
- Database schema updated with new columns
- API responses include new fields
- Account name update endpoint implemented
- Account username generation logic implemented

---

**Next Steps:**
1. Deploy backend changes to staging environment
2. Test frontend integration with new API responses
3. Deploy frontend changes to production
4. Monitor for any issues with QR code compatibility
5. Consider adding account name management UI in future releases

---</content>
<parameter name="filePath">/Users/rohan/Documents/repos/emotion_tracker/docs/FAMILY_SBD_API_CHANGES.md