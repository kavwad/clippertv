# Automated Monthly Ingestion

Auto-download and ingest Clipper PDFs monthly on your Raspberry Pi using systemd timer.

## Setup on Raspberry Pi

1. **Clone repo and install dependencies:**
   ```bash
   cd ~
   git clone https://github.com/kavwad/clippertv.git
   cd clippertv

   # Install uv if needed
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source ~/.local/bin/env

   # Install dependencies (core only, no Streamlit)
   uv sync
   ```

2. **Copy .env file** from your development machine with database credentials

3. **Users already set up in database** (Bree and Kaveh with encrypted Clipper credentials)

4. **Install systemd timer:**
   ```bash
   # Update paths in service file if needed (should be /home/kavwad/clippertv)
   sudo cp scheduler/clippertv-ingestion.{service,timer} /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now clippertv-ingestion.timer
   ```

5. **Verify:**
   ```bash
   systemctl list-timers clippertv-ingestion.timer
   ```

## Usage

```bash
# View next run time
systemctl list-timers clippertv-ingestion.timer

# Manual trigger
sudo systemctl start clippertv-ingestion.service

# View logs
sudo journalctl -u clippertv-ingestion -f
```

## Scheduled Run

- Runs on the **2nd of each month at 2:00 AM**
- Downloads last month's PDFs for all users
- Deduplicates and archives to `pdfs/` directory
- Ingests transactions to Turso database

## Optional: Healthchecks.io Monitoring

1. Sign up at https://healthchecks.io
2. Create check: 31-day period, 2-hour grace
3. Edit service file and uncomment HEALTHCHECK_URL line with your ping URL
4. Reload: `sudo systemctl daemon-reload && sudo systemctl restart clippertv-ingestion.timer`
