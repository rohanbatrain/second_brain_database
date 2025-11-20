# IPAM Missing Endpoints

## Issue
Frontend is trying to access `/ipam/audit?page=1&page_size=25` but getting **404 Not Found**.

## Root Cause
The audit endpoint is not implemented in the backend yet, even though:
- Frontend has audit components (`components/ipam/audit-log-viewer.tsx`)
- Frontend has audit hooks (`lib/hooks/use-audit.ts`)
- Frontend has audit API client (`lib/api/audit.ts`)
- Documentation mentions audit features (`IPAM_COMPLETE_FEATURE_GUIDE.md`)

## Missing Endpoints

Based on the frontend code and documentation, these endpoints are expected but not implemented:

### 1. Audit History
- `GET /ipam/audit` - List all audit entries
- `GET /ipam/audit/{audit_id}` - Get specific audit entry
- `GET /ipam/regions/{region_id}/audit` - Get region audit history
- `GET /ipam/hosts/{host_id}/audit` - Get host audit history

### 2. Possibly Other Missing Endpoints
Check `src/second_brain_database/routes/ipam/routes.py` for:
- Import/Export endpoints
- Analytics endpoints
- Webhook endpoints
- Notification endpoints
- Reservation endpoints
- Share endpoints

## Quick Check

To see which endpoints are actually implemented, check:
```bash
grep -n "@router\." src/second_brain_database/routes/ipam/routes.py | grep -E "get|post|patch|delete"
```

## Workaround

For now, the audit page will show a 404 error. To fix:

### Option 1: Implement the Endpoint (Recommended)
Add to `src/second_brain_database/routes/ipam/routes.py`:

```python
@router.get(
    "/audit",
    summary="List audit entries",
    tags=["IPAM - Audit"]
)
async def list_audit_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """List audit entries for the current user."""
    user_id = str(current_user.get("_id", ""))
    
    # Query ipam_audit collection
    collection = db_manager.get_collection("ipam_audit")
    
    skip = (page - 1) * page_size
    cursor = collection.find({"user_id": user_id}).sort("timestamp", -1).skip(skip).limit(page_size)
    
    entries = await cursor.to_list(length=page_size)
    total_count = await collection.count_documents({"user_id": user_id})
    
    return {
        "results": entries,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": (total_count + page_size - 1) // page_size
        }
    }
```

### Option 2: Hide the Feature (Quick Fix)
Remove or hide the audit navigation link in the frontend until the backend is ready.

## Frontend Files Affected

These files expect the audit endpoint to exist:
- `submodules/IPAM/frontend/lib/api/audit.ts`
- `submodules/IPAM/frontend/lib/hooks/use-audit.ts`
- `submodules/IPAM/frontend/components/ipam/audit-log-viewer.tsx`
- `submodules/IPAM/frontend/components/ipam/audit-detail-dialog.tsx`
- `submodules/IPAM/frontend/app/dashboard/audit/page.tsx` (if it exists)

## Recommendation

Check which features are actually implemented in the backend:
```bash
# List all IPAM endpoints
grep -A 5 "@router\.(get|post|patch|delete)" src/second_brain_database/routes/ipam/routes.py | grep "summary"
```

Then update the frontend navigation to only show implemented features, or implement the missing backend endpoints.

## Status

- ✅ Owner field fix - Complete
- ✅ NaN% fix - Complete  
- ✅ Progress bar visibility - Complete
- ✅ Select empty value - Complete
- ⏳ CORS OPTIONS issue - Documented
- ❌ Audit endpoint - Not implemented
- ❓ Other endpoints - Need verification

## Next Steps

1. Verify which IPAM endpoints are actually implemented
2. Either implement missing endpoints or hide unimplemented features in UI
3. Update `IPAM_COMPLETE_FEATURE_GUIDE.md` to reflect actual implementation status
