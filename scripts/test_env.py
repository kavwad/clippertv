#!/usr/bin/env python
"""Test environment configuration."""

import os
from pathlib import Path

# Load .env file
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    os.environ[key] = value

# Now test the config
from clippertv.config import env_config

print("Testing environment configuration...")
print("=" * 60)

try:
    env_config.validate()
    print("✓ Database configuration validated")
except ValueError as e:
    print(f"✗ Database configuration error: {e}")
    exit(1)

try:
    env_config.validate_auth()
    print("✓ Authentication configuration validated")
except ValueError as e:
    print(f"✗ Authentication configuration error: {e}")
    exit(1)

print("=" * 60)
print("SUCCESS: All environment variables validated!")
print()
print("Configuration summary:")
print(f"  Database URL: {env_config.TURSO_DATABASE_URL[:50]}...")
print(f"  JWT Secret: {env_config.JWT_SECRET_KEY[:20]}...")
print(f"  Encryption Key: {env_config.ENCRYPTION_KEY[:20]}...")
print(f"  App URL: {env_config.APP_URL}")
