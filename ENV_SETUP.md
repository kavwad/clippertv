# Environment Variable Setup for Phase 1: Multi-User Backend

This document explains how to set up the required environment variables for ClipperTV's authentication and multi-user features.

## Quick Start ✅

**Your environment is already configured!** Run this to verify:

```bash
uv run python scripts/test_env.py
```

You should see:
```
SUCCESS: All environment variables validated!
```

Your `.env` file has been created with:
- ✅ Turso database credentials
- ✅ JWT secret key (freshly generated)
- ✅ Encryption key (freshly generated)
- ✅ Development configuration

**What's already set up:**
- `.env` - Your local environment variables (not committed to git)
- `.env.example` - Template for other developers
- `.streamlit/secrets.toml` - Updated with auth keys for Streamlit

---

## Required Environment Variables

### Database Configuration

```bash
# Turso database URL (already configured)
TURSO_DATABASE_URL=libsql://your-database.turso.io

# Turso authentication token (already configured)
TURSO_AUTH_TOKEN=your_turso_auth_token_here
```

### Authentication Configuration

```bash
# JWT Secret Key (for signing authentication tokens)
# Generate with: openssl rand -hex 32
JWT_SECRET_KEY=your_jwt_secret_key_here

# Encryption Key (for encrypting Clipper credentials)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_fernet_encryption_key_here
```

### Email Configuration (Optional - for Phase 1.5)

```bash
# Email service provider (default: resend)
EMAIL_PROVIDER=resend

# Email API key from Resend
EMAIL_API_KEY=re_your_resend_api_key

# From address for emails
EMAIL_FROM=ClipperTV <reports@clippertv.app>
```

### Application Configuration

```bash
# Application URL (default: http://localhost:8501)
APP_URL=https://clippertv.app
```

## Generating Secret Keys

### JWT Secret Key

The JWT secret key is used to sign authentication tokens. Generate a secure 32-byte hex string:

```bash
openssl rand -hex 32
```

Example output:
```
a3f8e9d2c1b4a5f6e7d8c9b0a1f2e3d4c5b6a7f8e9d0c1b2a3f4e5d6c7b8a9f0
```

Add this to your `.env` file:
```bash
JWT_SECRET_KEY=a3f8e9d2c1b4a5f6e7d8c9b0a1f2e3d4c5b6a7f8e9d0c1b2a3f4e5d6c7b8a9f0
```

### Encryption Key

The encryption key is used to encrypt Clipper account credentials stored in the database. Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Example output:
```
9Xj7kL3pQw8RtYu1IoPa2SdFg4HjK6lZxCvBn5MnEr8=
```

Add this to your `.env` file:
```bash
ENCRYPTION_KEY=9Xj7kL3pQw8RtYu1IoPa2SdFg4HjK6lZxCvBn5MnEr8=
```

## Setting Up Your .env File

1. Create a `.env` file in the project root:

```bash
touch .env
```

2. Add all required variables:

```bash
# Database
TURSO_DATABASE_URL=libsql://your-database.turso.io
TURSO_AUTH_TOKEN=your_turso_auth_token

# Authentication
JWT_SECRET_KEY=your_generated_jwt_secret_key
ENCRYPTION_KEY=your_generated_encryption_key

# Email (optional for Phase 1.5)
EMAIL_PROVIDER=resend
EMAIL_API_KEY=re_your_api_key
EMAIL_FROM=ClipperTV <reports@clippertv.app>

# App
APP_URL=http://localhost:8501
```

3. **Important**: Add `.env` to `.gitignore` to prevent committing secrets:

```bash
echo ".env" >> .gitignore
```

## Validating Configuration

You can validate that your configuration is set up correctly:

```python
from clippertv.config import env_config

# Validate basic configuration
env_config.validate()

# Validate authentication configuration
env_config.validate_auth()
```

If any required variables are missing, you'll see a helpful error message with instructions.

## Security Best Practices

1. **Never commit secrets to version control**: Always use `.env` files and keep them out of git
2. **Rotate keys periodically**: Consider rotating JWT and encryption keys on a regular schedule
3. **Use different keys for different environments**: Development, staging, and production should have different keys
4. **Store production keys securely**: Use a secrets manager (like AWS Secrets Manager, HashiCorp Vault, or your hosting platform's secrets management)

## Development vs Production

### Development

For local development, storing secrets in a `.env` file is acceptable:

```bash
# .env (local development only)
JWT_SECRET_KEY=dev-secret-key-not-for-production
ENCRYPTION_KEY=dev-encryption-key-not-for-production
```

### Production

For production deployments, use your hosting platform's secrets management:

**Vercel/Netlify:**
- Add environment variables through the dashboard
- They're encrypted at rest and injected at runtime

**AWS:**
- Use AWS Secrets Manager or Parameter Store
- Access via IAM roles

**Docker:**
- Use Docker secrets or environment variables
- Never hardcode in Dockerfiles

## Troubleshooting

### "Missing required config" error

If you see this error, ensure all required environment variables are set:

```python
ValueError: Missing required config: JWT_SECRET_KEY, ENCRYPTION_KEY
```

Solution: Generate and add the missing keys to your `.env` file.

### "Missing required auth config" error

This means authentication-specific variables are not set. The error message includes instructions for generating them:

```
Generate keys with:
  JWT_SECRET_KEY: openssl rand -hex 32
  ENCRYPTION_KEY: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Encryption key format error

If you get a Fernet key format error, ensure your encryption key:
- Is a valid base64-encoded string
- Was generated using `Fernet.generate_key()`
- Hasn't been truncated or modified

## Next Steps

After setting up environment variables:

1. Run the database migration:
   ```bash
   uv run python migrations/run_migration.py
   ```

2. Run tests to verify setup:
   ```bash
   uv run pytest tests/test_auth.py -v
   uv run pytest tests/test_user_store.py -v
   ```

3. Start the application:
   ```bash
   uv run streamlit run src/clippertv/app.py
   ```
