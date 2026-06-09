import io

import pytest
from httpx import AsyncClient

from tests.fixtures.documents import make_csv, make_docx


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] == "claude"
    assert "version" in body


@pytest.mark.asyncio
async def test_assess_returns_501_after_parsing(client: AsyncClient):
    """Valid document parses successfully; pipeline returns 501 until Phase 5."""
    csv_bytes = make_csv([["App", "Language"], ["BillingAPI", "Java"]])
    response = await client.post(
        "/api/assess",
        data={"csp": "aws"},
        files={"file": ("portfolio.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert response.status_code == 501


@pytest.mark.asyncio
async def test_assess_rejects_unsupported_file_type(client: AsyncClient):
    response = await client.post(
        "/api/assess",
        data={"csp": "aws"},
        files={"file": ("script.exe", io.BytesIO(b"MZ"), "application/x-msdownload")},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_assess_rejects_oversized_file(client: AsyncClient):
    # settings fixture sets max_upload_size_mb=25; create a 26 MB payload
    large = io.BytesIO(b"x" * (26 * 1024 * 1024))
    response = await client.post(
        "/api/assess",
        data={"csp": "aws"},
        files={"file": ("big.csv", large, "text/csv")},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_assess_rejects_invalid_csp(client: AsyncClient):
    csv_bytes = make_csv([["App"], ["Test"]])
    response = await client.post(
        "/api/assess",
        data={"csp": "alibaba"},
        files={"file": ("p.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert response.status_code == 422
