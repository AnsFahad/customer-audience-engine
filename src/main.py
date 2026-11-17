from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from src.core.config import get_settings
from src.core.logging import logger
from src.api.v1 import health, customers, events, segments, campaigns

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and shutdown lifecycle events."""
    logger.info(f"Starting {settings.APP_NAME} in [{settings.APP_ENV}] mode...")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


def create_application() -> FastAPI:
    """Application factory for Customer Audience Engine."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="Customer Data & Audience Segmentation Engine for Enterprise MarTech / CDP",
        lifespan=lifespan,
    )

    # Enable CORS for browser access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve Visual Dashboard at root URL
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def serve_dashboard():
        html_file = Path(__file__).parent / "static" / "index.html"
        if html_file.exists():
            return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
        return HTMLResponse(content="<h1>Customer Audience Engine</h1><p><a href='/docs'>Open Swagger API</a></p>")

    # Register API Routers
    app.include_router(
        health.router,
        prefix=settings.API_V1_STR,
        tags=["Health & Diagnostics"],
    )
    app.include_router(
        customers.router,
        prefix=settings.API_V1_STR,
        tags=["Customers"],
    )
    app.include_router(
        events.router,
        prefix=settings.API_V1_STR,
        tags=["Behavioral Events"],
    )
    app.include_router(
        segments.router,
        prefix=settings.API_V1_STR,
        tags=["Audience Segmentation"],
    )
    app.include_router(
        campaigns.router,
        prefix=settings.API_V1_STR,
        tags=["Campaign Management"],
    )

    return app


app = create_application()
