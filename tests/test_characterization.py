"""Preserve today's config flow, coordinator, sensor and unload behavior."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbeld import async_setup_entry, async_unload_entry
from custom_components.airbeld.config_flow import (
    OAuth2FlowHandler,
    async_register_implementation,
)
from custom_components.airbeld.const import DOMAIN
from custom_components.airbeld.sensor import AirbeldSensor
from custom_components.airbeld.sensor import async_setup_entry as setup_sensors


async def test_oauth_entry_and_registration(hass):
    """Registration is idempotent and entry data retains refresh capability."""
    await async_register_implementation(hass)
    first = await config_entry_oauth2_flow.async_get_implementations(hass, DOMAIN)
    await async_register_implementation(hass)
    second = await config_entry_oauth2_flow.async_get_implementations(hass, DOMAIN)
    assert first[DOMAIN] is second[DOMAIN]
    flow = OAuth2FlowHandler()
    flow.hass = hass
    data = {"auth_implementation": DOMAIN, "token": {"access_token": "test-only"}}
    result = await flow.async_oauth_create_entry(data)
    assert result["type"] == "create_entry"
    assert result["title"] == "Airbeld"
    assert result["data"] == data


async def test_coordinator_http_and_latest_sample(coordinator):
    """The real SDK receives refreshed auth and parses latest sample metadata."""
    request = coordinator.test_requests[0]
    assert request.url.path == "/api/v1/devices/all_readings_by_date/"
    assert request.headers["Authorization"] == "Bearer refreshed-test-only"
    coordinator.session.async_ensure_token_valid.assert_awaited_once()
    assert coordinator.data[42]["telemetry"]["temperature"] == {
        "value": 23.5,
        "display_name": "Temperature",
        "unit": "°C",
        "description": "Ambient temperature",
    }


async def test_coordinator_http_failure(coordinator):
    """An SDK HTTP auth error currently surfaces as UpdateFailed."""
    coordinator.client._client._transport = httpx.MockTransport(
        lambda request: httpx.Response(401, json={"detail": "unauthorized"})
    )
    with pytest.raises(UpdateFailed, match="Error communicating with API"):
        await coordinator._async_update_data()


async def test_sensor_values_metadata_and_availability(hass, coordinator):
    """Entities expose SDK metadata and track coordinator updates/removal."""
    entry = MockConfigEntry(domain=DOMAIN)
    hass.data[DOMAIN] = {entry.entry_id: coordinator}
    entities = []
    await setup_sensors(hass, entry, lambda items, **kwargs: entities.extend(items))
    assert len(entities) == 1
    sensor = entities[0]
    assert sensor.unique_id == "airbeld_42_temperature"
    assert sensor.name == "Temperature"
    assert sensor.device_class == SensorDeviceClass.TEMPERATURE
    assert sensor.state_class == SensorStateClass.MEASUREMENT
    assert sensor.native_unit_of_measurement == "°C"
    assert sensor.native_value == 23.5
    assert sensor.device_info["identifiers"] == {(DOMAIN, 42)}
    assert sensor.device_info["name"] == "Kitchen"
    assert sensor.extra_state_attributes == {"description": "Ambient temperature"}
    assert sensor.available
    coordinator.data[42]["telemetry"]["temperature"]["value"] = 27.0
    assert sensor.native_value == 27.0
    coordinator.last_update_success = False
    assert not sensor.available
    coordinator.last_update_success = True
    coordinator.data = {}
    assert not sensor.available
    assert sensor.native_value is None


async def test_dimensionless_unit(coordinator):
    """An SDK dash is not sent to HA as a measurement unit."""
    sensor = AirbeldSensor(
        coordinator,
        42,
        coordinator.data[42]["device"],
        "iaq",
        {
            "display_name": "IAQ",
            "unit": "-",
            "value": 80,
        },
    )
    assert sensor.native_unit_of_measurement is None


async def test_setup_and_unload(hass, coordinator):
    """Entry setup stores the coordinator; successful unload closes the SDK."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "test-only", "expires_at": 9999999999},
        },
    )
    entry.add_to_hass(hass)
    await async_register_implementation(hass)
    with (
        patch(
            "custom_components.airbeld.AirbeldClient", return_value=coordinator.client
        ),
        patch(
            "custom_components.airbeld.AirbeldDataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(coordinator, "async_config_entry_first_refresh", new=AsyncMock()),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ) as forward,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new=AsyncMock(return_value=True),
        ),
        patch.object(
            coordinator.client, "aclose", wraps=coordinator.client.aclose
        ) as close,
    ):
        assert await async_setup_entry(hass, entry)
        assert hass.data[DOMAIN][entry.entry_id] is coordinator
        forward.assert_awaited_once()
        assert await async_unload_entry(hass, entry)
        close.assert_awaited_once()
        assert DOMAIN not in hass.data
