from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.core.config import get_settings
from src.core.database import get_db
from src.core.logging import logger

router = APIRouter()
settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    database: str


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service and Database Health Check",
)
def check_health(db: Session = Depends(get_db)):
    """Verifies service responsiveness and validates active database connectivity via a ping query."""
    try:
        # Execute basic ping query to test connection from the pool
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        logger.error(f"Health check database ping failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "app_name": settings.APP_NAME,
                "environment": settings.APP_ENV,
                "database": "unreachable",
                "error": str(exc),
            },
        )

    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        database=db_status,
    )
