# Auth sprint: deferred work

## Features
- [ ] Seed transaction history on first login (CSV data is already downloaded, just needs ingest call)
- [ ] Scrape Clipper dashboard HTML for card names and user profile on login

## Cleanup
- [ ] Drop vestigial columns from clipper_cards (credentials_encrypted, card_serial, is_primary)
- [ ] Migrate `clipper-download` CLI to read credentials from users table instead of clipper.toml
- [ ] Remove or simplify 003_seed_users.py (legacy onboarding path, replaced by web login)

## UX (needs smoke-testing)
- [ ] Card rename: confirm blur/enter behavior works, consider save indicator
- [ ] Refresh-cards failure: returns plain text into #card-list, may need styled error partial
