# ClipperTV Migration & Feature Roadmap

**Strategy:** Backend-First Hybrid Approach with Quick Wins

**Total Duration:** 6-7 weeks
**Last Updated:** 2025-10-27

---

## Overview

This plan migrates ClipperTV from Streamlit to Reflex while adding multi-user authentication and automated monthly reports. The phased approach minimizes risk and delivers user value incrementally.

### Key Principles

- **Backend-first:** De-risk auth and data model changes before touching UI
- **No throwaway work:** Don't build Streamlit UI features we'll discard
- **Quick wins:** Ship email reports while working on larger migration
- **Framework-agnostic logic:** Keep business logic separate from UI framework

---

## Version Control Workflow

This project uses **Jujutsu (jj)** with a **squash/absorb workflow** for clean, incremental development.

### Why jj Squash Workflow?

- **Incremental commits:** Make small, frequent commits as you work
- **Clean history:** Squash related changes into logical commits before review
- **Easy fixups:** Use `jj squash` to absorb changes into previous commits
- **Phase isolation:** Each phase gets its own commit(s) for easy review and rollback

### Workflow Pattern

**During Development (Make frequent micro-commits):**

```bash
# Make changes to a file
jj commit -m "wip: add User model"

# Make more changes
jj commit -m "wip: add password hashing"

# Fix a bug in previous commit
jj commit -m "wip: fix User model validation"

# Add tests
jj commit -m "wip: add auth service tests"
```

**Before Review (Squash into logical commits):**

```bash
# View your commit history
jj log

# Squash the last 3 commits into one
jj squash --from <commit-id> --into <parent-commit-id>

# Or use interactive squash
jj squash -i

# Result: Clean commit like "feat: Add multi-user authentication backend"
```

### Commit Organization by Phase

**Phase 1: Multi-User Backend**
```bash
# Suggested commit structure after squashing:
1. feat: Add user account models and authentication service
2. feat: Add Clipper card encryption and user store
3. feat: Update transaction store for multi-user row-level security
4. test: Add comprehensive auth and user store tests
5. docs: Update configuration for JWT and encryption keys
```

**Phase 1.5: Monthly Email Reports**
```bash
1. refactor: Extract summary generation into framework-agnostic SummaryGenerator
2. feat: Add email service with Resend integration
3. feat: Add chart export for email embedding
4. feat: Integrate email reports with scheduler
5. test: Add email service tests
```

**Phase 2: Reflex Migration**
```bash
1. feat: Set up Reflex app structure and state management
2. feat: Add login, signup, and onboarding pages
3. feat: Migrate dashboard components to Reflex
4. feat: Migrate PDF upload and manual entry to Reflex
5. feat: Update email deep links for Reflex URLs
6. test: Add E2E tests for Reflex app
7. chore: Remove Streamlit dependencies
```

### Useful jj Commands for This Project

```bash
# Start working on Phase 1
jj describe -m "feat: Start Phase 1 - multi-user backend"

# View commit graph
jj log --graph

# Absorb changes into a specific commit (by description match)
jj squash --into <commit-id>

# Amend the current commit
jj describe -m "Updated description"

# Create a new change on top of current
jj new

# Squash all WIP commits from Phase 1 into one
jj squash --from <first-wip-commit> --into <phase1-start-commit>

# Move to a different commit to continue work
jj edit <commit-id>

# View what changed in a commit
jj diff -r <commit-id>
```

### Best Practices

1. **Commit early, commit often** during development
   - Don't worry about perfect commit messages during active work
   - Use `wip:` prefix for work-in-progress commits

2. **Squash before pushing** or creating PRs
   - Group related changes into logical commits
   - Write clear, descriptive commit messages
   - Follow conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`

3. **One commit per logical unit**
   - Database schema changes = 1 commit
   - New service implementation + tests = 1 commit
   - Each phase milestone = 1-5 commits max

4. **Test before squashing**
   - Run `uv run pytest` to ensure tests pass
   - Run `uv run mypy src/` for type checking
   - Squash only when you're confident in the changes

5. **Keep phases separate**
   - Don't mix Phase 1 and Phase 1.5 changes in the same commit
   - Makes rollback easier if needed
   - Clearer history for future reference

### Example Phase 1 Workflow

```bash
# Start Phase 1
jj new -m "feat: Start Phase 1 - multi-user backend"

# Work on database models (make many small commits)
# ... edit files ...
jj commit -m "wip: add User model"
jj commit -m "wip: add ClipperCard model"
jj commit -m "wip: fix User email validation"

# Work on auth service
jj commit -m "wip: add AuthService"
jj commit -m "wip: add JWT token generation"
jj commit -m "wip: add password hashing with bcrypt"

# Work on user store
jj commit -m "wip: add UserStore"
jj commit -m "wip: add create_user method"
jj commit -m "wip: add Clipper card methods"

# Add tests
jj commit -m "wip: add auth service tests"
jj commit -m "wip: add user store tests"

# View your work
jj log --limit 10

# Squash into logical commits
jj squash -i  # Interactive mode to choose what to squash

# Final result: 3 clean commits
# 1. feat: Add user account models and authentication service
# 2. feat: Add user and Clipper card data access layer
# 3. test: Add comprehensive authentication tests
```

### Recovery and Rollback

```bash
# If you need to undo a squash
jj undo

# View operation history
jj op log

# Restore to a previous operation
jj op restore <operation-id>

# Abandon a change you don't want
jj abandon <commit-id>
```

---

## Phase 1: Multi-User Backend Infrastructure

**Duration:** 2 weeks
**Goal:** Build production-ready authentication and user management without touching UI

### Database Schema Changes

**New Tables:**

```sql
-- Users table
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Clipper cards table (many-to-one with users)
CREATE TABLE clipper_cards (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    card_number TEXT NOT NULL,
    rider_name TEXT NOT NULL,
    credentials_encrypted TEXT, -- For automated downloads
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, card_number)
);

-- Update existing riders table
ALTER TABLE riders ADD COLUMN user_id TEXT REFERENCES users(id);
ALTER TABLE riders ADD COLUMN clipper_card_id TEXT REFERENCES clipper_cards(id);
```

**Update Transactions Table:**
```sql
-- Add user_id for row-level security
ALTER TABLE transactions ADD COLUMN user_id TEXT REFERENCES users(id);

-- Create index for performance
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_rider_date ON transactions(rider, date);
```

### Data Models

**File:** `src/clippertv/data/models.py`

Add new Pydantic models:

```python
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

class User(BaseModel):
    """User account model."""
    id: str
    email: EmailStr
    name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class UserCreate(BaseModel):
    """User registration payload."""
    email: EmailStr
    password: str  # Will be hashed before storage
    name: Optional[str] = None

class UserLogin(BaseModel):
    """User login payload."""
    email: EmailStr
    password: str

class ClipperCard(BaseModel):
    """Clipper card associated with user."""
    id: str
    user_id: str
    card_number: str
    rider_name: str
    credentials_encrypted: Optional[str] = None
    is_primary: bool = False
    created_at: datetime = Field(default_factory=datetime.now)

class ClipperCardCreate(BaseModel):
    """Clipper card registration payload."""
    card_number: str
    rider_name: str
    credentials: Optional[dict] = None  # {username, password} - will be encrypted
    is_primary: bool = False

class AuthToken(BaseModel):
    """JWT authentication token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
```

### Authentication Service

**New File:** `src/clippertv/auth/service.py`

```python
"""Authentication service using JWT tokens."""

from datetime import datetime, timedelta
from typing import Optional
import bcrypt
import jwt
from ..data.models import User, UserCreate, UserLogin, AuthToken

class AuthService:
    """Handles user authentication and token management."""

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expiry = timedelta(days=7)

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode(), password_hash.encode())

    def create_access_token(self, user_id: str, email: str) -> AuthToken:
        """Generate JWT access token."""
        expire = datetime.utcnow() + self.token_expiry
        payload = {
            "sub": user_id,
            "email": email,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return AuthToken(
            access_token=token,
            expires_in=int(self.token_expiry.total_seconds())
        )

    def verify_token(self, token: str) -> Optional[dict]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
```

**New File:** `src/clippertv/auth/crypto.py`

```python
"""Encryption utilities for sensitive data."""

from cryptography.fernet import Fernet
from typing import Optional
import json

class CredentialEncryption:
    """Encrypt/decrypt Clipper credentials."""

    def __init__(self, encryption_key: str):
        self.cipher = Fernet(encryption_key.encode())

    def encrypt_credentials(self, username: str, password: str) -> str:
        """Encrypt Clipper login credentials."""
        data = json.dumps({"username": username, "password": password})
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt_credentials(self, encrypted: str) -> Optional[dict]:
        """Decrypt Clipper login credentials."""
        try:
            data = self.cipher.decrypt(encrypted.encode()).decode()
            return json.loads(data)
        except Exception:
            return None
```

### User Repository

**New File:** `src/clippertv/data/user_store.py`

```python
"""User and Clipper card data access layer."""

from typing import Optional, List
import uuid
from .turso_client import TursoClient
from .models import User, UserCreate, ClipperCard, ClipperCardCreate
from ..auth.service import AuthService
from ..auth.crypto import CredentialEncryption

class UserStore:
    """Manage user accounts and Clipper cards."""

    def __init__(
        self,
        client: TursoClient,
        auth_service: AuthService,
        crypto: CredentialEncryption
    ):
        self.client = client
        self.auth = auth_service
        self.crypto = crypto

    def create_user(self, user_data: UserCreate) -> User:
        """Register new user account."""
        user_id = str(uuid.uuid4())
        password_hash = self.auth.hash_password(user_data.password)

        self.client.execute(
            """
            INSERT INTO users (id, email, password_hash, name)
            VALUES (?, ?, ?, ?)
            """,
            [user_id, user_data.email, password_hash, user_data.name]
        )

        return self.get_user_by_id(user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Find user by email address."""
        result = self.client.execute(
            "SELECT id, email, name, created_at, updated_at FROM users WHERE email = ?",
            [email]
        )
        if not result.rows:
            return None
        row = result.rows[0]
        return User(
            id=row[0],
            email=row[1],
            name=row[2],
            created_at=row[3],
            updated_at=row[4]
        )

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Find user by ID."""
        result = self.client.execute(
            "SELECT id, email, name, created_at, updated_at FROM users WHERE id = ?",
            [user_id]
        )
        if not result.rows:
            return None
        row = result.rows[0]
        return User(
            id=row[0],
            email=row[1],
            name=row[2],
            created_at=row[3],
            updated_at=row[4]
        )

    def verify_user_credentials(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password."""
        result = self.client.execute(
            "SELECT id, email, name, password_hash, created_at, updated_at FROM users WHERE email = ?",
            [email]
        )
        if not result.rows:
            return None

        row = result.rows[0]
        password_hash = row[3]

        if not self.auth.verify_password(password, password_hash):
            return None

        return User(
            id=row[0],
            email=row[1],
            name=row[2],
            created_at=row[4],
            updated_at=row[5]
        )

    def add_clipper_card(
        self,
        user_id: str,
        card_data: ClipperCardCreate
    ) -> ClipperCard:
        """Associate Clipper card with user account."""
        card_id = str(uuid.uuid4())

        # Encrypt credentials if provided
        credentials_encrypted = None
        if card_data.credentials:
            credentials_encrypted = self.crypto.encrypt_credentials(
                card_data.credentials["username"],
                card_data.credentials["password"]
            )

        # If this is primary card, unset other primary cards for this user
        if card_data.is_primary:
            self.client.execute(
                "UPDATE clipper_cards SET is_primary = false WHERE user_id = ?",
                [user_id]
            )

        self.client.execute(
            """
            INSERT INTO clipper_cards (id, user_id, card_number, rider_name, credentials_encrypted, is_primary)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [card_id, user_id, card_data.card_number, card_data.rider_name, credentials_encrypted, card_data.is_primary]
        )

        return self.get_clipper_card(card_id)

    def get_clipper_card(self, card_id: str) -> Optional[ClipperCard]:
        """Get Clipper card by ID."""
        result = self.client.execute(
            """
            SELECT id, user_id, card_number, rider_name, credentials_encrypted, is_primary, created_at
            FROM clipper_cards WHERE id = ?
            """,
            [card_id]
        )
        if not result.rows:
            return None

        row = result.rows[0]
        return ClipperCard(
            id=row[0],
            user_id=row[1],
            card_number=row[2],
            rider_name=row[3],
            credentials_encrypted=row[4],
            is_primary=row[5],
            created_at=row[6]
        )

    def get_user_clipper_cards(self, user_id: str) -> List[ClipperCard]:
        """Get all Clipper cards for a user."""
        result = self.client.execute(
            """
            SELECT id, user_id, card_number, rider_name, credentials_encrypted, is_primary, created_at
            FROM clipper_cards WHERE user_id = ? ORDER BY is_primary DESC, created_at ASC
            """,
            [user_id]
        )

        cards = []
        for row in result.rows:
            cards.append(ClipperCard(
                id=row[0],
                user_id=row[1],
                card_number=row[2],
                rider_name=row[3],
                credentials_encrypted=row[4],
                is_primary=row[5],
                created_at=row[6]
            ))
        return cards

    def get_decrypted_credentials(self, card_id: str) -> Optional[dict]:
        """Get decrypted Clipper credentials for automated downloads."""
        card = self.get_clipper_card(card_id)
        if not card or not card.credentials_encrypted:
            return None

        return self.crypto.decrypt_credentials(card.credentials_encrypted)
```

### Update Transaction Store for Multi-User

**File:** `src/clippertv/data/turso_store.py`

Add user_id parameter to existing methods:

```python
def get_transactions(self, user_id: str, rider: Optional[str] = None) -> pd.DataFrame:
    """Get all transactions for a user, optionally filtered by rider."""
    query = "SELECT * FROM transactions WHERE user_id = ?"
    params = [user_id]

    if rider:
        query += " AND rider = ?"
        params.append(rider)

    query += " ORDER BY date DESC"

    result = self.client.execute(query, params)
    # ... existing DataFrame conversion logic

def save_transactions(self, user_id: str, transactions: List[TransitTransaction]) -> int:
    """Save transactions with user_id for row-level security."""
    # ... existing hash-based deduplication logic
    # Add user_id to INSERT statement
```

### Configuration Updates

**File:** `src/clippertv/config.py`

Add authentication configuration:

```python
import os
from typing import Optional

class Config:
    """Application configuration."""

    # Database
    TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
    TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

    # Authentication
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # Generate with: openssl rand -hex 32
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_DAYS = 7

    # Encryption
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    # Email (for Phase 1.5)
    EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "resend")
    EMAIL_API_KEY = os.getenv("EMAIL_API_KEY")
    EMAIL_FROM = os.getenv("EMAIL_FROM", "ClipperTV <reports@clippertv.app>")

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        required = [
            ("TURSO_DATABASE_URL", cls.TURSO_DATABASE_URL),
            ("TURSO_AUTH_TOKEN", cls.TURSO_AUTH_TOKEN),
            ("JWT_SECRET_KEY", cls.JWT_SECRET_KEY),
            ("ENCRYPTION_KEY", cls.ENCRYPTION_KEY),
        ]

        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")
```

### Testing

**New File:** `tests/test_auth.py`

```python
"""Test authentication service."""

import pytest
from src.clippertv.auth.service import AuthService
from src.clippertv.data.models import UserCreate, UserLogin

@pytest.fixture
def auth_service():
    return AuthService(secret_key="test-secret-key-32-characters-long!")

def test_password_hashing(auth_service):
    """Test password hashing and verification."""
    password = "secure_password_123"
    hashed = auth_service.hash_password(password)

    assert auth_service.verify_password(password, hashed)
    assert not auth_service.verify_password("wrong_password", hashed)

def test_jwt_token_creation(auth_service):
    """Test JWT token generation and verification."""
    user_id = "user-123"
    email = "test@example.com"

    token = auth_service.create_access_token(user_id, email)
    assert token.access_token
    assert token.token_type == "bearer"

    payload = auth_service.verify_token(token.access_token)
    assert payload["sub"] == user_id
    assert payload["email"] == email

def test_invalid_token(auth_service):
    """Test invalid token verification."""
    assert auth_service.verify_token("invalid-token") is None
```

**New File:** `tests/test_user_store.py`

```python
"""Test user data store."""

import pytest
from src.clippertv.data.user_store import UserStore
from src.clippertv.data.models import UserCreate, ClipperCardCreate

# TODO: Implement with test database fixture
```

### Dependencies

**Update:** `pyproject.toml`

```toml
[project]
dependencies = [
    # Existing dependencies...
    "pyjwt>=2.8.0",
    "bcrypt>=4.1.2",
    "cryptography>=41.0.7",
    "python-multipart>=0.0.6",  # For form data in Reflex
]
```

Run: `uv sync`

### Phase 1 Checklist

- [ ] Create database migration script for new tables
- [ ] Implement User and ClipperCard Pydantic models
- [ ] Implement AuthService with JWT tokens
- [ ] Implement CredentialEncryption
- [ ] Implement UserStore with all CRUD operations
- [ ] Update TursoStore to filter by user_id
- [ ] Add configuration for JWT and encryption keys
- [ ] Write unit tests for auth service
- [ ] Write integration tests for user store
- [ ] Generate and document environment variables
- [ ] Test end-to-end user registration → login → data access

### Success Criteria

- ✅ New user can be created via Python API
- ✅ User can authenticate and receive JWT token
- ✅ Token verification correctly identifies user
- ✅ Clipper card can be associated with user
- ✅ Credentials are encrypted in database
- ✅ Transactions are filtered by user_id
- ✅ All tests pass
- ✅ No Streamlit UI changes (app still works for existing usage)

---

## Phase 1.5: Monthly Email Reports

**Duration:** 1 week
**Goal:** Send automated monthly recaps after each ingestion run

### Summary Text Refactor

**Current Issue:** Text summary in `viz/dashboard.py` uses Streamlit-specific markdown syntax.

**Solution:** Extract into framework-agnostic function with multiple output formats.

**New File:** `src/clippertv/viz/summary.py`

```python
"""Generate transit usage summaries in multiple formats."""

from typing import Literal
from datetime import datetime
import pandas as pd

SummaryFormat = Literal["html", "markdown", "plain"]

class SummaryGenerator:
    """Generate text summaries for dashboards and email reports."""

    def __init__(self, stats: dict, rider: str):
        self.stats = stats
        self.rider = rider

    def generate(self, format: SummaryFormat = "html") -> str:
        """Generate summary in specified format."""
        if format == "html":
            return self._generate_html()
        elif format == "markdown":
            return self._generate_markdown()
        elif format == "plain":
            return self._generate_plain()

    def _generate_html(self) -> str:
        """Generate HTML summary for email reports."""
        return f"""
        <h3>Monthly Recap for {self.rider}</h3>
        <p>
            <strong>{self.rider}</strong> took <strong style="color: #dc3545;">{self.stats['trips_this_month']}</strong> trips in
            {self.stats['most_recent_date'].strftime('%B')}, which cost
            <strong style="color: #dc3545;">${self.stats['cost_this_month']}</strong>.
        </p>
        <p>
            {self.rider} rode <strong>{self.stats['most_used_mode']}</strong> most, at
            <strong>{self.stats['most_used_count']}</strong> times.
            Altogether, {self.rider} took {abs(self.stats['trip_diff'])} {self.stats['trip_diff_text']}
            trips and paid ${abs(self.stats['cost_diff'])} {self.stats['cost_diff_text']}
            than the previous month.
        </p>
        {self._caltrain_pass_html()}
        {self._ytd_html()}
        """

    def _generate_markdown(self) -> str:
        """Generate Streamlit-compatible markdown."""
        return f"""
#### {self.rider} took **:red[{self.stats['trips_this_month']}]** trips in {self.stats['most_recent_date'].strftime('%B')}, which cost **:red[${self.stats['cost_this_month']}]**.

{self.rider} rode **{self.stats['most_used_mode']}** most, at **{self.stats['most_used_count']}** times.
Altogether, {self.rider} took {abs(self.stats['trip_diff'])} {self.stats['trip_diff_text']}
trips and paid ${abs(self.stats['cost_diff'])} {self.stats['cost_diff_text']} than the previous month.

{self._caltrain_pass_markdown()}
{self._ytd_markdown()}
        """.strip()

    def _generate_plain(self) -> str:
        """Generate plain text summary."""
        # Implementation for plain text
        pass

    def _caltrain_pass_html(self) -> str:
        """Generate Caltrain pass analysis in HTML."""
        if not self.stats.get('has_caltrain_pass'):
            return ""

        savings = self.stats['caltrain_pass_savings']
        if savings > 0:
            message = f"saved <strong>${savings}</strong> by using the Caltrain Go Pass instead of paying per ride"
        elif savings < 0:
            message = f"spent an extra <strong>${abs(savings)}</strong> on the Caltrain Go Pass compared to paying per ride"
        else:
            message = "broke even on the Caltrain Go Pass"

        return f"<p>{self.rider} {message}.</p>"

    def _caltrain_pass_markdown(self) -> str:
        """Generate Caltrain pass analysis in Streamlit markdown."""
        # Similar to HTML but with Streamlit syntax
        pass

    def _ytd_html(self) -> str:
        """Generate year-to-date summary in HTML."""
        if self.stats['most_recent_date'].month == 1:
            return ""

        return f"""
        <p>
            So far this year, {self.rider} has taken <strong>{self.stats['trips_ytd']}</strong> trips
            for a total of <strong>${self.stats['cost_ytd']}</strong>.
        </p>
        """

    def _ytd_markdown(self) -> str:
        """Generate year-to-date summary in Streamlit markdown."""
        # Similar to HTML but with Streamlit syntax
        pass
```

**Update:** `src/clippertv/viz/dashboard.py`

Replace `display_summary()` function to use new `SummaryGenerator`:

```python
from .summary import SummaryGenerator, SummaryFormat

def display_summary(df_all: pd.DataFrame, rider: str) -> None:
    """Display summary statistics."""
    stats = calculate_summary_stats(df_all, rider)

    # Generate Streamlit-compatible markdown
    generator = SummaryGenerator(stats, rider)
    summary_text = generator.generate(format="markdown")

    st.markdown(summary_text)
```

### Email Service Integration

**New File:** `src/clippertv/email/service.py`

```python
"""Email service for monthly reports."""

from typing import List, Optional
import resend
from ..config import Config
from ..data.models import User

class EmailService:
    """Send monthly transit reports via email."""

    def __init__(self, api_key: str, from_address: str):
        resend.api_key = api_key
        self.from_address = from_address

    def send_monthly_report(
        self,
        to_email: str,
        rider_name: str,
        summary_html: str,
        chart_urls: List[str],
        dashboard_url: str
    ) -> bool:
        """Send monthly recap email."""
        html = self._build_email_template(
            rider_name=rider_name,
            summary_html=summary_html,
            chart_urls=chart_urls,
            dashboard_url=dashboard_url
        )

        try:
            params = {
                "from": self.from_address,
                "to": to_email,
                "subject": f"Your {rider_name} Transit Recap",
                "html": html,
            }

            resend.Emails.send(params)
            return True
        except Exception as e:
            print(f"Failed to send email to {to_email}: {e}")
            return False

    def _build_email_template(
        self,
        rider_name: str,
        summary_html: str,
        chart_urls: List[str],
        dashboard_url: str
    ) -> str:
        """Build HTML email template."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ClipperTV Monthly Recap</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; margin: 0; padding: 0; background-color: #f6f9fc;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f6f9fc; padding: 40px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700;">
                                ClipperTV
                            </h1>
                            <p style="color: #e0e7ff; margin: 8px 0 0; font-size: 16px;">
                                Your Monthly Transit Recap
                            </p>
                        </td>
                    </tr>

                    <!-- Summary -->
                    <tr>
                        <td style="padding: 40px;">
                            {summary_html}
                        </td>
                    </tr>

                    <!-- Charts -->
                    <tr>
                        <td style="padding: 0 40px 40px;">
                            <h3 style="margin: 0 0 20px; color: #1a202c; font-size: 20px;">
                                Visual Breakdown
                            </h3>
                            {"".join(f'<img src="{url}" alt="Chart" style="width: 100%; margin-bottom: 20px; border-radius: 4px;">' for url in chart_urls)}
                        </td>
                    </tr>

                    <!-- CTA -->
                    <tr>
                        <td style="padding: 0 40px 40px; text-align: center;">
                            <a href="{dashboard_url}" style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                                View Full Dashboard
                            </a>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; text-align: center; border-top: 1px solid #e2e8f0;">
                            <p style="margin: 0; color: #718096; font-size: 14px;">
                                This is an automated report from ClipperTV
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """
```

### Chart Image Generation

**New File:** `src/clippertv/viz/export.py`

```python
"""Export charts as static images for email embedding."""

import plotly.graph_objects as go
from typing import List
import tempfile
import os

class ChartExporter:
    """Export Plotly charts as static images."""

    def export_chart_to_image(self, fig: go.Figure, filename: str) -> str:
        """Export Plotly figure to PNG file."""
        # Requires kaleido: uv add kaleido
        output_path = os.path.join(tempfile.gettempdir(), filename)
        fig.write_image(output_path, width=800, height=500)
        return output_path

    def export_charts_for_email(self, figures: List[go.Figure]) -> List[str]:
        """Export multiple charts and return file paths."""
        paths = []
        for i, fig in enumerate(figures):
            path = self.export_chart_to_image(fig, f"chart_{i}.png")
            paths.append(path)
        return paths
```

Note: For email, we'll either:
1. **Option A:** Upload images to cloud storage (S3, Cloudinary) and use URLs
2. **Option B:** Embed as base64 inline (increases email size)
3. **Option C:** Host charts as endpoints that generate images on-demand

Recommend **Option A** for best deliverability.

### Scheduler Integration

**Update:** `src/clippertv/scheduler/run_ingestion.py`

Add email notification after successful ingestion:

```python
"""Standalone script for scheduled PDF ingestion and email reports."""

from ..pdf.batch_ingest import batch_ingest_rider
from ..data.factory import get_data_store
from ..data.user_store import UserStore
from ..email.service import EmailService
from ..viz.summary import SummaryGenerator
from ..viz.dashboard import calculate_summary_stats
from ..config import Config

def send_monthly_reports():
    """Send email reports to all users after ingestion."""
    Config.validate()

    data_store = get_data_store()
    # TODO: Initialize UserStore
    email_service = EmailService(
        api_key=Config.EMAIL_API_KEY,
        from_address=Config.EMAIL_FROM
    )

    # Get all users
    # For each user:
    #   - Get their Clipper cards
    #   - For each card:
    #       - Generate summary stats
    #       - Generate charts
    #       - Send email

    print("Monthly reports sent successfully")

if __name__ == "__main__":
    # Run ingestion
    batch_ingest_rider("K")
    batch_ingest_rider("B")

    # Send reports
    send_monthly_reports()
```

**Update:** `src/clippertv/scheduler/service.py`

Add scheduled job for monthly reports (runs after ingestion):

```python
from apscheduler.schedulers.background import BackgroundScheduler
from .run_ingestion import send_monthly_reports

def start_scheduler():
    """Start background scheduler for automated tasks."""
    scheduler = BackgroundScheduler()

    # Existing: Ingest PDFs on 1st of each month at 2 AM
    scheduler.add_job(
        func=run_monthly_ingestion,
        trigger="cron",
        day=1,
        hour=2,
        minute=0
    )

    # New: Send email reports 30 minutes after ingestion
    scheduler.add_job(
        func=send_monthly_reports,
        trigger="cron",
        day=1,
        hour=2,
        minute=30
    )

    scheduler.start()
```

### Dependencies

**Update:** `pyproject.toml`

```toml
[project]
dependencies = [
    # Existing dependencies...
    "resend>=0.8.0",
    "kaleido>=0.2.1",  # For Plotly image export
]
```

Run: `uv sync`

### Testing

**New File:** `tests/test_email.py`

```python
"""Test email service."""

import pytest
from src.clippertv.email.service import EmailService

def test_email_template_generation():
    """Test HTML email template generation."""
    service = EmailService(api_key="test-key", from_address="test@example.com")

    html = service._build_email_template(
        rider_name="Test Rider",
        summary_html="<p>Summary content</p>",
        chart_urls=["https://example.com/chart1.png"],
        dashboard_url="https://app.clippertv.com/dashboard"
    )

    assert "Test Rider" in html
    assert "Summary content" in html
    assert "chart1.png" in html
    assert "View Full Dashboard" in html
```

**Manual Testing:**

Create test script: `scripts/test_email.py`

```python
"""Send test email report."""

from src.clippertv.email.service import EmailService
from src.clippertv.config import Config

email_service = EmailService(
    api_key=Config.EMAIL_API_KEY,
    from_address=Config.EMAIL_FROM
)

success = email_service.send_monthly_report(
    to_email="your-email@example.com",
    rider_name="Test Rider",
    summary_html="<p><strong>Test Rider</strong> took <strong>42</strong> trips this month.</p>",
    chart_urls=[],
    dashboard_url="http://localhost:8501"
)

print(f"Email sent: {success}")
```

Run: `uv run python scripts/test_email.py`

### Phase 1.5 Checklist

- [ ] Extract summary generation into `SummaryGenerator` class
- [ ] Update `dashboard.py` to use new `SummaryGenerator`
- [ ] Implement `EmailService` with Resend integration
- [ ] Implement `ChartExporter` for Plotly images
- [ ] Set up cloud storage for chart images (S3 or Cloudinary)
- [ ] Update scheduler to send emails after ingestion
- [ ] Create email template with branding
- [ ] Add deep links to dashboard
- [ ] Test email delivery to multiple providers (Gmail, Outlook, Apple Mail)
- [ ] Add configuration for email service
- [ ] Write unit tests for summary generation
- [ ] Write integration test for email sending
- [ ] Send test emails to verify formatting

### Success Criteria

- ✅ Summary text can be generated in HTML, Markdown, and Plain formats
- ✅ Existing Streamlit dashboard still works (uses Markdown format)
- ✅ Email template renders correctly across email clients
- ✅ Charts are exported as static images
- ✅ Charts are accessible via URLs in emails
- ✅ Emails are sent automatically after each monthly ingestion
- ✅ Each user receives a personalized report for their Clipper cards
- ✅ Deep links navigate to correct dashboard pages
- ✅ Test emails delivered successfully

---

## Phase 2: Reflex Migration + User-Facing Features

**Duration:** 3-4 weeks
**Goal:** Migrate from Streamlit to Reflex with full auth UI and onboarding

### Phase 2.1: Reflex Setup & Core Layout (Week 1)

**Install Reflex:**

```bash
uv add reflex
```

**Create Reflex App Structure:**

```
src/clippertv/
├── reflex_app/
│   ├── __init__.py
│   ├── app.py              # Main Reflex app entry point
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── login.py        # Login page
│   │   ├── signup.py       # Registration page
│   │   ├── onboarding.py   # Clipper card setup wizard
│   │   ├── dashboard.py    # Main dashboard
│   │   ├── import_pdf.py   # PDF upload
│   │   ├── add_manual.py   # Manual entry
│   │   └── stats.py        # Stats views
│   ├── components/
│   │   ├── __init__.py
│   │   ├── navbar.py       # Top navigation
│   │   ├── sidebar.py      # Side navigation
│   │   ├── chart.py        # Chart wrapper component
│   │   ├── summary.py      # Summary text component
│   │   └── table.py        # Data table component
│   ├── state/
│   │   ├── __init__.py
│   │   ├── auth.py         # Auth state management
│   │   ├── dashboard.py    # Dashboard state
│   │   └── upload.py       # Upload state
│   └── styles/
│       ├── __init__.py
│       └── theme.py        # Custom theme and colors
```

**Reflex State Management Pattern:**

```python
# src/clippertv/reflex_app/state/auth.py

import reflex as rx
from typing import Optional
from ...data.models import User, UserLogin, UserCreate
from ...data.user_store import UserStore
from ...auth.service import AuthService

class AuthState(rx.State):
    """Authentication state."""

    user: Optional[User] = None
    token: Optional[str] = None
    is_authenticated: bool = False
    error_message: str = ""

    def login(self, form_data: dict):
        """Handle user login."""
        try:
            # Validate credentials
            user_store = get_user_store()  # From factory
            user = user_store.verify_user_credentials(
                email=form_data["email"],
                password=form_data["password"]
            )

            if not user:
                self.error_message = "Invalid email or password"
                return

            # Generate token
            auth_service = get_auth_service()  # From factory
            token = auth_service.create_access_token(user.id, user.email)

            # Update state
            self.user = user
            self.token = token.access_token
            self.is_authenticated = True
            self.error_message = ""

            # Redirect to dashboard
            return rx.redirect("/dashboard")

        except Exception as e:
            self.error_message = f"Login failed: {str(e)}"

    def logout(self):
        """Handle user logout."""
        self.user = None
        self.token = None
        self.is_authenticated = False
        return rx.redirect("/login")

    def signup(self, form_data: dict):
        """Handle user registration."""
        try:
            user_store = get_user_store()

            # Create user
            user_data = UserCreate(
                email=form_data["email"],
                password=form_data["password"],
                name=form_data.get("name")
            )
            user = user_store.create_user(user_data)

            # Auto-login after registration
            return self.login({
                "email": form_data["email"],
                "password": form_data["password"]
            })

        except Exception as e:
            self.error_message = f"Registration failed: {str(e)}"
```

**Login Page:**

```python
# src/clippertv/reflex_app/pages/login.py

import reflex as rx
from ..state.auth import AuthState

def login_page() -> rx.Component:
    """Login page component."""
    return rx.center(
        rx.card(
            rx.vstack(
                rx.heading("Welcome to ClipperTV", size="2xl"),
                rx.text("Track your transit usage with ease", color="gray"),

                rx.form(
                    rx.vstack(
                        rx.input(
                            name="email",
                            placeholder="Email",
                            type="email",
                            required=True,
                        ),
                        rx.input(
                            name="password",
                            placeholder="Password",
                            type="password",
                            required=True,
                        ),
                        rx.button(
                            "Sign In",
                            type="submit",
                            width="100%",
                        ),
                        spacing="4",
                    ),
                    on_submit=AuthState.login,
                ),

                rx.cond(
                    AuthState.error_message != "",
                    rx.text(AuthState.error_message, color="red"),
                ),

                rx.divider(),

                rx.hstack(
                    rx.text("Don't have an account?"),
                    rx.link("Sign up", href="/signup"),
                ),

                spacing="6",
                width="400px",
            ),
            padding="8",
        ),
        height="100vh",
    )
```

**Dashboard Page (Reflex version):**

```python
# src/clippertv/reflex_app/pages/dashboard.py

import reflex as rx
from ..state.auth import AuthState
from ..state.dashboard import DashboardState
from ..components.navbar import navbar
from ..components.summary import summary_component
from ..components.chart import chart_component

@rx.page(route="/dashboard", on_load=DashboardState.load_data)
def dashboard_page() -> rx.Component:
    """Main dashboard page."""
    return rx.box(
        navbar(),
        rx.container(
            rx.vstack(
                rx.heading(f"Welcome, {AuthState.user.name}!", size="xl"),

                # Rider selector
                rx.radio(
                    ["K", "B"],
                    default_value="K",
                    on_change=DashboardState.set_selected_rider,
                ),

                # Summary section
                summary_component(),

                # Tabs
                rx.tabs(
                    items=[
                        {"label": "Import from PDF", "content": import_tab()},
                        {"label": "Add Manually", "content": manual_tab()},
                        {"label": "Annual Stats", "content": annual_stats_tab()},
                        {"label": "Monthly Stats", "content": monthly_stats_tab()},
                    ],
                ),

                spacing="6",
            ),
            max_width="1200px",
            padding="8",
        ),
    )

def import_tab() -> rx.Component:
    """PDF import tab."""
    # TODO: Implement file upload
    pass

# ... other tab implementations
```

### Phase 2.2: Onboarding Flow (Week 2)

**Onboarding Wizard:**

```python
# src/clippertv/reflex_app/pages/onboarding.py

import reflex as rx
from ..state.onboarding import OnboardingState

def onboarding_page() -> rx.Component:
    """Multi-step onboarding wizard."""
    return rx.center(
        rx.card(
            rx.vstack(
                # Progress indicator
                rx.hstack(
                    rx.badge("1", variant=rx.cond(OnboardingState.step >= 1, "solid", "outline")),
                    rx.text("→"),
                    rx.badge("2", variant=rx.cond(OnboardingState.step >= 2, "solid", "outline")),
                    rx.text("→"),
                    rx.badge("3", variant=rx.cond(OnboardingState.step >= 3, "solid", "outline")),
                    spacing="2",
                ),

                # Step content
                rx.cond(
                    OnboardingState.step == 1,
                    welcome_step(),
                    rx.cond(
                        OnboardingState.step == 2,
                        clipper_card_step(),
                        automation_step(),
                    ),
                ),

                spacing="6",
                width="600px",
            ),
            padding="8",
        ),
        height="100vh",
    )

def welcome_step() -> rx.Component:
    """Step 1: Welcome message."""
    return rx.vstack(
        rx.heading("Welcome to ClipperTV!", size="xl"),
        rx.text("Let's get your account set up in 3 simple steps."),
        rx.button("Get Started", on_click=OnboardingState.next_step),
        spacing="4",
    )

def clipper_card_step() -> rx.Component:
    """Step 2: Add Clipper card information."""
    return rx.vstack(
        rx.heading("Add Your Clipper Card", size="lg"),
        rx.text("Enter your Clipper card number to start tracking your rides."),

        rx.form(
            rx.vstack(
                rx.input(
                    name="card_number",
                    placeholder="Card Number (last 9 digits)",
                    type="text",
                    required=True,
                ),
                rx.input(
                    name="rider_name",
                    placeholder="Nickname (e.g., Work Card, Personal)",
                    type="text",
                    required=True,
                ),
                rx.checkbox(
                    "Set as primary card",
                    name="is_primary",
                ),
                rx.hstack(
                    rx.button("Back", on_click=OnboardingState.prev_step, variant="outline"),
                    rx.button("Next", type="submit"),
                    spacing="2",
                ),
                spacing="4",
            ),
            on_submit=OnboardingState.add_clipper_card,
        ),
        spacing="4",
    )

def automation_step() -> rx.Component:
    """Step 3: Optional automation setup."""
    return rx.vstack(
        rx.heading("Automatic Data Import (Optional)", size="lg"),
        rx.text("Save your Clipper account credentials to automatically download your monthly statements."),

        rx.form(
            rx.vstack(
                rx.input(
                    name="clipper_username",
                    placeholder="Clipper Website Username",
                    type="text",
                ),
                rx.input(
                    name="clipper_password",
                    placeholder="Clipper Website Password",
                    type="password",
                ),
                rx.text(
                    "Your credentials are encrypted and never shared.",
                    size="sm",
                    color="gray",
                ),
                rx.hstack(
                    rx.button("Back", on_click=OnboardingState.prev_step, variant="outline"),
                    rx.button("Skip", on_click=OnboardingState.skip_automation, variant="ghost"),
                    rx.button("Finish", type="submit"),
                    spacing="2",
                ),
                spacing="4",
            ),
            on_submit=OnboardingState.finish_onboarding,
        ),
        spacing="4",
    )
```

### Phase 2.3: Component Migration (Week 3)

**Chart Component:**

```python
# src/clippertv/reflex_app/components/chart.py

import reflex as rx
import plotly.graph_objects as go

def chart_component(fig: go.Figure, title: str) -> rx.Component:
    """Plotly chart component."""
    return rx.box(
        rx.heading(title, size="md", margin_bottom="4"),
        rx.plotly(data=fig),
        padding="4",
        border="1px solid #e2e8f0",
        border_radius="8px",
    )
```

**Summary Component (using refactored SummaryGenerator):**

```python
# src/clippertv/reflex_app/components/summary.py

import reflex as rx
from ...viz.summary import SummaryGenerator

def summary_component() -> rx.Component:
    """Display summary statistics."""
    # For Reflex, we'll need to convert HTML to Reflex components
    # Or use rx.html() to render HTML directly

    return rx.box(
        rx.html(DashboardState.summary_html),
        padding="6",
        background="gray.50",
        border_radius="8px",
    )
```

### Phase 2.4: Testing & Deployment (Week 4)

**Update Dependencies:**

```toml
[project]
dependencies = [
    # Remove Streamlit
    # "streamlit>=1.28.0",  # REMOVE

    # Add Reflex
    "reflex>=0.4.0",

    # Keep all other dependencies
]
```

**Update Run Scripts:**

```python
# run_app.py (update for Reflex)

import reflex as rx
from src.clippertv.reflex_app.app import app

if __name__ == "__main__":
    rx.run(app)
```

**Testing Checklist:**

- [ ] All pages render correctly
- [ ] Login/signup flow works end-to-end
- [ ] Onboarding wizard completes successfully
- [ ] Clipper card credentials are encrypted
- [ ] Dashboard loads user-specific data
- [ ] PDF upload and processing works
- [ ] Manual entry form works
- [ ] Charts render correctly
- [ ] Summary text displays properly
- [ ] Logout clears session
- [ ] Deep links from email work
- [ ] Mobile responsive design

**Deployment:**

Update email template deep links to point to new Reflex app URL.

**File:** `src/clippertv/email/service.py`

```python
# Update dashboard_url generation
def get_dashboard_url(user_id: str, page: str = "dashboard") -> str:
    """Generate deep link to Reflex dashboard."""
    base_url = os.getenv("APP_URL", "https://clippertv.app")
    return f"{base_url}/{page}?token={generate_magic_link_token(user_id)}"
```

### Phase 2 Checklist

- [ ] Install Reflex and set up project structure
- [ ] Implement AuthState for state management
- [ ] Create login and signup pages
- [ ] Create onboarding wizard (3 steps)
- [ ] Migrate dashboard layout to Reflex
- [ ] Create reusable components (navbar, charts, tables)
- [ ] Implement PDF upload in Reflex
- [ ] Implement manual entry form in Reflex
- [ ] Migrate all statistics tabs
- [ ] Add mobile-responsive styling
- [ ] Update email template deep links
- [ ] Test full user journey (signup → onboard → use app)
- [ ] Write E2E tests with Playwright or Selenium
- [ ] Deploy Reflex app to production
- [ ] Deprecate Streamlit app

### Success Criteria

- ✅ New users can sign up and create accounts
- ✅ Users can add Clipper cards during onboarding
- ✅ Users can optionally save credentials for automation
- ✅ Login/logout works correctly with JWT tokens
- ✅ Dashboard shows only user's own data
- ✅ All Streamlit features have been migrated
- ✅ Email deep links navigate to correct Reflex pages
- ✅ App is responsive on mobile devices
- ✅ Performance is acceptable (page load < 2s)
- ✅ No Streamlit dependencies remain

---

## Post-Migration: Continuous Improvements

### Quick Wins

- [ ] Add password reset flow
- [ ] Add profile settings page
- [ ] Allow users to add multiple Clipper cards
- [ ] Add dark mode toggle
- [ ] Improve chart interactivity

### Future Features

- [ ] Data export (CSV, JSON)
- [ ] Custom date range filtering
- [ ] Budget tracking and alerts
- [ ] Comparison with other users (opt-in)
- [ ] Mobile app (React Native using same backend)
- [ ] Transit route recommendations based on usage patterns

---

## Risk Mitigation

### Major Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Reflex learning curve | High | Prototype login page first to validate feasibility |
| Data migration complexity | Medium | Phase 1 keeps existing data model intact |
| Email deliverability | Medium | Test with multiple providers; use reputable ESP (Resend) |
| User adoption of multi-user | Low | Grandfather existing users with simple migration path |
| Credential encryption security | High | Use industry-standard Fernet; store keys in secure vault |

### Rollback Plan

- Keep Streamlit app running in parallel during Phase 2
- Use feature flags to toggle between old/new UI
- Maintain database backward compatibility
- If Reflex migration fails, can continue with Streamlit + auth backend

---

## Timeline Summary

| Week | Phase | Deliverable |
|------|-------|-------------|
| 1-2 | Phase 1 | Multi-user backend (auth, DB schema, user management) |
| 3 | Phase 1.5 | Email reports (text refactor, email service, scheduler) |
| 4 | Phase 2.1 | Reflex setup (login, signup, basic layout) |
| 5 | Phase 2.2 | Onboarding wizard |
| 6 | Phase 2.3 | Component migration (dashboard, charts, forms) |
| 7 | Phase 2.4 | Testing, deployment, deprecate Streamlit |

**Total: 7 weeks (estimated 40-60 dev hours)**

---

## Dependencies & Configuration

### Required Environment Variables

```bash
# Database
TURSO_DATABASE_URL=libsql://your-db.turso.io
TURSO_AUTH_TOKEN=your-turso-token

# Authentication
JWT_SECRET_KEY=your-secret-key-32-chars-min
ENCRYPTION_KEY=your-fernet-key

# Email
EMAIL_PROVIDER=resend
EMAIL_API_KEY=re_your_resend_key
EMAIL_FROM=ClipperTV <reports@clippertv.app>

# App
APP_URL=https://clippertv.app
```

### Generate Secrets

```bash
# JWT secret (32+ characters)
openssl rand -hex 32

# Fernet encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Notes

- This plan prioritizes **shipping incremental value** over big-bang rewrites
- Each phase has **clear success criteria** and can be validated independently
- **No throwaway work**: Email reports built in Phase 1.5 work with both Streamlit and Reflex
- **Backend-first approach** de-risks the hardest parts (auth, encryption, multi-tenancy)
- **Phase 1.5 is the quick win** that delivers user value while working on the bigger migration

**Last Updated:** 2025-10-27
