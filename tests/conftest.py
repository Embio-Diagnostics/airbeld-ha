"""Credential-free v2 fixture backend using the real candidate SDK."""

from unittest.mock import AsyncMock

import httpx
import pytest
from airbeld import AirbeldClient
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbeld.const import DOMAIN
from custom_components.airbeld.coordinator import AirbeldDataUpdateCoordinator


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Enable the integration in HA's loader."""


@pytest.fixture
def payload():
    return {
        "period": "latest",
        "start": None,
        "end": None,
        "truncatedTo": None,
        "results": [
            {
                "uid": "device-42",
                "status": "ok",
                "sensors": {
                    "temperature": {
                        "name": "temperature",
                        "displayName": "Temperature",
                        "unit": "°C",
                        "description": "Ambient temperature",
                        "descriptionEl": None,
                        "aggregates": {"avg": 21.25, "max": 23.5},
                        "values": [
                            {"timestamp": "2026-10-15T11:00:00Z", "value": 19.0},
                            {"timestamp": "2026-10-15T12:00:00Z", "value": 23.5},
                        ],
                    }
                },
            }
        ],
    }


@pytest.fixture
async def coordinator(hass, payload):
    requests = []
    inventory = [
        {
            "uid": "device-42",
            "name": "Monitor",
            "displayName": "Kitchen",
            "legacyId": None,
            "status": "online",
        }
    ]

    def respond(request):
        assert request.url.host == "backend.invalid"
        requests.append(request)
        if request.url.path == "/api/v2/devices/":
            return httpx.Response(200, json=inventory)
        if request.url.path == "/api/v2/readings/batch/":
            return httpx.Response(200, json=payload)
        if request.url.path == "/api/v2/integrations/legacy-device-ids/resolve":
            return httpx.Response(200, json=[{"id": 42, "uid": "device-42"}])
        message = f"Unexpected endpoint {request.url.path}"
        raise AssertionError(message)

    shared = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client = AirbeldClient(
        token="test-only", base_url="https://backend.invalid", client=shared
    )
    session = AsyncMock()
    session.token = {"access_token": "refreshed-test-only"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={
            "environment": "https://backend.invalid",
            "sub": "auth0|one",
            "auth_implementation": DOMAIN,
            "token": {"access_token": "test-only", "expires_at": 9999999999},
        },
    )
    entry.add_to_hass(hass)
    result = AirbeldDataUpdateCoordinator(hass, client, session, entry)
    result.data = await result._async_update_data()
    result.last_update_success = True
    result.test_requests = requests
    result.test_inventory = inventory
    result.test_shared = shared
    result.test_payload = payload
    entry.runtime_data = result
    yield result
    await shared.aclose()
