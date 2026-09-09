import app.models  # noqa: F401 — registers all ORM models on Base.metadata
from fastapi import FastAPI

app = FastAPI(title="Ketabdaneh API")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
