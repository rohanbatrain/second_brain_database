# WebRTC Chunked File Transfer Implementation Plan

## Overview

Implement chunked file transfer over WebRTC data channels to enable peer-to-peer file sharing between participants with support for large files (100MB+), pause/resume, and progress tracking.

**Status:** 🚧 **IN PROGRESS**
**Estimated Effort:** 1-2 weeks
**Priority:** High (2nd of 4 priorities)

---

## Goals

1. Enable P2P file transfer between room participants
2. Support large files (100MB+) with chunking
3. Provide real-time progress tracking
4. Support pause/resume functionality
5. Handle network interruptions gracefully
6. Integrate with existing WebRTC infrastructure

---

## Architecture

### Components

1. **File Transfer Manager** (`file_transfer.py`)
   - Chunk file into smaller pieces (configurable size, default 64KB)
   - Track transfer progress
   - Handle pause/resume
   - Manage concurrent transfers
   - Cleanup on completion/cancellation

2. **WebRTC Integration** (`router.py`)
   - New message types for file transfer protocol
   - File offer/accept/reject flow
   - Progress updates via WebSocket
   - Transfer status tracking

3. **Storage Integration** (optional)
   - Temporary storage for chunked uploads
   - S3 integration for permanent storage
   - Automatic cleanup of temp files

### Message Types (Already Defined)

From `schemas.py` MessageType enum:
- `FILE_SHARE_OFFER`: Initiate file transfer
- `FILE_SHARE_ACCEPT`: Accept file transfer
- `FILE_SHARE_REJECT`: Reject file transfer  
- `FILE_SHARE_PROGRESS`: Progress update
- `FILE_SHARE_COMPLETE`: Transfer complete

### Data Flow

```
Sender                              Router                          Receiver
  |                                   |                                |
  |-- FILE_SHARE_OFFER -------------->|-- broadcast ---------------->  |
  |    {filename, size, chunks}       |                                |
  |                                   |                                |
  |                                   |<-- FILE_SHARE_ACCEPT ----------|
  |<-- relay accept -----------------|                                |
  |                                   |                                |
  |-- send chunk 1 ----------------->|-- relay chunk 1 ------------->|
  |-- send chunk 2 ----------------->|-- relay chunk 2 ------------->|
  |   ...                             |   ...                          |
  |-- FILE_SHARE_COMPLETE ---------->|-- broadcast ------------------>|
```

---

## Implementation Plan

### Phase 1: Core File Transfer Manager (3-4 days)

**File:** `src/second_brain_database/webrtc/file_transfer.py`

**Features:**
- [ ] File chunking algorithm (configurable chunk size)
- [ ] Transfer state tracking (pending, active, paused, completed, failed)
- [ ] Chunk verification (hash/checksum)
- [ ] Progress calculation
- [ ] Concurrent transfer management
- [ ] Memory-efficient streaming (don't load entire file)

**Key Classes:**
```python
class FileTransferManager:
    def __init__(self, chunk_size: int = 64 * 1024):  # 64KB default
        """Initialize file transfer manager"""
        
    async def create_offer(
        self, 
        file_path: str, 
        sender_id: str, 
        receiver_id: str,
        room_id: str
    ) -> Dict:
        """Create file transfer offer"""
        
    async def accept_transfer(self, transfer_id: str) -> bool:
        """Accept file transfer"""
        
    async def reject_transfer(self, transfer_id: str, reason: str) -> bool:
        """Reject file transfer"""
        
    async def send_chunk(
        self, 
        transfer_id: str, 
        chunk_index: int
    ) -> bytes:
        """Get next chunk to send"""
        
    async def receive_chunk(
        self, 
        transfer_id: str, 
        chunk_index: int, 
        data: bytes
    ) -> bool:
        """Receive and store chunk"""
        
    async def get_progress(self, transfer_id: str) -> Dict:
        """Get transfer progress"""
        
    async def pause_transfer(self, transfer_id: str) -> bool:
        """Pause active transfer"""
        
    async def resume_transfer(self, transfer_id: str) -> bool:
        """Resume paused transfer"""
        
    async def cancel_transfer(self, transfer_id: str) -> bool:
        """Cancel transfer and cleanup"""
```

### Phase 2: Router Integration (2-3 days)

**File:** `src/second_brain_database/webrtc/router.py`

**Changes:**
- [ ] Handle `FILE_SHARE_OFFER` messages
- [ ] Handle `FILE_SHARE_ACCEPT/REJECT` messages
- [ ] Stream file chunks via WebSocket
- [ ] Track transfer progress
- [ ] Broadcast progress updates
- [ ] Handle transfer completion/failure

**New Endpoints:**
```python
@router.post("/rooms/{room_id}/file-transfer/offer")
async def create_file_transfer_offer(...):
    """Create new file transfer offer"""
    
@router.post("/rooms/{room_id}/file-transfer/{transfer_id}/accept")
async def accept_file_transfer(...):
    """Accept file transfer"""
    
@router.post("/rooms/{room_id}/file-transfer/{transfer_id}/reject")
async def reject_file_transfer(...):
    """Reject file transfer"""
    
@router.post("/rooms/{room_id}/file-transfer/{transfer_id}/pause")
async def pause_file_transfer(...):
    """Pause active transfer"""
    
@router.post("/rooms/{room_id}/file-transfer/{transfer_id}/resume")
async def resume_file_transfer(...):
    """Resume paused transfer"""
    
@router.get("/rooms/{room_id}/file-transfer/{transfer_id}/progress")
async def get_transfer_progress(...):
    """Get real-time transfer progress"""
    
@router.delete("/rooms/{room_id}/file-transfer/{transfer_id}")
async def cancel_file_transfer(...):
    """Cancel transfer and cleanup"""
```

### Phase 3: Testing & Documentation (1-2 days)

**Test File:** `test_file_transfer_feature.py`

**Tests:**
- [ ] File chunking algorithm
- [ ] Transfer state management
- [ ] Pause/resume functionality
- [ ] Progress tracking accuracy
- [ ] Concurrent transfer handling
- [ ] Error handling and cleanup
- [ ] Large file support (100MB+)
- [ ] Network interruption recovery

---

## Technical Specifications

### Chunk Protocol

**Chunk Format:**
```json
{
  "transfer_id": "uuid",
  "chunk_index": 0,
  "total_chunks": 100,
  "chunk_size": 65536,
  "data": "base64_encoded_bytes",
  "checksum": "sha256_hash"
}
```

### Transfer State

**Transfer Object:**
```json
{
  "transfer_id": "uuid",
  "room_id": "room_123",
  "sender_id": "user1@example.com",
  "receiver_id": "user2@example.com",
  "filename": "document.pdf",
  "file_size": 10485760,
  "chunk_size": 65536,
  "total_chunks": 160,
  "chunks_sent": 85,
  "status": "active",
  "progress_percent": 53.13,
  "bytes_transferred": 5570560,
  "started_at": "2025-11-10T02:10:00Z",
  "completed_at": null,
  "error": null
}
```

### Storage Strategy

**Options:**
1. **In-Memory Buffer (Small Files < 10MB)**
   - Fast, no disk I/O
   - Limited by RAM

2. **Temporary File System (Medium Files < 100MB)**
   - `/tmp/webrtc_transfers/{transfer_id}/`
   - Automatic cleanup after 1 hour

3. **S3 Storage (Large Files > 100MB)**
   - Multipart upload
   - Permanent storage
   - CDN distribution

**Decision:** Start with option 2 (temp filesystem), add S3 in future iteration.

---

## Security Considerations

1. **File Size Limits**
   - Max file size: 500MB (configurable)
   - Rate limit: 5 concurrent transfers per user
   - Total bandwidth limit per room

2. **File Type Validation**
   - Whitelist/blacklist of MIME types
   - Magic byte verification
   - Virus scanning integration (future)

3. **Access Control**
   - Only room participants can transfer files
   - Sender/receiver authentication required
   - Transfer expiration (1 hour timeout)

4. **Data Privacy**
   - Files stored encrypted at rest
   - Automatic cleanup of temp files
   - No permanent storage without explicit consent

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Chunk Size | 64KB (configurable) |
| Max Concurrent Transfers | 10 per room |
| Max File Size | 500MB (configurable) |
| Transfer Speed | Network-limited (P2P) |
| Memory Usage | < 10MB per active transfer |
| Cleanup Latency | < 1 second after completion |

---

## Error Handling

**Error Scenarios:**
1. Network interruption → Auto-resume from last chunk
2. Receiver disconnects → Pause transfer, resume on reconnect
3. Sender disconnects → Cancel transfer, cleanup
4. File system full → Fail gracefully, notify user
5. Invalid chunk checksum → Request retransmission
6. Timeout (no activity 30s) → Auto-cancel

---

## Integration with Reconnection Feature

Leverage existing reconnection infrastructure:

```python
# On reconnect, check for paused transfers
reconnect_info = await reconnection_manager.handle_reconnect(room_id, username)

# Resume any paused file transfers
paused_transfers = await file_transfer_manager.get_user_transfers(
    user_id=username,
    status="paused"
)

for transfer in paused_transfers:
    await file_transfer_manager.resume_transfer(transfer["transfer_id"])
```

---

## Next Steps

1. **Create `file_transfer.py` module** - Core transfer manager
2. **Add file transfer message handlers** - Router integration
3. **Implement chunk streaming** - WebSocket binary frames
4. **Add progress tracking** - Real-time updates
5. **Write comprehensive tests** - All scenarios covered
6. **Document API endpoints** - OpenAPI specs

**Start Date:** November 10, 2025
**Target Completion:** November 17-24, 2025

---

*This feature builds on the reconnection infrastructure and provides critical file sharing capabilities for the WebRTC platform.*
