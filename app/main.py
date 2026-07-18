"""FastAPI entrypoint. Run with: uvicorn app.main:app --reload

Routers get registered here as they're implemented under app/api/routes/.
"""

from fastapi import FastAPI

from app.api.routes.hr_users import router as hr_users_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.requisitions import router as requisitions_router

app = FastAPI(title="Sift API", version="0.1.0")

app.include_router(organizations_router)
app.include_router(hr_users_router)
app.include_router(requisitions_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
