"""
FastAPI application entrypoint.

Run with:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

(run from the project root, so the `backend` package resolves correctly)
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings, BASE_DIR
from backend.database.database import init_db
from backend.api import documents, presentations, quality

app = FastAPI(
    title="AI Presentation Generator",
    description="Generates professional PowerPoint presentations from a topic, "
                "optional source documents, and user-selected settings, using a "
                "hierarchical Gemini prompting pipeline with RAG.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak internals (stack traces, API keys, etc.) to the client.
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred. Please try again."},
    )


app.include_router(documents.router)
app.include_router(presentations.router)
app.include_router(quality.router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "gemini_model": settings.GEMINI_MODEL,
    }


# Serve the static frontend directly from FastAPI so the whole app can run
# from a single `uvicorn` process during development.
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
