"""FastAPI application entry point for ClipperTV."""

import os
from pathlib import Path

from fastapi import FastAPI

# Load .env file if it exists
env_file = Path(__file__).parent.parent.parent.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

from clippertv.web.routes import router

app = FastAPI(title="ClipperTV", description="Transit trip dashboard")

# Include routes
app.include_router(router)


def run():
    """Run the FastAPI app with uvicorn."""
    import uvicorn
    uvicorn.run("clippertv.web.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
