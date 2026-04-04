"""FastAPI application entry point for ClipperTV."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.middleware.authentication import AuthenticationMiddleware  # noqa: E402

from clippertv.web.auth import CookieAuthBackend, auth_exception_handlers  # noqa: E402
from clippertv.web.auth_routes import router as auth_router  # noqa: E402
from clippertv.web.routes import router  # noqa: E402
from clippertv.web.settings_routes import router as settings_router  # noqa: E402

app = FastAPI(title="ClipperTV", description="Transit trip dashboard")

# Authentication middleware — populates request.user on every request
app.add_middleware(AuthenticationMiddleware, backend=CookieAuthBackend())

# Exception handlers for auth redirects
for exc_class, handler in auth_exception_handlers().items():
    app.add_exception_handler(exc_class, handler)

# Static files
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)

# Routes — auth first, then settings, then dashboard
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(router)


def run():
    """Run the FastAPI app with uvicorn."""
    import uvicorn

    uvicorn.run("clippertv.web.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
