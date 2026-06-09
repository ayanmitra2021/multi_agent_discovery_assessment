import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        llm_provider="claude",
        anthropic_api_key="test-key",
    )


@pytest.fixture
async def client(test_settings: Settings):
    app = create_app(settings=test_settings)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
