from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import Settings
from .api.errors import register_exception_handlers
from .api.routes_assess import router as assess_router
from .api.routes_health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 3: initialise DB connections here
    # Phase 5: start MCP server subprocess here
    yield
    # shutdown: close DB / MCP client here


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="Cloud Migration Assessment API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    app.include_router(health_router)
    app.include_router(assess_router, prefix="/api")
    register_exception_handlers(app)

    app.state.settings = settings
    return app


app = create_app()
