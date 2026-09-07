from fastapi import FastAPI

from app.api.v1.candidates import router as candidates_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.investigations import router as investigations_router
from app.api.v1.repositories import router as repositories_router

app = FastAPI(
    title="CodeArchaeologist",
    description="AI-powered software archaeology and safe code deletion intelligence",
    version="0.1.0",
)


app.include_router(
    repositories_router,
    prefix="/api/v1",
)

app.include_router(
    candidates_router,
    prefix="/api/v1",
)

app.include_router(
    investigations_router,
    prefix="/api/v1",
)

app.include_router(
    evidence_router,
    prefix="/api/v1",
)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "CodeArchaeologist",
    }
