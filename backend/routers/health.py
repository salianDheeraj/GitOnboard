from fastapi import APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import Depends
from backend.database import get_db

router = APIRouter(tags=["health"])

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint for Docker and Azure readiness probes.
    Also verifies database connectivity.
    """
    try:
        # Simple query to verify DB connection
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}
