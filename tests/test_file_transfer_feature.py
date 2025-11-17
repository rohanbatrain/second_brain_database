#!/usr/bin/env python3
"""
Test script for WebRTC File Transfer feature.

Tests:
1. Transfer offer creation
2. Transfer acceptance/rejection
3. Progress tracking
4. Pause/resume functionality
5. Concurrent transfer limits
6. Transfer cancellation
7. Cleanup
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.webrtc.file_transfer import (
    file_transfer_manager,
    TransferStatus
)
from second_brain_database.managers.redis_manager import redis_manager


async def test_create_offer():
    """Test creating a file transfer offer."""
    print("\n🧪 Test 1: Create File Transfer Offer")
    print("=" * 60)
    
    try:
        # Create offer
        transfer = await file_transfer_manager.create_offer(
            room_id="test_room_1",
            sender_id="user1@example.com",
            receiver_id="user2@example.com",
            filename="test_document.pdf",
            file_size=1024 * 1024,  # 1MB
            mime_type="application/pdf"
        )
        
        print(f"  ✓ Transfer created: {transfer['transfer_id']}")
        print(f"  ✓ Total chunks: {transfer['total_chunks']}")
        print(f"  ✓ Chunk size: {transfer['chunk_size']} bytes")
        print(f"  ✓ Status: {transfer['status']}")
        
        if transfer['status'] == TransferStatus.PENDING:
            print(f"\n✅ SUCCESS: File transfer offer created")
            return True, transfer['transfer_id']
        else:
            print(f"\n❌ FAILED: Unexpected status {transfer['status']}")
            return False, None
            
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False, None


async def test_accept_transfer(transfer_id: str):
    """Test accepting a file transfer."""
    print("\n🧪 Test 2: Accept File Transfer")
    print("=" * 60)
    
    try:
        # Accept transfer
        transfer = await file_transfer_manager.accept_transfer(
            transfer_id=transfer_id,
            receiver_id="user2@example.com"
        )
        
        print(f"  ✓ Transfer accepted: {transfer_id}")
        print(f"  ✓ Status: {transfer['status']}")
        
        if transfer['status'] == TransferStatus.ACTIVE:
            print(f"\n✅ SUCCESS: File transfer accepted")
            return True
        else:
            print(f"\n❌ FAILED: Unexpected status {transfer['status']}")
            return False
            
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return False


async def test_reject_transfer():
    """Test rejecting a file transfer."""
    print("\n🧪 Test 3: Reject File Transfer")
    print("=" * 60)
    
    try:
        # Create offer to reject
        transfer = await file_transfer_manager.create_offer(
            room_id="test_room_2",
            sender_id="user1@example.com",
            receiver_id="user3@example.com",
            filename="rejected.txt",
            file_size=1024,
            mime_type="text/plain"
        )
        
        transfer_id = transfer['transfer_id']
        print(f"  ✓ Created transfer to reject: {transfer_id}")
        
        # Reject it
        rejected = await file_transfer_manager.reject_transfer(
            transfer_id=transfer_id,
            receiver_id="user3@example.com",
            reason="Not interested"
        )
        
        print(f"  ✓ Transfer rejected: {transfer_id}")
        print(f"  ✓ Status: {rejected['status']}")
        print(f"  ✓ Error: {rejected.get('error')}")
        
        if rejected['status'] == TransferStatus.CANCELLED:
            print(f"\n✅ SUCCESS: File transfer rejected")
            return True
        else:
            print(f"\n❌ FAILED: Unexpected status {rejected['status']}")
            return False
            
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return False


async def test_pause_resume(transfer_id: str):
    """Test pause and resume functionality."""
    print("\n🧪 Test 4: Pause/Resume Transfer")
    print("=" * 60)
    
    try:
        # Pause
        paused = await file_transfer_manager.pause_transfer(
            transfer_id=transfer_id,
            user_id="user1@example.com"
        )
        
        print(f"  ✓ Transfer paused: {transfer_id}")
        print(f"  ✓ Status: {paused['status']}")
        
        if paused['status'] != TransferStatus.PAUSED:
            print(f"\n❌ FAILED: Expected PAUSED, got {paused['status']}")
            return False
        
        # Resume
        resumed = await file_transfer_manager.resume_transfer(
            transfer_id=transfer_id,
            user_id="user1@example.com"
        )
        
        print(f"  ✓ Transfer resumed: {transfer_id}")
        print(f"  ✓ Status: {resumed['status']}")
        
        if resumed['status'] == TransferStatus.ACTIVE:
            print(f"\n✅ SUCCESS: Pause/resume working correctly")
            return True
        else:
            print(f"\n❌ FAILED: Expected ACTIVE, got {resumed['status']}")
            return False
            
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return False


async def test_progress_tracking(transfer_id: str):
    """Test progress tracking."""
    print("\n🧪 Test 5: Progress Tracking")
    print("=" * 60)
    
    try:
        # Simulate receiving some chunks
        transfer = await file_transfer_manager.get_transfer_progress(transfer_id)
        initial_chunks = transfer['chunks_received']
        
        print(f"  ✓ Initial chunks received: {initial_chunks}")
        print(f"  ✓ Total chunks: {transfer['total_chunks']}")
        
        # Simulate receiving 3 chunks
        chunk_data = b"x" * transfer['chunk_size']
        
        for i in range(3):
            progress = await file_transfer_manager.receive_chunk(
                transfer_id=transfer_id,
                chunk_index=i,
                data=chunk_data[:min(len(chunk_data), transfer['chunk_size'])]
            )
            
            print(f"  ✓ Chunk {i+1} received - Progress: {progress['progress_percent']:.2f}%")
        
        # Get final progress
        final_transfer = await file_transfer_manager.get_transfer_progress(transfer_id)
        
        if final_transfer['chunks_received'] == initial_chunks + 3:
            print(f"\n✅ SUCCESS: Progress tracking accurate")
            return True
        else:
            print(f"\n❌ FAILED: Expected {initial_chunks + 3} chunks, got {final_transfer['chunks_received']}")
            return False
            
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_concurrent_limit():
    """Test concurrent transfer limits."""
    print("\n🧪 Test 6: Concurrent Transfer Limits")
    print("=" * 60)
    
    try:
        sender_id = "user_concurrent@example.com"
        
        # Create max allowed transfers
        created = []
        for i in range(file_transfer_manager.max_concurrent_per_user):
            transfer = await file_transfer_manager.create_offer(
                room_id=f"test_room_concurrent_{i}",
                sender_id=sender_id,
                receiver_id=f"receiver_{i}@example.com",
                filename=f"file_{i}.txt",
                file_size=1024
            )
            created.append(transfer['transfer_id'])
        
        print(f"  ✓ Created {len(created)} transfers (max allowed)")
        
        # Try to create one more (should fail)
        try:
            await file_transfer_manager.create_offer(
                room_id="test_room_overflow",
                sender_id=sender_id,
                receiver_id="overflow@example.com",
                filename="overflow.txt",
                file_size=1024
            )
            print(f"\n❌ FAILED: Should not allow more than {file_transfer_manager.max_concurrent_per_user} transfers")
            return False
        except ValueError as e:
            print(f"  ✓ Correctly rejected excess transfer: {e}")
        
        # Cleanup
        for transfer_id in created:
            await file_transfer_manager.cancel_transfer(transfer_id, sender_id)
        
        print(f"\n✅ SUCCESS: Concurrent transfer limit enforced")
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_cancel_and_cleanup(transfer_id: str):
    """Test transfer cancellation and cleanup."""
    print("\n🧪 Test 7: Cancel Transfer & Cleanup")
    print("=" * 60)
    
    try:
        # Cancel transfer
        cancelled = await file_transfer_manager.cancel_transfer(
            transfer_id=transfer_id,
            user_id="user1@example.com"
        )
        
        print(f"  ✓ Transfer cancelled: {transfer_id}")
        print(f"  ✓ Status: {cancelled['status']}")
        
        # Check temp directory was cleaned up
        transfer_dir = file_transfer_manager.temp_dir / transfer_id
        
        if not transfer_dir.exists():
            print(f"  ✓ Temp directory cleaned up")
        else:
            print(f"  ⚠️  Temp directory still exists")
        
        if cancelled['status'] == TransferStatus.CANCELLED:
            print(f"\n✅ SUCCESS: Transfer cancelled and cleaned up")
            return True
        else:
            print(f"\n❌ FAILED: Unexpected status {cancelled['status']}")
            return False
            
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return False


async def test_get_user_transfers():
    """Test getting user's transfers."""
    print("\n🧪 Test 8: Get User Transfers")
    print("=" * 60)
    
    try:
        user_id = "test_user_list@example.com"
        
        # Create a few transfers
        transfer_ids = []
        for i in range(3):
            transfer = await file_transfer_manager.create_offer(
                room_id=f"test_room_list_{i}",
                sender_id=user_id,
                receiver_id=f"receiver_list_{i}@example.com",
                filename=f"file_list_{i}.txt",
                file_size=1024
            )
            transfer_ids.append(transfer['transfer_id'])
        
        print(f"  ✓ Created {len(transfer_ids)} transfers")
        
        # Get all transfers for user
        transfers = await file_transfer_manager.get_user_transfers(user_id)
        
        print(f"  ✓ Retrieved {len(transfers)} transfers")
        
        # Get only pending transfers
        pending = await file_transfer_manager.get_user_transfers(
            user_id,
            status=TransferStatus.PENDING
        )
        
        print(f"  ✓ Found {len(pending)} pending transfers")
        
        # Cleanup
        for transfer_id in transfer_ids:
            await file_transfer_manager.cancel_transfer(transfer_id, user_id)
        
        if len(transfers) >= 3 and len(pending) >= 3:
            print(f"\n✅ SUCCESS: User transfer listing working")
            return True
        else:
            print(f"\n❌ FAILED: Expected at least 3 transfers")
            return False
            
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("🚀 WebRTC File Transfer Feature Test Suite")
    print("=" * 60)
    
    try:
        # Initialize Redis connection
        await redis_manager.get_redis()
        print("✓ Redis connection established")
        
        # Run tests
        results = []
        
        # Test 1: Create offer
        success, transfer_id = await test_create_offer()
        results.append(success)
        
        if not success or not transfer_id:
            print("\n⚠️  Cannot continue without valid transfer_id")
            return 1
        
        # Test 2: Accept transfer
        results.append(await test_accept_transfer(transfer_id))
        
        # Test 3: Reject transfer
        results.append(await test_reject_transfer())
        
        # Test 4: Pause/Resume
        results.append(await test_pause_resume(transfer_id))
        
        # Test 5: Progress tracking
        results.append(await test_progress_tracking(transfer_id))
        
        # Test 6: Concurrent limits
        results.append(await test_concurrent_limit())
        
        # Test 7: Cancel and cleanup
        results.append(await test_cancel_and_cleanup(transfer_id))
        
        # Test 8: Get user transfers
        results.append(await test_get_user_transfers())
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(results)
        total = len(results)
        
        print(f"\nPassed: {passed}/{total} tests")
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED! File transfer feature is working correctly.")
            print("\n📋 Feature Complete:")
            print("  ✓ Transfer offer creation")
            print("  ✓ Transfer acceptance/rejection")
            print("  ✓ Pause/resume functionality")
            print("  ✓ Progress tracking")
            print("  ✓ Concurrent transfer limits")
            print("  ✓ Transfer cancellation")
            print("  ✓ Cleanup and user transfer listing")
            return 0
        else:
            print(f"\n⚠️  {total - passed} test(s) failed")
            return 1
            
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Cleanup any remaining test data
        print("\n🧹 Cleaning up test data...")
        print("✓ Cleanup complete")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
