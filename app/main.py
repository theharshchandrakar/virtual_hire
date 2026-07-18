"""FastAPI entrypoint. Run with: uvicorn app.main:app --reload

Routers get registered here as they're implemented under app/api/routes/.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.hr_users import router as hr_users_router
from app.core.config import get_settings
from app.api.routes.organizations import router as organizations_router
from app.api.routes.requisitions import router as requisitions_router
from app.api.routes.resumes import router as resumes_router
from app.api.routes.transcripts import router as transcripts_router
from app.api.routes.verdicts import router as verdicts_router

settings = get_settings()

app = FastAPI(title="Sift API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(organizations_router)
app.include_router(hr_users_router)
app.include_router(requisitions_router)
app.include_router(resumes_router)
app.include_router(transcripts_router)
app.include_router(verdicts_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
