# CORS OPTIONS Request Issue - Region Update

## Problem
When trying to update a region from the frontend, you're getting:
```
OPTIONS /ipam/regions/69199f3fbaccb3281af2e834?region_name=Bidholi&owner=Rohan HTTP/1.1" 400 Bad Request
```

## Root Cause
The PATCH endpoint uses Query parameters instead of a request body:
```python
@router.patch("/regions/{region_id}")
async def update_region(
    region_name: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    # ... other query params
):
```

When the browser sends an OPTIONS preflight request, it includes the query parameters, and FastAPI tries to validate them, causing a 400 error.

## Solution Options

### Option 1: Change Backend to Use Request Body (RECOMMENDED)
This is the REST best practice for PATCH requests.

**Backend Change:**
```python
from pydantic import BaseModel

class RegionUpdateRequest(BaseModel):
    region_name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[Dict[str, str]] = None

@router.patch("/regions/{region_id}")
async def update_region(
    region_id: str,
    request_body: RegionUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    updates = request_body.dict(exclude_unset=True)
    # ... rest of logic
```

**Frontend Change:**
```typescript
update: async (regionId: string, updates: Partial<Region>): Promise<Region> => {
  const response = await apiClient.patch(`/ipam/regions/${regionId}`, updates);
  return response.data;
},
```

### Option 2: Add OPTIONS Handler (Quick Fix)
Add an explicit OPTIONS handler that bypasses validation:

```python
@router.options("/regions/{region_id}")
async def options_update_region(region_id: str):
    return {"message": "OK"}
```

### Option 3: Middleware to Handle OPTIONS
Create middleware that intercepts OPTIONS requests before they reach the endpoint.

## Recommended Action
**Use Option 1** - Change to request body. This is:
- RESTful best practice
- More secure (data not in URL/logs)
- Easier to extend
- Avoids CORS preflight issues

## Files to Modify

### Backend:
1. `src/second_brain_database/routes/ipam/routes.py` - Update region endpoint
2. `src/second_brain_database/routes/ipam/models.py` - Add RegionUpdateRequest model

### Frontend:
1. `submodules/IPAM/frontend/lib/api/regions.ts` - Change update method

## Current Workaround
Until fixed, you can:
1. Use the API directly with curl/Postman (no CORS preflight)
2. Disable CORS in browser (dev only, not recommended)
3. Use a CORS proxy (dev only)

## Testing After Fix
1. Open region detail page
2. Click "Edit" button
3. Change region name or owner
4. Click "Save"
5. Should see success toast and updated data
6. Check browser network tab - should see:
   - OPTIONS request → 200 OK
   - PATCH request → 200 OK

