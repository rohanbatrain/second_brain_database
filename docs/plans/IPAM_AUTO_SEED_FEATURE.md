# IPAM Auto-Seed Feature

## Overview

The IPAM system now includes automatic fallback seeding of country/continent mappings. If the database is empty on startup, it automatically populates with the default hierarchical IP allocation rules from the SOP.

## How It Works

### Startup Sequence

1. **Application starts** → `main.py` lifespan function runs
2. **Database connects** → MongoDB connection established
3. **Indexes created** → Database indexes verified/created
4. **Auto-seed check** → Checks if `continent_country_mapping` collection is empty
5. **Auto-seed (if needed)** → Inserts 18 default country mappings
6. **Application ready** → Server starts accepting requests

### Code Flow

```python
# In main.py lifespan function
collection = db_manager.get_collection("continent_country_mapping")
count = await collection.count_documents({})

if count == 0:
    # Auto-seed with defaults
    from second_brain_database.managers.ipam_defaults import get_default_country_documents
    documents = get_default_country_documents()
    await collection.insert_many(documents)
    # Create indexes
    await collection.create_index("continent")
    await collection.create_index("country", unique=True)
    await collection.create_index([("x_start", 1), ("x_end", 1)])
```

## Default Country Mappings

The system seeds with **18 countries** across **7 continents**:

| Continent | Countries | X Range |
|-----------|-----------|---------|
| Asia | India, UAE, Singapore, Japan, South Korea, Indonesia, Taiwan | 0-77 |
| Africa | South Africa | 78-97 |
| Europe | Finland, Sweden, Poland, Spain | 98-137 |
| North America | Canada, United States | 138-167 |
| South America | Brazil, Chile | 168-187 |
| Australia | Australia | 188-207 |
| Reserved | Future Use | 208-255 |

## Files Involved

### New Files
1. **`src/second_brain_database/managers/ipam_defaults.py`**
   - Contains `DEFAULT_COUNTRY_MAPPINGS` constant
   - Provides `get_default_country_documents()` function
   - Generates properly formatted documents with metadata

2. **`scripts/seed_continent_country_mapping.py`**
   - Manual seeding script (optional)
   - Includes confirmation prompt before clearing existing data
   - Useful for resetting or updating mappings

### Modified Files
1. **`src/second_brain_database/main.py`**
   - Added auto-seed logic in lifespan function
   - Runs after database connection and index creation
   - Logs seeding status for monitoring

## Usage

### Automatic (Recommended)
Simply start the application. If the database is empty, it will auto-seed:

```bash
uv run uvicorn src.second_brain_database.main:app --reload
```

**Expected Log Output:**
```
[INFO] Checking IPAM country mappings...
[INFO] IPAM country mappings not found. Auto-seeding with defaults...
[INFO] ✅ Auto-seeded 18 IPAM country mappings
```

### Manual Seeding (Optional)
If you need to manually reseed or update the mappings:

```bash
uv run python scripts/seed_continent_country_mapping.py
```

**Interactive Prompt:**
```
Collection already has 18 documents. Do you want to clear and reseed? (y/n)
Clear and reseed? (y/n): y
Deleted 18 existing documents
Successfully inserted 18 country mappings
✅ Country mapping seed completed successfully!
```

## Benefits

### 1. Zero Configuration
- No manual database setup required
- Works out of the box for new installations
- Reduces deployment complexity

### 2. Idempotent
- Safe to run multiple times
- Only seeds if collection is empty
- Doesn't duplicate data

### 3. Production Ready
- Based on official SOP specifications
- Includes proper indexes for performance
- Comprehensive logging for monitoring

### 4. Maintainable
- Centralized default data in `ipam_defaults.py`
- Easy to update mappings if SOP changes
- Manual override available when needed

## Monitoring

### Successful Auto-Seed
```
[INFO] Checking IPAM country mappings...
[INFO] IPAM country mappings not found. Auto-seeding with defaults...
[INFO] ✅ Auto-seeded 18 IPAM country mappings
[LIFECYCLE] ipam_auto_seeded: {"countries_seeded": 18, "duration": "0.015s"}
```

### Skipped (Data Exists)
```
[INFO] Checking IPAM country mappings...
[INFO] IPAM country mappings already exist (18 countries)
[LIFECYCLE] ipam_seed_skipped: {"existing_countries": 18}
```

### Failed (Error)
```
[WARNING] Failed to auto-seed IPAM country mappings: <error message>
[LIFECYCLE] ipam_seed_failed: {"error": "<error message>"}
```

## Verification

### Check if Data Exists
```bash
uv run python -c "
import asyncio
from second_brain_database.database import db_manager

async def check():
    await db_manager.connect()
    collection = db_manager.get_collection('continent_country_mapping')
    count = await collection.count_documents({})
    print(f'Country mappings: {count}')
    await db_manager.disconnect()

asyncio.run(check())
"
```

### Test API Endpoint
```bash
curl http://localhost:8000/ipam/countries \
  -H "Authorization: Bearer YOUR_TOKEN" | jq
```

## Customization

To modify the default country mappings:

1. Edit `src/second_brain_database/managers/ipam_defaults.py`
2. Update the `DEFAULT_COUNTRY_MAPPINGS` list
3. Restart the application (or run manual seed script)

Example:
```python
DEFAULT_COUNTRY_MAPPINGS = [
    {"continent": "Asia", "country": "India", "x_start": 0, "x_end": 29},
    # Add or modify countries here
]
```

## Troubleshooting

### Issue: Auto-seed not running
**Solution**: Check that the collection is actually empty:
```bash
uv run python -c "
import asyncio
from second_brain_database.database import db_manager

async def check():
    await db_manager.connect()
    collection = db_manager.get_collection('continent_country_mapping')
    count = await collection.count_documents({})
    print(f'Count: {count}')
    if count > 0:
        print('Collection not empty - auto-seed will be skipped')
    await db_manager.disconnect()

asyncio.run(check())
"
```

### Issue: Need to reseed with updated data
**Solution**: Use the manual seed script with confirmation:
```bash
uv run python scripts/seed_continent_country_mapping.py
# Answer 'y' when prompted to clear and reseed
```

### Issue: Duplicate key error
**Solution**: Collection already has data. Clear it first:
```bash
uv run python -c "
import asyncio
from second_brain_database.database import db_manager

async def clear():
    await db_manager.connect()
    collection = db_manager.get_collection('continent_country_mapping')
    result = await collection.delete_many({})
    print(f'Deleted {result.deleted_count} documents')
    await db_manager.disconnect()

asyncio.run(clear())
"
```

## SOP Compliance

The auto-seed feature ensures compliance with the **Hierarchical IP Allocation Rules (10.X.Y.Z)** SOP by:

✅ Maintaining fixed continent-to-country mappings
✅ Preserving X octet ranges for each country
✅ Including reserved space (X=208-255) for future use
✅ Calculating correct capacity metrics (256 Y values per X)
✅ Setting proper metadata (created_at, updated_at, is_reserved)

---

**Status**: ✅ PRODUCTION READY

The auto-seed feature is fully functional and ready for production use. No manual intervention required for new deployments.
