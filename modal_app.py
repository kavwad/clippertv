"""Modal deployment entrypoint for ClipperTV.

The only Modal-specific module in the repo. Everything it needs lives in the
portable ``clippertv`` package; this file just wires two workloads onto Modal:

- ``web``   — the FastAPI dashboard as a scale-to-zero ASGI app.
- ``ingest`` — the weekly Clipper ingestion as a native scheduled function
              (replaces the old launchd plist + shell wrapper + Railway cron).

Deploy:   uv run modal deploy -m modal_app
Spike:    uv run modal run modal_app.py::ingest    # one-off ingest, no schedule
Secrets:  a Modal secret named "clippertv" supplies TURSO_DATABASE_URL,
          TURSO_AUTH_TOKEN, JWT_SECRET_KEY, ENCRYPTION_KEY (+ optional APP_URL,
          HEALTHCHECK_URL). See the plan / README for the create command.
"""

import os

import modal

app = modal.App("clippertv")

# uv_sync installs the dependencies from pyproject.toml + uv.lock, but not the
# local clippertv project itself. We mount the src/ tree and put it on
# PYTHONPATH: this makes `import clippertv` work and carries the non-Python web
# assets (templates/static) inline, so Path(__file__).parent resolves correctly.
# (.env must precede the local-dir mount — copy=False mounts are applied last.)
image = (
    modal.Image.debian_slim(python_version="3.13")
    .uv_sync()
    .env({"PYTHONPATH": "/root/src"})
    .add_local_dir("src", "/root/src")
)

clippertv_secret = modal.Secret.from_name("clippertv")


@app.function(
    image=image,
    secrets=[clippertv_secret],
    # Scale to zero when idle; one container fields many concurrent requests.
    scaledown_window=300,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def web():
    # Imported inside the container, not at deploy time.
    from clippertv.web.main import app as fastapi_app

    return fastapi_app


@app.function(
    image=image,
    secrets=[clippertv_secret],
    # Matches the old launchd schedule: Mondays at 08:00 Pacific.
    # NOTE: when a staging environment is added later, gate this schedule so a
    # staging deploy does not double-ingest into the shared Turso DB.
    schedule=modal.Cron("0 8 * * 1", timezone="America/Los_Angeles"),
    timeout=600,
)
def ingest():
    from clippertv.scheduler.service import run_ingestion

    healthcheck = os.environ.get("HEALTHCHECK_URL")
    try:
        results = run_ingestion(days=30, output_dir="/tmp/downloads")
    except Exception:
        _ping(healthcheck, "/fail")
        raise

    total_new = sum(r.new_rows for r in results)
    failures = [r for r in results if r.error]
    print(
        f"ingest complete: {len(results)} account(s), "
        f"{total_new} new row(s), {len(failures)} failure(s)"
    )
    for r in failures:
        print(f"  FAILED {r.account}: {r.error}")

    # Match the old wrapper: ping success, or /fail if any account errored.
    _ping(healthcheck, "" if not failures else "/fail")

    return {
        "accounts": len(results),
        "new_rows": total_new,
        "failures": len(failures),
    }


def _ping(base_url: str | None, suffix: str) -> None:
    """Best-effort healthchecks.io ping; never raises."""
    if not base_url:
        return
    import contextlib

    import requests

    with contextlib.suppress(Exception):
        requests.get(f"{base_url}{suffix}", timeout=10)
