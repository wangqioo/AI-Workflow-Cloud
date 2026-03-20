"""AI Workflow Terminal v0.8 - Cloud-native FastAPI backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth.router import router as auth_router
from .config import settings
from .database import engine, Base
from .engines.router import router as engines_router
from .llm.provider import get_llm_provider
from .llm.router import router as llm_router
from .memory.router import router as memory_router
from .openclaw.router import router as openclaw_router
from .rag.router import router as rag_router
from .doc_version.router import router as doc_version_router
from .services.router import router as services_router
from .task_system.router import router as task_router
from .workflow.router import router as workflow_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables (dev only; production uses Alembic migrations)
    if settings.app_debug:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: close LLM HTTP client
    llm = get_llm_provider()
    await llm.close()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(llm_router)
app.include_router(engines_router)
app.include_router(memory_router)
app.include_router(openclaw_router)
app.include_router(rag_router)
app.include_router(workflow_router)
app.include_router(doc_version_router)
app.include_router(task_router)
app.include_router(services_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        "deploy_mode": settings.deploy_mode,
    }
