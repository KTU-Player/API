from contextlib import asynccontextmanager
from fastapi import FastAPI

from .routers import users, tracks, queue, search
from .services.storage_service import storage_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MinIO buckets on startup
    storage_service.init_buckets()
    yield
    # Clean up resources if needed on shutdown
    pass


app = FastAPI(
    title="Music Information System API",
    description="A production-ready backend for a Music Information System.",
    version="0.1.0",
    debug=True,
    lifespan=lifespan,
)

app.include_router(users.router)
app.include_router(tracks.router)
app.include_router(queue.router)
app.include_router(search.router)


@app.get("/", tags=["Health"])
async def read_root():
    """
    Root endpoint for health checks.
    """
    return {"status": "ok"}
