from fastapi import FastAPI
from .routers import users, tracks

app = FastAPI(
    title="Music Information System API",
    description="A production-ready backend for a Music Information System.",
    version="0.1.0",
    debug=True,
)

app.include_router(users.router)
app.include_router(tracks.router)


@app.get("/", tags=["Health"])
async def read_root():
    """
    Root endpoint for health checks.
    """
    return {"status": "ok"}
