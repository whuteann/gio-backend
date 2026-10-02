from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — every model must be imported before SQLAlchemy
# configures its mappers, or a relationship() referencing a model with no
# endpoint yet (nothing else to transitively import it) fails at first use.
# Every endpoint module happens to import exactly the models it needs
# directly, which is what covered this so far — until a model with no
# endpoint of its own (Narrative) exposed the gap. See
# docs/behaviour_log_0005.md.
from app.api.v1.router import api_router
from app.config import settings
from app.dependencies import get_db

app = FastAPI(title="Auren Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check(response: Response, db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "database": "unreachable"}
