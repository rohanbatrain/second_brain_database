"""
WebRTC File Transfer Manager

Handles chunked file transfer over WebRTC data channels with support for:
- Large files (100MB+) with configurable chunk sizes
- Pause/resume functionality
- Real-time progress tracking
- Concurrent transfer management
- Automatic cleanup and error handling
"""

import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, BinaryIO
from enum import Enum

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.config import settings

logger = get_logger(prefix="[WebRTC-FileTransfer]")


class TransferStatus(str, Enum):
    """File transfer status states."""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FileTransferManager:
    """
    Manages chunked file transfers between WebRTC participants.
    
    Features:
    - Configurable chunk sizes (default 64KB)
    - Progress tracking with Redis state
    - Pause/resume support
    - Concurrent transfer limits
    - Automatic cleanup
    - Checksum verification
    """
    
    def __init__(
        self,
        chunk_size: int = 64 * 1024,  # 64KB default
        max_file_size: int = 500 * 1024 * 1024,  # 500MB default
        max_concurrent_per_user: int = 5,
        transfer_timeout: int = 3600,  # 1 hour
        temp_dir: Optional[str] = None
    ):
        """
        Initialize file transfer manager.
        
        Args:
            chunk_size: Size of each chunk in bytes (default 64KB)
            max_file_size: Maximum file size in bytes (default 500MB)
            max_concurrent_per_user: Max concurrent transfers per user
            transfer_timeout: Transfer timeout in seconds (default 1 hour)
            temp_dir: Temporary directory for file chunks
        """
        self.chunk_size = chunk_size
        self.max_file_size = max_file_size
        self.max_concurrent_per_user = max_concurrent_per_user
        self.transfer_timeout = transfer_timeout
        
        # Setup temp directory
        if temp_dir:
            self.temp_dir = Path(temp_dir)
        else:
            self.temp_dir = Path("/tmp/webrtc_transfers")
        
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Redis key prefixes
        self.TRANSFER_STATE_PREFIX = "webrtc:file_transfer:state:"
        self.TRANSFER_CHUNKS_PREFIX = "webrtc:file_transfer:chunks:"
        self.USER_TRANSFERS_PREFIX = "webrtc:file_transfer:user:"
        
        logger.info(
            f"File transfer manager initialized "
            f"(chunk_size={chunk_size}, max_size={max_file_size}, "
            f"temp_dir={self.temp_dir})"
        )
    
    async def create_offer(
        self,
        room_id: str,
        sender_id: str,
        receiver_id: str,
        filename: str,
        file_size: int,
        mime_type: Optional[str] = None
    ) -> Dict:
        """
        Create a new file transfer offer.
        
        Args:
            room_id: Room ID where transfer occurs
            sender_id: User ID of sender
            receiver_id: User ID of receiver
            filename: Name of file being transferred
            file_size: Size of file in bytes
            mime_type: MIME type of file (optional)
            
        Returns:
            Dict with transfer details including transfer_id
            
        Raises:
            ValueError: If file size exceeds limit or user has too many transfers
        """
        try:
            # Validate file size
            if file_size > self.max_file_size:
                raise ValueError(
                    f"File size {file_size} exceeds maximum {self.max_file_size}"
                )
            
            # Check concurrent transfer limit
            sender_transfers = await self._get_user_active_transfers(sender_id)
            if len(sender_transfers) >= self.max_concurrent_per_user:
                raise ValueError(
                    f"User has {len(sender_transfers)} active transfers, "
                    f"maximum is {self.max_concurrent_per_user}"
                )
            
            # Generate transfer ID
            transfer_id = str(uuid.uuid4())
            
            # Calculate chunks
            total_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
            
            # Create transfer state
            transfer_state = {
                "transfer_id": transfer_id,
                "room_id": room_id,
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "filename": filename,
                "file_size": file_size,
                "mime_type": mime_type,
                "chunk_size": self.chunk_size,
                "total_chunks": total_chunks,
                "chunks_sent": 0,
                "chunks_received": 0,
                "status": TransferStatus.PENDING,
                "progress_percent": 0.0,
                "bytes_transferred": 0,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "error": None,
                "checksum": None
            }
            
            # Store in Redis
            redis_client = await redis_manager.get_redis()
            state_key = f"{self.TRANSFER_STATE_PREFIX}{transfer_id}"
            await redis_client.setex(
                state_key,
                self.transfer_timeout,
                json.dumps(transfer_state)
            )
            
            # Add to sender's transfer list
            sender_key = f"{self.USER_TRANSFERS_PREFIX}{sender_id}"
            await redis_client.sadd(sender_key, transfer_id)
            await redis_client.expire(sender_key, self.transfer_timeout)
            
            # Add to receiver's transfer list
            receiver_key = f"{self.USER_TRANSFERS_PREFIX}{receiver_id}"
            await redis_client.sadd(receiver_key, transfer_id)
            await redis_client.expire(receiver_key, self.transfer_timeout)
            
            logger.info(
                f"Created file transfer offer: {transfer_id}",
                extra={
                    "transfer_id": transfer_id,
                    "sender_id": sender_id,
                    "receiver_id": receiver_id,
                    "file_name": filename,  # Changed from 'filename' to avoid conflict
                    "file_size": file_size,
                    "total_chunks": total_chunks
                }
            )
            
            return transfer_state
            
        except Exception as e:
            logger.error(f"Failed to create file transfer offer: {e}", exc_info=True)
            raise
    
    async def accept_transfer(self, transfer_id: str, receiver_id: str) -> Dict:
        """
        Accept a pending file transfer.
        
        Args:
            transfer_id: Transfer ID to accept
            receiver_id: User ID of receiver (for authorization)
            
        Returns:
            Updated transfer state
            
        Raises:
            ValueError: If transfer not found or not pending
            PermissionError: If user is not the receiver
        """
        try:
            transfer_state = await self._get_transfer_state(transfer_id)
            
            if not transfer_state:
                raise ValueError(f"Transfer {transfer_id} not found")
            
            # Verify receiver
            if transfer_state["receiver_id"] != receiver_id:
                raise PermissionError("Only receiver can accept transfer")
            
            # Check status
            if transfer_state["status"] != TransferStatus.PENDING:
                raise ValueError(
                    f"Transfer is {transfer_state['status']}, not pending"
                )
            
            # Update status to active
            transfer_state["status"] = TransferStatus.ACTIVE
            transfer_state["accepted_at"] = datetime.now(timezone.utc).isoformat()
            
            await self._update_transfer_state(transfer_id, transfer_state)
            
            # Create temp directory for chunks
            transfer_dir = self.temp_dir / transfer_id
            transfer_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(
                f"File transfer accepted: {transfer_id}",
                extra={"transfer_id": transfer_id, "receiver_id": receiver_id}
            )
            
            return transfer_state
            
        except Exception as e:
            logger.error(f"Failed to accept transfer: {e}", exc_info=True)
            raise
    
    async def reject_transfer(
        self,
        transfer_id: str,
        receiver_id: str,
        reason: Optional[str] = None
    ) -> Dict:
        """
        Reject a pending file transfer.
        
        Args:
            transfer_id: Transfer ID to reject
            receiver_id: User ID of receiver (for authorization)
            reason: Optional rejection reason
            
        Returns:
            Updated transfer state
        """
        try:
            transfer_state = await self._get_transfer_state(transfer_id)
            
            if not transfer_state:
                raise ValueError(f"Transfer {transfer_id} not found")
            
            # Verify receiver
            if transfer_state["receiver_id"] != receiver_id:
                raise PermissionError("Only receiver can reject transfer")
            
            # Update status
            transfer_state["status"] = TransferStatus.CANCELLED
            transfer_state["error"] = reason or "Rejected by receiver"
            transfer_state["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            await self._update_transfer_state(transfer_id, transfer_state)
            
            logger.info(
                f"File transfer rejected: {transfer_id}",
                extra={
                    "transfer_id": transfer_id,
                    "receiver_id": receiver_id,
                    "reason": reason
                }
            )
            
            return transfer_state
            
        except Exception as e:
            logger.error(f"Failed to reject transfer: {e}", exc_info=True)
            raise
    
    async def get_chunk(self, transfer_id: str, chunk_index: int) -> bytes:
        """
        Get a specific chunk for sending.
        
        This is a placeholder - in production, this would read from the
        actual file being transferred.
        
        Args:
            transfer_id: Transfer ID
            chunk_index: Index of chunk to retrieve
            
        Returns:
            Chunk data as bytes
        """
        transfer_state = await self._get_transfer_state(transfer_id)
        
        if not transfer_state:
            raise ValueError(f"Transfer {transfer_id} not found")
        
        # In production, read from actual file
        # For now, return placeholder
        chunk_data = b"placeholder_chunk_data"
        
        return chunk_data
    
    async def receive_chunk(
        self,
        transfer_id: str,
        chunk_index: int,
        data: bytes,
        checksum: Optional[str] = None
    ) -> Dict:
        """
        Receive and store a chunk.
        
        Args:
            transfer_id: Transfer ID
            chunk_index: Index of chunk
            data: Chunk data
            checksum: Optional checksum for verification
            
        Returns:
            Updated progress information
        """
        try:
            transfer_state = await self._get_transfer_state(transfer_id)
            
            if not transfer_state:
                raise ValueError(f"Transfer {transfer_id} not found")
            
            # Verify checksum if provided
            if checksum:
                computed = hashlib.sha256(data).hexdigest()
                if computed != checksum:
                    raise ValueError(
                        f"Checksum mismatch for chunk {chunk_index}"
                    )
            
            # Store chunk to temp file
            transfer_dir = self.temp_dir / transfer_id
            transfer_dir.mkdir(parents=True, exist_ok=True)
            
            chunk_file = transfer_dir / f"chunk_{chunk_index:06d}"
            chunk_file.write_bytes(data)
            
            # Update state
            transfer_state["chunks_received"] += 1
            transfer_state["bytes_transferred"] += len(data)
            transfer_state["progress_percent"] = (
                transfer_state["chunks_received"] / transfer_state["total_chunks"] * 100
            )
            
            # Check if complete
            if transfer_state["chunks_received"] == transfer_state["total_chunks"]:
                transfer_state["status"] = TransferStatus.COMPLETED
                transfer_state["completed_at"] = datetime.now(timezone.utc).isoformat()
                
                # Assemble final file
                await self._assemble_chunks(transfer_id, transfer_state)
            
            await self._update_transfer_state(transfer_id, transfer_state)
            
            logger.debug(
                f"Received chunk {chunk_index}/{transfer_state['total_chunks']} "
                f"for transfer {transfer_id}"
            )
            
            return {
                "transfer_id": transfer_id,
                "chunk_index": chunk_index,
                "chunks_received": transfer_state["chunks_received"],
                "total_chunks": transfer_state["total_chunks"],
                "progress_percent": transfer_state["progress_percent"],
                "status": transfer_state["status"]
            }
            
        except Exception as e:
            logger.error(f"Failed to receive chunk: {e}", exc_info=True)
            raise
    
    async def pause_transfer(self, transfer_id: str, user_id: str) -> Dict:
        """
        Pause an active transfer.
        
        Args:
            transfer_id: Transfer ID to pause
            user_id: User ID (must be sender or receiver)
            
        Returns:
            Updated transfer state
        """
        try:
            transfer_state = await self._get_transfer_state(transfer_id)
            
            if not transfer_state:
                raise ValueError(f"Transfer {transfer_id} not found")
            
            # Verify user is involved in transfer
            if user_id not in [transfer_state["sender_id"], transfer_state["receiver_id"]]:
                raise PermissionError("User not involved in this transfer")
            
            # Can only pause active transfers
            if transfer_state["status"] != TransferStatus.ACTIVE:
                raise ValueError(f"Cannot pause transfer with status {transfer_state['status']}")
            
            transfer_state["status"] = TransferStatus.PAUSED
            transfer_state["paused_at"] = datetime.now(timezone.utc).isoformat()
            
            await self._update_transfer_state(transfer_id, transfer_state)
            
            logger.info(f"Transfer paused: {transfer_id}", extra={"transfer_id": transfer_id})
            
            return transfer_state
            
        except Exception as e:
            logger.error(f"Failed to pause transfer: {e}", exc_info=True)
            raise
    
    async def resume_transfer(self, transfer_id: str, user_id: str) -> Dict:
        """
        Resume a paused transfer.
        
        Args:
            transfer_id: Transfer ID to resume
            user_id: User ID (must be sender or receiver)
            
        Returns:
            Updated transfer state
        """
        try:
            transfer_state = await self._get_transfer_state(transfer_id)
            
            if not transfer_state:
                raise ValueError(f"Transfer {transfer_id} not found")
            
            # Verify user is involved in transfer
            if user_id not in [transfer_state["sender_id"], transfer_state["receiver_id"]]:
                raise PermissionError("User not involved in this transfer")
            
            # Can only resume paused transfers
            if transfer_state["status"] != TransferStatus.PAUSED:
                raise ValueError(f"Cannot resume transfer with status {transfer_state['status']}")
            
            transfer_state["status"] = TransferStatus.ACTIVE
            transfer_state["resumed_at"] = datetime.now(timezone.utc).isoformat()
            
            await self._update_transfer_state(transfer_id, transfer_state)
            
            logger.info(f"Transfer resumed: {transfer_id}", extra={"transfer_id": transfer_id})
            
            return transfer_state
            
        except Exception as e:
            logger.error(f"Failed to resume transfer: {e}", exc_info=True)
            raise
    
    async def cancel_transfer(self, transfer_id: str, user_id: str) -> Dict:
        """
        Cancel a transfer and cleanup.
        
        Args:
            transfer_id: Transfer ID to cancel
            user_id: User ID (must be sender or receiver)
            
        Returns:
            Updated transfer state
        """
        try:
            transfer_state = await self._get_transfer_state(transfer_id)
            
            if not transfer_state:
                raise ValueError(f"Transfer {transfer_id} not found")
            
            # Verify user is involved in transfer
            if user_id not in [transfer_state["sender_id"], transfer_state["receiver_id"]]:
                raise PermissionError("User not involved in this transfer")
            
            transfer_state["status"] = TransferStatus.CANCELLED
            transfer_state["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            await self._update_transfer_state(transfer_id, transfer_state)
            
            # Cleanup temp files
            await self._cleanup_transfer(transfer_id)
            
            logger.info(f"Transfer cancelled: {transfer_id}", extra={"transfer_id": transfer_id})
            
            return transfer_state
            
        except Exception as e:
            logger.error(f"Failed to cancel transfer: {e}", exc_info=True)
            raise
    
    async def get_transfer_progress(self, transfer_id: str) -> Dict:
        """
        Get current transfer progress.
        
        Args:
            transfer_id: Transfer ID
            
        Returns:
            Transfer state with progress information
        """
        transfer_state = await self._get_transfer_state(transfer_id)
        
        if not transfer_state:
            raise ValueError(f"Transfer {transfer_id} not found")
        
        return transfer_state
    
    async def get_user_transfers(
        self,
        user_id: str,
        status: Optional[TransferStatus] = None
    ) -> List[Dict]:
        """
        Get all transfers for a user.
        
        Args:
            user_id: User ID
            status: Optional status filter
            
        Returns:
            List of transfer states
        """
        try:
            redis_client = await redis_manager.get_redis()
            user_key = f"{self.USER_TRANSFERS_PREFIX}{user_id}"
            
            transfer_ids = await redis_client.smembers(user_key)
            
            if not transfer_ids:
                return []
            
            transfers = []
            for transfer_id in transfer_ids:
                state = await self._get_transfer_state(transfer_id)
                if state and (not status or state["status"] == status):
                    transfers.append(state)
            
            return transfers
            
        except Exception as e:
            logger.error(f"Failed to get user transfers: {e}", exc_info=True)
            return []
    
    # Private helper methods
    
    async def _get_transfer_state(self, transfer_id: str) -> Optional[Dict]:
        """Get transfer state from Redis."""
        try:
            redis_client = await redis_manager.get_redis()
            state_key = f"{self.TRANSFER_STATE_PREFIX}{transfer_id}"
            
            state_json = await redis_client.get(state_key)
            
            if not state_json:
                return None
            
            return json.loads(state_json)
            
        except Exception as e:
            logger.error(f"Failed to get transfer state: {e}", exc_info=True)
            return None
    
    async def _update_transfer_state(self, transfer_id: str, state: Dict) -> None:
        """Update transfer state in Redis."""
        try:
            redis_client = await redis_manager.get_redis()
            state_key = f"{self.TRANSFER_STATE_PREFIX}{transfer_id}"
            
            await redis_client.setex(
                state_key,
                self.transfer_timeout,
                json.dumps(state)
            )
            
        except Exception as e:
            logger.error(f"Failed to update transfer state: {e}", exc_info=True)
            raise
    
    async def _get_user_active_transfers(self, user_id: str) -> List[str]:
        """Get list of active transfer IDs for a user."""
        transfers = await self.get_user_transfers(user_id)
        return [
            t["transfer_id"] for t in transfers
            if t["status"] in [TransferStatus.PENDING, TransferStatus.ACTIVE, TransferStatus.PAUSED]
        ]
    
    async def _assemble_chunks(self, transfer_id: str, transfer_state: Dict) -> None:
        """Assemble chunks into final file."""
        try:
            transfer_dir = self.temp_dir / transfer_id
            
            if not transfer_dir.exists():
                raise ValueError(f"Transfer directory not found: {transfer_dir}")
            
            # Assemble chunks in order
            output_file = transfer_dir / transfer_state["filename"]
            
            with output_file.open("wb") as outfile:
                for i in range(transfer_state["total_chunks"]):
                    chunk_file = transfer_dir / f"chunk_{i:06d}"
                    if chunk_file.exists():
                        outfile.write(chunk_file.read_bytes())
                        # Delete chunk after assembling
                        chunk_file.unlink()
            
            # Calculate final checksum
            with output_file.open("rb") as f:
                file_hash = hashlib.sha256()
                while chunk := f.read(8192):
                    file_hash.update(chunk)
                transfer_state["checksum"] = file_hash.hexdigest()
            
            logger.info(
                f"Assembled file for transfer {transfer_id}: {output_file}",
                extra={"transfer_id": transfer_id, "checksum": transfer_state["checksum"]}
            )
            
        except Exception as e:
            logger.error(f"Failed to assemble chunks: {e}", exc_info=True)
            raise
    
    async def _cleanup_transfer(self, transfer_id: str) -> None:
        """Cleanup temp files for a transfer."""
        try:
            transfer_dir = self.temp_dir / transfer_id
            
            if transfer_dir.exists():
                # Remove all files in directory
                for file in transfer_dir.iterdir():
                    file.unlink()
                
                # Remove directory
                transfer_dir.rmdir()
                
                logger.debug(f"Cleaned up transfer directory: {transfer_dir}")
                
        except Exception as e:
            logger.warning(f"Failed to cleanup transfer: {e}")


# Global singleton instance
file_transfer_manager = FileTransferManager()
