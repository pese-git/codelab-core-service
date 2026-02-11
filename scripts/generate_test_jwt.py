#!/usr/bin/env python3
"""Generate test JWT token for API testing."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from jose import jwt

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings


def generate_test_token(
    user_id: str | UUID | None = None,
    expire_minutes: int | None = None,
) -> str:
    """
    Generate a test JWT token.
    
    Args:
        user_id: User UUID (generates random if not provided)
        expire_minutes: Token expiration in minutes (uses settings default if not provided)
    
    Returns:
        JWT token string
    """
    settings = get_settings()
    
    # Generate or validate user_id
    if user_id is None:
        user_id = uuid4()
    elif isinstance(user_id, str):
        try:
            user_id = UUID(user_id)
        except ValueError:
            raise ValueError(f"Invalid UUID format: {user_id}")
    
    # Calculate expiration
    if expire_minutes is None:
        expire_minutes = settings.jwt_access_token_expire_minutes
    
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)
    
    # Create payload
    payload = {
        "sub": str(user_id),  # Subject (user_id)
        "iat": int(now.timestamp()),  # Issued at
        "exp": int(expire.timestamp()),  # Expiration
    }
    
    # Generate token
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    
    return token


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate test JWT token for API testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate token with random user_id (30 min expiration)
  python scripts/generate_test_jwt.py
  
  # Generate token with specific user_id
  python scripts/generate_test_jwt.py --user-id 123e4567-e89b-12d3-a456-426614174000
  
  # Generate token with 60 minutes expiration
  python scripts/generate_test_jwt.py --expire 60
  
  # Generate long-lived token (24 hours)
  python scripts/generate_test_jwt.py --expire 1440
        """,
    )
    
    parser.add_argument(
        "--user-id",
        type=str,
        help="User UUID (generates random if not provided)",
    )
    
    parser.add_argument(
        "--expire",
        type=int,
        help="Token expiration in minutes (default: from settings)",
    )
    
    parser.add_argument(
        "--decode",
        action="store_true",
        help="Also decode and display token payload",
    )
    
    args = parser.parse_args()
    
    try:
        # Generate token
        token = generate_test_token(
            user_id=args.user_id,
            expire_minutes=args.expire,
        )
        
        print("=" * 80)
        print("🔐 TEST JWT TOKEN GENERATED")
        print("=" * 80)
        print()
        print("Token:")
        print(token)
        print()
        
        # Decode if requested
        if args.decode:
            settings = get_settings()
            decoded = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            
            print("-" * 80)
            print("Decoded Payload:")
            print("-" * 80)
            print(f"  sub (user_id): {decoded['sub']}")
            print(f"  iat (issued):  {datetime.fromtimestamp(decoded['iat'], tz=timezone.utc).isoformat()}")
            print(f"  exp (expires): {datetime.fromtimestamp(decoded['exp'], tz=timezone.utc).isoformat()}")
            print()
        
        print("-" * 80)
        print("Usage in Swagger UI (/docs):")
        print("-" * 80)
        print("1. Click 'Authorize' button 🔓")
        print("2. Paste token above (WITHOUT 'Bearer' prefix)")
        print("3. Click 'Authorize'")
        print()
        
        print("-" * 80)
        print("Usage in curl:")
        print("-" * 80)
        print(f'curl -X GET "http://localhost:8000/my/agents/" \\')
        print(f'  -H "Authorization: Bearer {token}" \\')
        print(f'  -H "Content-Type: application/json"')
        print()
        
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
