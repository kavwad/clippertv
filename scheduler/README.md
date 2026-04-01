# Scheduler: Weekly Clipper Ingestion

Platform-agnostic Python module (`clippertv.scheduler`) with a thin
platform-specific trigger layer.

## Architecture

```
launchd / systemd / cron
  └── scheduler/clippertv-ingest.sh   (logging wrapper, disposable)
        └── clippertv-ingest           (Python entry point)
              └── clippertv.scheduler.service.run_ingestion()
                    ├── clipper.login()
                    ├── clipper.download_transactions()
                    └── pipeline.ingest()
```

The Python module is the portable part. The shell wrapper and plist/timer
are platform glue — swap them when moving to a Pi or cloud.

## Usage

```bash
# Run directly
uv run clippertv-ingest --days 30 -v

# Dry run (validate logins)
uv run clippertv-ingest --dry-run

# Or as a module
uv run python -m clippertv.scheduler --days 30
```

## macOS Setup (launchd)

1. Edit the plist path:

   ```bash
   sed -i '' "s|/Users/YOU/clippertv|$(pwd)|" scheduler/com.clippertv.ingest.plist
   ```

2. Make the wrapper executable:

   ```bash
   chmod +x scheduler/clippertv-ingest.sh
   ```

3. Install and load:

   ```bash
   cp scheduler/com.clippertv.ingest.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.clippertv.ingest.plist
   ```

4. Verify: `launchctl list | grep clippertv`

5. Manual trigger: `launchctl start com.clippertv.ingest`

## Linux Setup (systemd)

Create a systemd timer pointing at the same script, or call
`clippertv-ingest` directly from cron:

```cron
0 9 * * 0  cd /path/to/clippertv && uv run clippertv-ingest --days 30 -v >> logs/cron.log 2>&1
```

## Uninstall (macOS)

```bash
launchctl unload ~/Library/LaunchAgents/com.clippertv.ingest.plist
rm ~/Library/LaunchAgents/com.clippertv.ingest.plist
```

## Logs

- Application logs: `logs/ingest-YYYYMMDD_HHMMSS.log` (auto-pruned after 90 days)
- launchd stdout/stderr: `/tmp/clippertv-ingest.{stdout,stderr}.log`
