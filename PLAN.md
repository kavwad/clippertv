# ClipperTV Migration Plan

**Status:** Phase 1 Complete ✅
**Next:** Phase 1.5 or Phase 2

---

## Phase 1: Multi-User Backend ✅ COMPLETE

**What's Done:**
- User accounts with JWT auth (bcrypt password hashing)
- Clipper card management with Fernet-encrypted credentials
- Database schema: `users`, `clipper_cards` tables + `user_id` columns
- UserStore: CRUD operations, credential verification
- TursoStore: Updated with optional `user_id` filtering
- Config: EnvConfig with validation
- Tests: 13/13 auth, 13/14 user store passing
- Migration: Idempotent script at `migrations/run_migration.py`

**Key Files:**
- `src/clippertv/auth/service.py` - AuthService (JWT)
- `src/clippertv/auth/crypto.py` - CredentialEncryption
- `src/clippertv/data/user_store.py` - UserStore
- `src/clippertv/data/models.py` - User, ClipperCard, AuthToken models
- `src/clippertv/config.py` - EnvConfig class
- `tests/test_auth.py`, `tests/test_user_store.py`

**Env Setup:**
- `.env` created with JWT_SECRET_KEY and ENCRYPTION_KEY
- `.streamlit/secrets.toml` updated
- Validation script: `scripts/test_env.py`

---

## Phase 1.5: Monthly Email Reports (1 week)

**Goal:** Automated email recaps after PDF ingestion

**Tasks:**
1. Extract `SummaryGenerator` from dashboard (HTML/Markdown/Plain formats)
2. Create `EmailService` with Resend integration
3. Add `ChartExporter` for Plotly → PNG conversion
4. Update scheduler to send reports after ingestion
5. Store chart images (S3 or inline base64)

**Key Files to Create:**
- `src/clippertv/viz/summary.py` - SummaryGenerator class
- `src/clippertv/email/service.py` - EmailService
- `src/clippertv/viz/export.py` - ChartExporter
- `src/clippertv/scheduler/run_ingestion.py` - Add send_monthly_reports()

**Dependencies:** `resend`, `kaleido`

---

## Phase 2: Reflex Migration (3-4 weeks)

**Goal:** Replace Streamlit with Reflex + full auth UI

**Phase 2.1: Core Setup**
- Reflex app structure in `src/clippertv/reflex_app/`
- AuthState for session management
- Login/signup pages

**Phase 2.2: Onboarding**
- 3-step wizard: Welcome → Add Clipper Card → Optional Automation

**Phase 2.3: Dashboard Migration**
- Migrate charts, summary, stats tabs
- PDF upload component
- Manual entry form

**Phase 2.4: Cleanup**
- Remove Streamlit dependencies
- Update email deep links
- E2E tests

**Key Files to Create:**
- `src/clippertv/reflex_app/app.py`
- `src/clippertv/reflex_app/state/auth.py`
- `src/clippertv/reflex_app/pages/` - login, signup, dashboard, onboarding
- `src/clippertv/reflex_app/components/` - reusable UI components

---

## Quick Reference

**Run tests:**
```bash
uv run pytest tests/test_auth.py -v
uv run pytest tests/test_user_store.py -v
```

**Validate env:**
```bash
uv run python scripts/test_env.py
```

**Run migration:**
```bash
uv run python migrations/run_migration.py
```

**Usage example:**
```python
from clippertv.auth.service import AuthService
from clippertv.data.user_store import UserStore
from clippertv.data.turso_client import get_turso_client
from clippertv.config import env_config

client = get_turso_client()
auth = AuthService(secret_key=env_config.JWT_SECRET_KEY)
crypto = CredentialEncryption(encryption_key=env_config.ENCRYPTION_KEY)
user_store = UserStore(client, auth, crypto)
```
