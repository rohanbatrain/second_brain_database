#!/usr/bin/env python3
"""
Setup RAG User - Create a user and permanent token for RAG system testing

This script:
1. Creates a new user account (or uses existing)
2. Generates a permanent token
3. Saves the token to rag_token.txt for easy access
4. Verifies the token works with RAG endpoints

Usage:
    python scripts/setup_rag_user.py
    python scripts/setup_rag_user.py --username my_user --email my@email.com
    python scripts/setup_rag_user.py --base-url http://localhost:8001
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import httpx


class RAGUserSetup:
    """Handles RAG user setup and token generation"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=30.0)
    
    def register_user(self, username: str, email: str, password: str) -> dict:
        """Register a new user account"""
        url = f"{self.base_url}/auth/register"
        payload = {
            "username": username,
            "email": email,
            "password": password,
        }
        
        print(f"🔐 Registering user: {username} ({email})")
        
        try:
            response = self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            print(f"✅ User registered successfully")
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                # User might already exist
                error_data = e.response.json()
                if "already exists" in str(error_data.get("detail", "")):
                    print(f"ℹ️  User already exists, attempting login...")
                    return self.login_user(username, password)
            print(f"❌ Registration failed: {e.response.status_code}")
            print(f"   {e.response.text}")
            raise
    
    def login_user(self, username: str, password: str) -> dict:
        """Login with existing user"""
        url = f"{self.base_url}/auth/login"
        # OAuth2 login expects form data, not JSON
        data = {
            "username": username,
            "password": password,
        }
        
        print(f"🔑 Logging in as: {username}")
        
        try:
            response = self.client.post(url, data=data)
            response.raise_for_status()
            result = response.json()
            print(f"✅ Login successful")
            return result
        except httpx.HTTPStatusError as e:
            print(f"❌ Login failed: {e.response.status_code}")
            print(f"   {e.response.text}")
            raise
    
    def create_permanent_token(
        self, 
        access_token: str, 
        description: str = "RAG System Token",
        ip_restrictions: Optional[list] = None
    ) -> dict:
        """Create a permanent token"""
        url = f"{self.base_url}/auth/permanent-tokens"
        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {"description": description}
        
        if ip_restrictions:
            payload["ip_restrictions"] = ip_restrictions
        
        print(f"🎫 Creating permanent token: {description}")
        
        try:
            response = self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            print(f"✅ Permanent token created")
            return data
        except httpx.HTTPStatusError as e:
            print(f"❌ Token creation failed: {e.response.status_code}")
            print(f"   {e.response.text}")
            raise
    
    def verify_token(self, token: str) -> bool:
        """Verify token works with RAG health endpoint"""
        url = f"{self.base_url}/rag/health"
        
        print(f"🔍 Verifying token with RAG health endpoint...")
        print(f"   URL: {url}")
        
        try:
            response = self.client.get(url)
            if response.status_code == 200:
                print(f"✅ RAG system is healthy")
                return True
            else:
                print(f"⚠️  RAG health check returned: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ RAG health check failed: {e}")
            return False
    
    def verify_auth(self, token: str) -> bool:
        """Verify token works with authenticated endpoint"""
        url = f"{self.base_url}/rag/status"
        headers = {"Authorization": f"Bearer {token}"}
        
        print(f"🔍 Verifying authentication with RAG status endpoint...")
        print(f"   URL: {url}")
        print(f"   Token (first 50 chars): {token[:50]}...")
        
        try:
            response = self.client.get(url, headers=headers)
            
            print(f"   Response Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✅ Authentication successful")
                data = response.json()
                print(f"   RAG Status: {data.get('status', 'unknown')}")
                print(f"   Document Count: {data.get('document_count', 'N/A')}")
                return True
            elif response.status_code == 422:
                print(f"⚠️  Unprocessable Entity (422)")
                try:
                    error_data = response.json()
                    print(f"   Error Detail: {error_data}")
                    
                    # Check if it's a validation error
                    if "detail" in error_data:
                        details = error_data["detail"]
                        if isinstance(details, list) and len(details) > 0:
                            first_error = details[0]
                            if first_error.get("loc") == ["query", "token"]:
                                print(f"\n   💡 The endpoint is expecting token as query param, not header")
                                print(f"      This might be an OAuth2 configuration issue")
                except:
                    print(f"   Raw Response: {response.text[:300]}")
                return False
            elif response.status_code == 401:
                print(f"⚠️  Unauthorized (401) - Invalid or expired token")
                print(f"   Response: {response.text[:200]}")
                return False
            else:
                print(f"⚠️  Unexpected status code: {response.status_code}")
                print(f"   Response: {response.text[:300]}")
                return False
        except Exception as e:
            print(f"❌ Auth verification failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_token(self, token: str, filename: str = "rag_token.txt") -> bool:
        """Save token to file"""
        try:
            # Get project root (parent of scripts directory)
            script_dir = Path(__file__).parent
            project_root = script_dir.parent
            token_file = project_root / filename
            
            token_file.write_text(token)
            print(f"💾 Token saved to: {token_file}")
            print(f"   You can now use this token with the Streamlit app")
            return True
        except Exception as e:
            print(f"❌ Failed to save token: {e}")
            return False
    
    def close(self):
        """Close HTTP client"""
        self.client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Setup RAG user and generate permanent token",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default settings
  python scripts/setup_rag_user.py
  
  # Custom user
  python scripts/setup_rag_user.py --username john --email john@example.com
  
  # Different API URL
  python scripts/setup_rag_user.py --base-url http://localhost:8001
  
  # With IP restrictions
  python scripts/setup_rag_user.py --ip-restrictions 127.0.0.1 192.168.1.0/24
        """
    )
    
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the Second Brain Database API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--username",
        default="rag_user",
        help="Username for the RAG user (default: rag_user)"
    )
    parser.add_argument(
        "--email",
        default="rag@example.com",
        help="Email for the RAG user (default: rag@example.com)"
    )
    parser.add_argument(
        "--password",
        default="RAGPassword123!",
        help="Password for the RAG user (default: RAGPassword123!)"
    )
    parser.add_argument(
        "--token-desc",
        default="RAG System Token",
        help="Description for the permanent token"
    )
    parser.add_argument(
        "--ip-restrictions",
        nargs="*",
        help="Optional IP restrictions (space separated)"
    )
    parser.add_argument(
        "--output",
        default="rag_token.txt",
        help="Output file for the token (default: rag_token.txt)"
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip token verification"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("RAG User Setup")
    print("=" * 60)
    print(f"API URL: {args.base_url}")
    print(f"Username: {args.username}")
    print(f"Email: {args.email}")
    print("=" * 60)
    print()
    
    setup = RAGUserSetup(args.base_url)
    
    try:
        # Step 1: Register or login user
        auth_result = setup.register_user(args.username, args.email, args.password)
        access_token = auth_result.get("access_token")
        
        if not access_token:
            print("❌ No access token received from server")
            print(f"   Response: {json.dumps(auth_result, indent=2)}")
            sys.exit(1)
        
        print()
        
        # Step 2: Create permanent token
        token_result = setup.create_permanent_token(
            access_token,
            description=args.token_desc,
            ip_restrictions=args.ip_restrictions
        )
        
        permanent_token = token_result.get("token")
        token_id = token_result.get("token_id")
        
        if not permanent_token:
            print("❌ No permanent token received from server")
            print(f"   Response: {json.dumps(token_result, indent=2)}")
            sys.exit(1)
        
        print()
        print("=" * 60)
        print("🎉 SUCCESS! Permanent Token Created")
        print("=" * 60)
        print(f"Token ID: {token_id}")
        print(f"Description: {args.token_desc}")
        if args.ip_restrictions:
            print(f"IP Restrictions: {', '.join(args.ip_restrictions)}")
        print()
        print("⚠️  IMPORTANT: Store this token securely!")
        print("   It will only be shown once.")
        print()
        print(f"Token: {permanent_token}")
        print("=" * 60)
        print()
        
        # Step 3: Save token to file
        if setup.save_token(permanent_token, args.output):
            print()
        
        # Step 4: Verify token (unless skipped)
        if not args.skip_verify:
            print()
            print("=" * 60)
            print("Verification")
            print("=" * 60)
            
            # Check RAG health
            setup.verify_token(permanent_token)
            print()
            
            # Check authentication
            auth_ok = setup.verify_auth(permanent_token)
            print()
            
            if auth_ok:
                print("=" * 60)
                print("✅ All checks passed! You're ready to use the RAG system")
                print("=" * 60)
                print()
                print("Next steps:")
                print("  1. Run the Streamlit app: ./start_streamlit_app.sh")
                print("  2. Load the token in the app using the sidebar")
                print("  3. Start uploading documents and querying!")
            else:
                print("=" * 60)
                print("⚠️  Token created but authentication verification failed")
                print("=" * 60)
                print()
                print("The token was created and saved, but there may be an issue")
                print("with the RAG endpoint authentication. Check the logs for details.")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        setup.close()


if __name__ == "__main__":
    main()
