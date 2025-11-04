# MCP Database Connection Fix Guide

## Current Status

✅ **Authentication Fixed** - MCP authentication is now working correctly  
❌ **Database Issue** - MCP tools can't connect to MongoDB

## The Problem

The error `"Failed to check family limits: Database not connected"` occurs because:

1. **FastAPI vs MCP Context**: The main FastAPI app initializes the database connection, but the MCP server runs in a separate context
2. **Timing Issue**: MCP tools try to access the database before the connection is fully established
3. **Connection Verification**: The database manager needs explicit connection verification for MCP operations

## Solutions Implemented

### 1. Database Integration Module (`database_integration.py`)
- **Purpose**: Provides MCP-specific database connection management
- **Features**: Connection verification, health checks, retry logic
- **Integration**: Works with existing `db_manager` from the main app

### 2. MCP Server Startup Fix (`start_mcp_server.py`)
- **Added**: Database initialization during server startup
- **Verification**: Checks database connection before starting MCP tools
- **Error Handling**: Provides clear error messages if MongoDB isn't running

### 3. Family Tools Update (`family_tools.py`)
- **Added**: Database connection verification in `create_family` tool
- **Import**: Uses MCP database integration for connection checks
- **Fallback**: Graceful error handling if database is unavailable

## Quick Fix Steps

### 1. Ensure MongoDB is Running
```bash
# Check if MongoDB is running
brew services list | grep mongodb

# Start MongoDB if not running
brew services start mongodb-community

# Verify MongoDB is listening
netstat -an | grep 27017
```

### 2. Test Database Connection
```bash
# Run the database connection test
python test_database_connection.py
```

### 3. Apply Configuration Fix
```bash
# Apply the complete fix
python fix_mcp_auth_now.py
```

### 4. Restart MCP Server
```bash
# Start MCP server with database initialization
python start_mcp_server.py --transport http
```

## Verification

After applying the fixes, you should see:

```
🔗 Initializing database connection...
✅ Database connection established
✅ MCP Server: SecondBrainMCP
📊 Tools: 140
```

Then test the create_family tool - it should work without database errors.

## Troubleshooting

### If MongoDB Won't Start
```bash
# Check MongoDB status
brew services info mongodb-community

# Check MongoDB logs
tail -f /usr/local/var/log/mongodb/mongo.log

# Restart MongoDB
brew services restart mongodb-community
```

### If Database Connection Still Fails
```bash
# Check configuration
cat .sbd | grep MONGODB

# Test connection manually
python -c "
import asyncio
import sys
sys.path.insert(0, 'src')
from second_brain_database.database import db_manager
asyncio.run(db_manager.health_check())
"
```

### If MCP Tools Still Fail
1. **Check server logs** for detailed error messages
2. **Verify configuration** matches your MongoDB setup
3. **Test individual components** using the test script
4. **Check timing** - ensure database is fully initialized before MCP tools run

## Architecture Notes

The fix maintains the existing architecture:
- **FastAPI app** continues to use `db_manager` directly
- **MCP tools** use the same `db_manager` but with additional connection verification
- **No breaking changes** to existing functionality
- **Backward compatible** with all existing database operations

## Files Modified

1. **`src/second_brain_database/integrations/mcp/database_integration.py`** (NEW)
   - MCP-specific database connection management
   - Health checks and retry logic

2. **`start_mcp_server.py`**
   - Added database initialization during startup
   - Better error messages for database issues

3. **`src/second_brain_database/integrations/mcp/tools/family_tools.py`**
   - Added database connection verification
   - Improved error handling

4. **`test_database_connection.py`** (NEW)
   - Comprehensive database connection testing
   - Diagnostic information for troubleshooting

5. **`fix_mcp_auth_now.py`**
   - Updated to include database fix information
   - Added troubleshooting steps

## Expected Result

After applying these fixes:
- ✅ MCP server starts with verified database connection
- ✅ `create_family` tool works without "Database not connected" errors
- ✅ All other MCP tools have reliable database access
- ✅ Existing FastAPI functionality remains unchanged

The system will be fully functional with both authentication and database connectivity working correctly.