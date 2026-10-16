"""Credential-free HA fixtures using the real SDK and an HTTP transport double."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import httpx
import pytest
from airbeld import AirbeldClient
from homeassistant.core import HomeAssistant

from custom_components.airbeld.coordinator import AirbeldDataUpdateCoordinator


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Enable the integration in HA's loader."""


@pytest.fixture
def payload():
    """Return a v1 response with deliberately out-of-order samples."""
    return {
        "devices": [
            {
                "id": 42,
                "uid": "device-42",
                "name": "Monitor",
                "displayName": "Kitchen",
                "timezone": "UTC",
                "sensors": {
                    "temperature": {
                        "name": "temperature",
                        "displayName": "Temperature",
                        "unit": "°C",
                        "description": "Ambient temperature",
                        "values": [
                            {"timestamp": "2026-10-15T12:00:00Z", "value": 23.5},
                            {"timestamp": "2026-10-15T11:00:00Z", "value": 19.0},
                        ],
                    }
                },
            }
        ],
    }


@pytest.fixture
async def coordinator(hass: HomeAssistant, payload) -> AsyncIterator:
    """Fetch through the SDK parser without allowing external HTTP."""
    requests = []

    def respond(request):
        assert request.url.host == "backend.invalid"
        requests.append(request)
        return httpx.Response(200, json=payload)

    client = await hass.async_add_executor_job(
        lambda: AirbeldClient(token="test-only", base_url="https://backend.invalid")
    )
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(respond),
        headers={"Authorization": "Bearer stale-test-only"},
    )
    session = AsyncMock()
    session.token = {"access_token": "refreshed-test-only"}
    result = AirbeldDataUpdateCoordinator(hass, client, session)
    result.data = await result._async_update_data()
    result.last_update_success = True
    result.test_requests = requests
    yield result
    await client.aclose()
