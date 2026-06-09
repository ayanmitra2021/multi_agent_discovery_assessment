from fastapi import APIRouter, Request
from ..schemas.api import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        version="0.1.0",
        llm_provider=settings.llm_provider.value,
    )
