import app.models  # noqa: F401 — registers all ORM models on Base.metadata
from fastapi import FastAPI

from app.api.persons import router as persons_router
from app.api.roles import router as roles_router

app = FastAPI(title="Ketabdaneh API")

app.include_router(roles_router)
app.include_router(persons_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
