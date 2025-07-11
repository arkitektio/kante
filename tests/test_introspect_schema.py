import pytest
from test_project.asgi import application
from kante.testing.http import HttpGetTestClient  # Replace `your_module` with the actual import path

@pytest.mark.asyncio
async def test_schema_endpoint_returns_sdl() -> None:
    """Test that the /schema endpoint returns SDL text with 'type Query'."""
    client = HttpGetTestClient(application)
    body = await client.get("/schema")

    assert "type Query" in body
