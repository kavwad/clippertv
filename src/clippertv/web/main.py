"""FastAPI application entry point for ClipperTV."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from clippertv.web.routes import router

app = FastAPI(title="ClipperTV", description="Transit trip dashboard")

# Static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Include routes
app.include_router(router)


def run():
    """Run the FastAPI app with uvicorn."""
    import uvicorn
    uvicorn.run("clippertv.web.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
