# Automated Monthly Ingestion

Auto-download and ingest Clipper PDFs monthly on your Raspberry Pi.

## Quick Start

1. **Choose scheduling approach:**
   - **APScheduler** (simpler): Always-running Python scheduler
   - **systemd Timer** (efficient): Native Linux timer, runs only when needed

2. **Install dependencies:**
   ```bash
   cd ~/schedule-ingestion
   uv sync && uv add apscheduler
   ```

3. **Configure secrets** in `.streamlit/secrets.toml`

4. **Install service** (see below for your chosen approach)

5. **(Optional)** Set up Healthchecks.io for failure notifications

---

## APScheduler Setup (Simpler)

**Best for:** Simple setup, Python familiarity

### Install

```bash
# Edit paths if needed
nano clippertv-scheduler.service

# Install
sudo cp clippertv-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now clippertv-scheduler

# Verify
sudo systemctl status clippertv-scheduler
```

### Usage

```bash
# View status
sudo systemctl status clippertv-scheduler

# View logs
sudo journalctl -u clippertv-scheduler -f
tail -f logs/scheduler.log

# Manual trigger
uv run python -m clippertv.pdf.downloader --all --last-month --ingest
```

---

## systemd Timer Setup (More Efficient)

**Best for:** Maximum efficiency, native Linux integration

### Install

```bash
# Edit paths if needed
nano clippertv-ingestion.service

# Install
sudo cp clippertv-ingestion.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now clippertv-ingestion.timer

# Verify
systemctl list-timers clippertv-ingestion.timer
```

### Usage

```bash
# View next run time
systemctl list-timers clippertv-ingestion.timer

# View status
sudo systemctl status clippertv-ingestion.timer

# Manual trigger
sudo systemctl start clippertv-ingestion.service

# View logs
sudo journalctl -u clippertv-ingestion -f
```

---

## Healthchecks.io Monitoring (Optional)

Get notified when ingestion fails.

1. Sign up at https://healthchecks.io (free)
2. Create check: 31-day period, 2-hour grace
3. Copy ping URL
4. Edit service file:
   ```bash
   sudo nano /etc/systemd/system/clippertv-scheduler.service  # or clippertv-ingestion.service
   ```
5. Uncomment and set:
   ```ini
   Environment="HEALTHCHECK_URL=https://hc-ping.com/your-uuid-here"
   ```
6. Reload:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart clippertv-scheduler  # or clippertv-ingestion.timer
   ```

---

## File Structure

```
clippertv/
├── src/clippertv/scheduler/
│   ├── service.py                      # APScheduler entry point (python -m clippertv.scheduler.service)
│   ├── run_ingestion.py                # systemd timer entry point (python -m clippertv.scheduler.run_ingestion)
│   └── __init__.py                     # Package exports
├── scheduler/                          # Deployment artifacts (this folder)
│   ├── clippertv-scheduler.service     # APScheduler systemd unit
│   ├── clippertv-ingestion.service     # Timer service unit
│   ├── clippertv-ingestion.timer       # Timer config
│   └── SCHEDULER.md                    # This guide
├── pdf/                               # Archived PDFs (gitignored)
│   ├── clippertv-transactions-12345-2025-01.pdf
│   └── ...
└── logs/scheduler.log                  # Application logs (gitignored)
```

---

## Configuration

Edit `.streamlit/secrets.toml`:

```toml
[clipper.rider_accounts]
B = ["card_serial_1", "card_serial_2"]
K = ["card_serial_3"]

[clipper.users.B]
email = "user@example.com"
password = "password"

[clipper.users.K]
email = "user@example.com"
password = "password"
```

Secure it:
```bash
chmod 600 .streamlit/secrets.toml
```

---

## Troubleshooting

### Service won't start
```bash
sudo journalctl -u clippertv-scheduler -n 50  # Check errors
sudo systemctl status clippertv-scheduler     # View status
```

### No PDFs downloaded
```bash
tail -f logs/scheduler.log  # Check app logs
# Verify credentials in .streamlit/secrets.toml
```

### Timer not triggering
```bash
systemctl list-timers  # Check next run
sudo systemctl status clippertv-ingestion.timer
```

---

## Comparison

| Feature | APScheduler | systemd Timer |
|---------|-------------|---------------|
| Setup | ⭐ Easy | ⭐⭐ Medium |
| Resources | Higher (always running) | Lower (on-demand) |
| Files | 1 service | 2 files (service + timer) |

**Both support:**
- Healthchecks.io monitoring
- Auto-restart on failure
- PDF deduplication
- Comprehensive logging

---

## FAQ

**Q: Which should I use?**
A: APScheduler is simpler. systemd timer is more efficient. Both work great!

**Q: What if Pi is offline during scheduled time?**
A: APScheduler has 1-hour grace. Timer has `Persistent=true` to catch up.

**Q: How much disk space?**
A: ~50-200 KB per PDF. ~5-10 MB/year for 2 riders.

**Q: How do I know if it fails?**
A: Set up Healthchecks.io for automatic email/SMS/Slack alerts.

---

**Need help?** Check logs first: `sudo journalctl -u <service-name> -n 100`
