"""
Test Suite for WebRTC E2EE (End-to-End Encryption) Feature

Tests:
1. Key Pair Generation
2. Key Exchange
3. Message Encryption
4. Message Decryption
5. Signature Verification
6. Replay Attack Prevention
7. Key Rotation
8. Key Revocation
9. Multiple Users
10. Cleanup
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.webrtc.e2ee import e2ee_manager, KeyType
from second_brain_database.managers.redis_manager import redis_manager


class TestE2EEFeature:
    """Test E2EE feature."""
    
    def __init__(self):
        self.test_room_id = "test_room_e2ee"
        self.test_user_a = "alice_e2ee"
        self.test_user_b = "bob_e2ee"
        self.test_user_c = "charlie_e2ee"
        self.generated_keys = []
    
    async def cleanup(self):
        """Cleanup test data."""
        try:
            # Cleanup all users
            for user_id in [self.test_user_a, self.test_user_b, self.test_user_c]:
                await e2ee_manager.cleanup_user_keys(user_id, self.test_room_id)
            
            print("✅ Cleanup completed")
            
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
    
    async def test_key_pair_generation(self):
        """Test 1: Key Pair Generation"""
        print("\n🧪 Test 1: Key Pair Generation")
        
        try:
            # Generate ephemeral key
            key_pair = await e2ee_manager.generate_key_pair(
                user_id=self.test_user_a,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            
            self.generated_keys.append(key_pair["key_id"])
            
            assert key_pair["user_id"] == self.test_user_a
            assert key_pair["room_id"] == self.test_room_id
            assert key_pair["key_type"] == KeyType.EPHEMERAL
            assert "public_key" in key_pair
            assert "signature_public_key" in key_pair
            assert "created_at" in key_pair
            assert "expires_at" in key_pair
            assert "private_key" not in key_pair  # Should not expose private key
            
            print(f"   Key ID: {key_pair['key_id']}")
            print(f"   Public Key: {key_pair['public_key'][:20]}...")
            print(f"   Signature Key: {key_pair['signature_public_key'][:20]}...")
            print("✅ Test 1 PASSED: Key pair generated successfully")
            return True
            
        except Exception as e:
            print(f"❌ Test 1 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_key_exchange(self):
        """Test 2: Key Exchange"""
        print("\n🧪 Test 2: Key Exchange")
        
        try:
            # Generate keys for both users
            key_a = await e2ee_manager.generate_key_pair(
                user_id=self.test_user_a,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            self.generated_keys.append(key_a["key_id"])
            
            key_b = await e2ee_manager.generate_key_pair(
                user_id=self.test_user_b,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            self.generated_keys.append(key_b["key_id"])
            
            # Exchange keys
            success = await e2ee_manager.exchange_keys(
                user_a_id=self.test_user_a,
                user_b_id=self.test_user_b,
                room_id=self.test_room_id
            )
            
            assert success is True
            
            print(f"   User A: {self.test_user_a}")
            print(f"   User B: {self.test_user_b}")
            print(f"   Exchange successful: {success}")
            print("✅ Test 2 PASSED: Key exchange successful")
            return True
            
        except Exception as e:
            print(f"❌ Test 2 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_message_encryption(self):
        """Test 3: Message Encryption"""
        print("\n🧪 Test 3: Message Encryption")
        
        try:
            # Setup keys
            await e2ee_manager.generate_key_pair(
                user_id=self.test_user_a,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            
            await e2ee_manager.generate_key_pair(
                user_id=self.test_user_b,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            
            await e2ee_manager.exchange_keys(
                user_a_id=self.test_user_a,
                user_b_id=self.test_user_b,
                room_id=self.test_room_id
            )
            
            # Encrypt message
            plaintext_message = {
                "type": "chat",
                "content": "Hello, this is a secret message!",
                "timestamp": "2025-11-10T12:00:00Z"
            }
            
            encrypted = await e2ee_manager.encrypt_message(
                message=plaintext_message,
                sender_id=self.test_user_a,
                recipient_id=self.test_user_b,
                room_id=self.test_room_id
            )
            
            assert encrypted["type"] == "e2ee_encrypted_message"
            assert encrypted["sender_id"] == self.test_user_a
            assert encrypted["recipient_id"] == self.test_user_b
            assert "nonce" in encrypted
            assert "ciphertext" in encrypted
            assert "signature" in encrypted
            
            print(f"   Plaintext: {plaintext_message['content']}")
            print(f"   Ciphertext: {encrypted['ciphertext'][:40]}...")
            print(f"   Nonce: {encrypted['nonce'][:20]}...")
            print(f"   Signature: {encrypted['signature'][:20]}...")
            print("✅ Test 3 PASSED: Message encrypted successfully")
            return True
            
        except Exception as e:
            print(f"❌ Test 3 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_message_decryption(self):
        """Test 4: Message Decryption"""
        print("\n🧪 Test 4: Message Decryption")
        
        try:
            # Setup keys
            await e2ee_manager.generate_key_pair(
                user_id=self.test_user_a,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            
            await e2ee_manager.generate_key_pair(
                user_id=self.test_user_b,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            
            await e2ee_manager.exchange_keys(
                user_a_id=self.test_user_a,
                user_b_id=self.test_user_b,
                room_id=self.test_room_id
            )
            
            # Encrypt and decrypt message
            plaintext_message = {
                "type": "chat",
                "content": "Testing encryption and decryption!",
                "metadata": {"priority": "high"}
            }
            
            encrypted = await e2ee_manager.encrypt_message(
                message=plaintext_message,
                sender_id=self.test_user_a,
                recipient_id=self.test_user_b,
                room_id=self.test_room_id
            )
            
            decrypted = await e2ee_manager.decrypt_message(
                encrypted=encrypted,
                recipient_id=self.test_user_b
            )
            
            assert decrypted["type"] == plaintext_message["type"]
            assert decrypted["content"] == plaintext_message["content"]
            assert decrypted["metadata"] == plaintext_message["metadata"]
            
            print(f"   Original: {plaintext_message['content']}")
            print(f"   Decrypted: {decrypted['content']}")
            print(f"   Match: {plaintext_message == decrypted}")
            print("✅ Test 4 PASSED: Message decrypted successfully")
            return True
            
        except Exception as e:
            print(f"❌ Test 4 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_signature_verification(self):
        """Test 5: Signature Verification"""
        print("\n🧪 Test 5: Signature Verification")
        
        try:
            # Setup keys
            await e2ee_manager.generate_key_pair(
                user_id=self.test_user_a,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            
            await e2ee_manager.generate_key_pair(
                user_id=self.test_user_b,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            
            await e2ee_manager.exchange_keys(
                user_a_id=self.test_user_a,
                user_b_id=self.test_user_b,
                room_id=self.test_room_id
            )
            
            # Encrypt message (includes signature)
            plaintext_message = {"type": "test", "data": "signature test"}
            
            encrypted = await e2ee_manager.encrypt_message(
                message=plaintext_message,
                sender_id=self.test_user_a,
                recipient_id=self.test_user_b,
                room_id=self.test_room_id
            )
            
            # Valid signature should decrypt successfully
            decrypted = await e2ee_manager.decrypt_message(
                encrypted=encrypted,
                recipient_id=self.test_user_b
            )
            
            assert decrypted == plaintext_message
            
            # Tampered message should fail
            tampered = encrypted.copy()
            tampered["ciphertext"] = tampered["ciphertext"][:-10] + "TAMPERED=="
            
            try:
                await e2ee_manager.decrypt_message(
                    encrypted=tampered,
                    recipient_id=self.test_user_b
                )
                print("❌ Test 5 FAILED: Tampered message should not decrypt")
                return False
            except Exception:
                print("   Correctly rejected tampered message")
            
            print("✅ Test 5 PASSED: Signature verification works")
            return True
            
        except Exception as e:
            print(f"❌ Test 5 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_replay_attack_prevention(self):
        """Test 6: Replay Attack Prevention"""
        print("\n🧪 Test 6: Replay Attack Prevention")
        
        try:
            # Setup keys
            await e2ee_manager.generate_key_pair(
                user_id=self.test_user_a,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            
            await e2ee_manager.generate_key_pair(
                user_id=self.test_user_b,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            
            await e2ee_manager.exchange_keys(
                user_a_id=self.test_user_a,
                user_b_id=self.test_user_b,
                room_id=self.test_room_id
            )
            
            # Encrypt message
            plaintext_message = {"type": "test", "nonce_test": True}
            
            encrypted = await e2ee_manager.encrypt_message(
                message=plaintext_message,
                sender_id=self.test_user_a,
                recipient_id=self.test_user_b,
                room_id=self.test_room_id
            )
            
            # First decryption should work
            decrypted1 = await e2ee_manager.decrypt_message(
                encrypted=encrypted,
                recipient_id=self.test_user_b
            )
            
            assert decrypted1 == plaintext_message
            print("   First decryption: success")
            
            # Second attempt with same message should fail (replay attack)
            try:
                await e2ee_manager.decrypt_message(
                    encrypted=encrypted,
                    recipient_id=self.test_user_b
                )
                print("❌ Test 6 FAILED: Replay attack should be prevented")
                return False
            except ValueError as e:
                assert "Replay attack" in str(e)
                print(f"   Replay attack prevented: {e}")
            
            print("✅ Test 6 PASSED: Replay attack prevention works")
            return True
            
        except Exception as e:
            print(f"❌ Test 6 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_key_rotation(self):
        """Test 7: Key Rotation"""
        print("\n🧪 Test 7: Key Rotation")
        
        try:
            # Generate initial key
            old_key = await e2ee_manager.generate_key_pair(
                user_id=self.test_user_a,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            
            print(f"   Old key ID: {old_key['key_id']}")
            
            # Wait a moment to ensure different timestamp
            await asyncio.sleep(0.01)
            
            # Rotate key
            new_key = await e2ee_manager.rotate_key(
                user_id=self.test_user_a,
                room_id=self.test_room_id
            )
            
            print(f"   New key ID: {new_key['key_id']}")
            
            assert new_key["key_id"] != old_key["key_id"]
            assert new_key["public_key"] != old_key["public_key"]
            
            # Verify new key is now the latest
            latest_key = await e2ee_manager.get_public_key(
                user_id=self.test_user_a,
                room_id=self.test_room_id
            )
            
            assert latest_key["key_id"] == new_key["key_id"]
            
            print("✅ Test 7 PASSED: Key rotation works")
            return True
            
        except Exception as e:
            print(f"❌ Test 7 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_key_revocation(self):
        """Test 8: Key Revocation"""
        print("\n🧪 Test 8: Key Revocation")
        
        try:
            # Generate key
            key_pair = await e2ee_manager.generate_key_pair(
                user_id=self.test_user_a,
                room_id=self.test_room_id,
                key_type=KeyType.EPHEMERAL
            )
            
            key_id = key_pair["key_id"]
            print(f"   Generated key: {key_id}")
            
            # Verify key exists
            public_key = await e2ee_manager.get_public_key(
                user_id=self.test_user_a,
                room_id=self.test_room_id
            )
            
            assert public_key is not None
            print(f"   Key exists: {public_key['key_id']}")
            
            # Revoke key
            success = await e2ee_manager.revoke_key(
                user_id=self.test_user_a,
                room_id=self.test_room_id,
                key_id=key_id
            )
            
            assert success is True
            print(f"   Key revoked: {success}")
            
            # Verify key is gone
            public_key_after = await e2ee_manager.get_public_key(
                user_id=self.test_user_a,
                room_id=self.test_room_id
            )
            
            assert public_key_after is None
            print("   Key no longer exists")
            
            print("✅ Test 8 PASSED: Key revocation works")
            return True
            
        except Exception as e:
            print(f"❌ Test 8 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_multiple_users(self):
        """Test 9: Multiple Users"""
        print("\n🧪 Test 9: Multiple Users (Group Encryption)")
        
        try:
            # Generate keys for all users
            for user_id in [self.test_user_a, self.test_user_b, self.test_user_c]:
                await e2ee_manager.generate_key_pair(
                    user_id=user_id,
                    room_id=self.test_room_id,
                    key_type=KeyType.EPHEMERAL
                )
            
            # Exchange keys between all pairs
            pairs = [
                (self.test_user_a, self.test_user_b),
                (self.test_user_a, self.test_user_c),
                (self.test_user_b, self.test_user_c)
            ]
            
            for user_a, user_b in pairs:
                await e2ee_manager.exchange_keys(
                    user_a_id=user_a,
                    user_b_id=user_b,
                    room_id=self.test_room_id
                )
                print(f"   Exchanged keys: {user_a} ↔ {user_b}")
            
            # Test encryption between all pairs
            plaintext = {"type": "group_test", "message": "Multi-user test"}
            
            for sender, recipient in pairs:
                encrypted = await e2ee_manager.encrypt_message(
                    message=plaintext,
                    sender_id=sender,
                    recipient_id=recipient,
                    room_id=self.test_room_id
                )
                
                decrypted = await e2ee_manager.decrypt_message(
                    encrypted=encrypted,
                    recipient_id=recipient
                )
                
                assert decrypted == plaintext
                print(f"   Verified: {sender} → {recipient}")
            
            print("✅ Test 9 PASSED: Multiple users work correctly")
            return True
            
        except Exception as e:
            print(f"❌ Test 9 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_cleanup(self):
        """Test 10: Cleanup"""
        print("\n🧪 Test 10: Cleanup")
        
        try:
            # Generate keys for user
            for i in range(3):
                await e2ee_manager.generate_key_pair(
                    user_id=self.test_user_a,
                    room_id=self.test_room_id,
                    key_type=KeyType.EPHEMERAL
                )
                await asyncio.sleep(0.01)  # Ensure different timestamps
            
            print(f"   Generated 3 keys for {self.test_user_a}")
            
            # Cleanup
            count = await e2ee_manager.cleanup_user_keys(
                user_id=self.test_user_a,
                room_id=self.test_room_id
            )
            
            assert count == 3
            print(f"   Cleaned up {count} keys")
            
            # Verify no keys remain
            public_key = await e2ee_manager.get_public_key(
                user_id=self.test_user_a,
                room_id=self.test_room_id
            )
            
            assert public_key is None
            print("   No keys remaining")
            
            print("✅ Test 10 PASSED: Cleanup works")
            return True
            
        except Exception as e:
            print(f"❌ Test 10 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def run_all_tests(self):
        """Run all tests."""
        print("=" * 60)
        print("🧪 WebRTC E2EE Feature Test Suite")
        print("=" * 60)
        
        tests = [
            ("Key Pair Generation", self.test_key_pair_generation),
            ("Key Exchange", self.test_key_exchange),
            ("Message Encryption", self.test_message_encryption),
            ("Message Decryption", self.test_message_decryption),
            ("Signature Verification", self.test_signature_verification),
            ("Replay Attack Prevention", self.test_replay_attack_prevention),
            ("Key Rotation", self.test_key_rotation),
            ("Key Revocation", self.test_key_revocation),
            ("Multiple Users", self.test_multiple_users),
            ("Cleanup", self.test_cleanup),
        ]
        
        results = []
        
        for test_name, test_func in tests:
            # Cleanup before each test
            await self.cleanup()
            
            try:
                result = await test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ Test '{test_name}' crashed: {e}")
                results.append((test_name, False))
        
        # Final cleanup
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}: {test_name}")
        
        print("=" * 60)
        print(f"Passed: {passed}/{total} tests")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"⚠️  {total - passed} test(s) failed")
        
        print("=" * 60)
        
        return passed == total


async def main():
    """Main test runner."""
    try:
        # Run tests
        tester = TestE2EEFeature()
        success = await tester.run_all_tests()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
