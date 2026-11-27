from fastapi import FastAPI

from caged_api.routes import router

app = FastAPI(title="CAGED API", version="0.1.0")
app.include_router(router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
