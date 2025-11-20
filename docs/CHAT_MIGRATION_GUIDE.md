# Chat System Migration Guide

This guide explains how to set up the MongoDB collections and indexes for the LangGraph-based chat system.

## Overview

The chat system requires four MongoDB collections:
- `chat_sessions` - Stores chat session metadata
- `chat_messages` - Stores individual messages in conversations
- `token_usage` - Tracks token usage for cost monitoring
- `message_votes` - Stores user feedback (upvotes/downvotes)

## Running the Migration

### Prerequisites

1. **MongoDB Running**: Ensure MongoDB is running and accessible
2. **Configuration**: Set `MONGODB_URL` and `MONGODB_DATABASE` in your `.sbd` or `.env` file
3. **Dependencies**: Install project dependencies with `uv sync`

### Execute Migration

```bash
# Run the migration
python scripts/run_chat_migration.py

# Or with uv
uv run python scripts/run_chat_migration.py
```

### Check Migration Status

```bash
# Check if migration has been applied
python scripts/run_chat_migration.py --status
```

### Rollback Migration (if needed)

⚠️ **WARNING**: This will delete all chat data!

```bash
# Rollback the migration
python scripts/run_chat_migration.py --rollback
```

## What the Migration Creates

### Collections

#### 1. chat_sessions
Stores chat session metadata with the following indexes:
- `id` (unique) - Session identifier
- `user_id` - User who owns the session
- `session_type` - Type of chat (GENERAL, SQL, VECTOR)
- `is_active` - Whether session is active
- `created_at` - Creation timestamp
- Compound indexes for efficient queries

#### 2. chat_messages
Stores individual messages with indexes:
- `id` (unique) - Message identifier
- `session_id` - Parent session
- `user_id` - Message author
- `role` - Message role (user, assistant, system)
- `status` - Message status (PENDING, COMPLETED, FAILED)
- `created_at` - Creation timestamp
- Compound indexes for conversation retrieval

#### 3. token_usage
Tracks token usage for cost monitoring:
- `id` (unique) - Usage record identifier
- `message_id` - Associated message
- `session_id` - Associated session
- `model` - LLM model used
- `created_at` - Timestamp
- Compound indexes for analytics

#### 4. message_votes
Stores user feedback on messages:
- `id` (unique) - Vote identifier
- `message_id` - Voted message
- `user_id` - User who voted
- `vote_type` - Vote type (up, down)
- `created_at` - Timestamp
- **Unique constraint**: One vote per user per message

## Verifying the Migration

### Using MongoDB Shell

```javascript
// Connect to MongoDB
mongosh

// Switch to your database
use your_database_name

// List collections
show collections
// Should show: chat_sessions, chat_messages, token_usage, message_votes

// Check indexes on chat_sessions
db.chat_sessions.getIndexes()

// Check indexes on chat_messages
db.chat_messages.getIndexes()

// Check indexes on token_usage
db.token_usage.getIndexes()

// Check indexes on message_votes
db.message_votes.getIndexes()
```

### Using Python

```python
import asyncio
from second_brain_database.database import db_manager

async def verify_collections():
    await db_manager.connect()
    
    # List collections
    collections = await db_manager.database.list_collection_names()
    print("Collections:", collections)
    
    # Check if chat collections exist
    chat_collections = ["chat_sessions", "chat_messages", "token_usage", "message_votes"]
    for collection in chat_collections:
        if collection in collections:
            print(f"✅ {collection} exists")
        else:
            print(f"❌ {collection} missing")
    
    await db_manager.close()

asyncio.run(verify_collections())
```

## Migration Details

### Schema Version

All collections include a `_schema_version` field set to `"1.0.0"` for future migration tracking.

### Index Strategy

The migration creates indexes optimized for:
- **Fast lookups**: Unique indexes on ID fields
- **User queries**: Indexes on `user_id` for user-specific data
- **Session queries**: Indexes on `session_id` for conversation retrieval
- **Time-based queries**: Indexes on `created_at` for chronological ordering
- **Compound queries**: Multi-field indexes for common query patterns

### Performance Considerations

- All indexes are created asynchronously
- Sample documents are inserted and removed to establish schema
- No data migration is performed (fresh collections)

## Troubleshooting

### Migration Already Applied

If you see "Migration already applied", the collections already exist. To re-run:

1. Drop existing collections:
   ```javascript
   db.chat_sessions.drop()
   db.chat_messages.drop()
   db.token_usage.drop()
   db.message_votes.drop()
   ```

2. Remove migration record:
   ```javascript
   db.migration_history.deleteMany({name: "create_chat_collections"})
   ```

3. Run migration again

### Database Connection Failed

Check your configuration:
```bash
# Verify MongoDB URL
echo $MONGODB_URL

# Test MongoDB connection
mongosh $MONGODB_URL
```

### Permission Errors

Ensure your MongoDB user has permissions to:
- Create collections
- Create indexes
- Insert/delete documents

## Next Steps

After running the migration:

1. **Start the application**: The chat system is ready to use
2. **Test the endpoints**: Use the chat API endpoints
3. **Monitor performance**: Check index usage with `db.collection.stats()`
4. **Review configuration**: See [CHAT_CONFIGURATION.md](./CHAT_CONFIGURATION.md)

## Related Documentation

- [Chat Configuration Guide](./CHAT_CONFIGURATION.md) - Environment variables and settings
- [Chat API Documentation](../README.md) - API endpoints and usage
- [Migration Manager](../src/second_brain_database/migrations/migration_manager.py) - Migration system details

## Support

For issues or questions:
1. Check application logs for detailed error messages
2. Verify MongoDB connection and permissions
3. Review migration history: `db.migration_history.find()`
4. Check the migration script output for specific errors
