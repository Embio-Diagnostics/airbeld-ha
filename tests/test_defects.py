"""Desired behavior: each strict AssertionError xfail pins an unfixed H defect."""

from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers import config_entry_oauth2_flow

from custom_components.airbeld import async_setup_entry
from custom_components.airbeld.config_flow import (
    OAuth2FlowHandler,
    async_register_implementation,
)
from custom_components.airbeld.const import DOMAIN, SENSOR_DEVICE_CLASSES
from custom_components.airbeld.identity import sensor_unique_id
from custom_components.airbeld.sensor import AirbeldSensor
from custom_components.airbeld.sensor import async_setup_entry as setup_sensors


async def test_h1_entry_unique_id(hass):
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.context = {"source": config_entries.SOURCE_USER}
    with patch(
        "custom_components.airbeld.config_flow.async_subject", return_value="auth0|one"
    ):
        await flow.async_oauth_create_entry({"token": {"access_token": "test-only"}})
    assert flow.unique_id is not None


async def test_h2_reauth(hass):
    flow = OAuth2FlowHandler()
    flow.hass = hass
    # Stop with the intended AssertionError rather than a missing-method error.
    assert callable(getattr(flow, "async_step_reauth", None))
    result = await flow.async_step_reauth({"token": {"access_token": "test-only"}})
    assert result["type"] in {"form", "external"}


async def test_h3_pkce_authorization(hass):
    await async_register_implementation(hass)
    flow = OAuth2FlowHandler()
    flow.hass = hass
    implementations = await config_entry_oauth2_flow.async_get_implementations(
        hass, DOMAIN
    )
    implementation = implementations[DOMAIN]
    with patch.object(
        type(implementation),
        "redirect_uri",
        new=property(lambda self: "http://localhost:8123/auth/external/callback"),
    ):
        url = await implementation.async_generate_authorize_url("flow-test")
    params = parse_qs(urlparse(url).query)
    params.update({key: [value] for key, value in flow.extra_authorize_data.items()})
    assert params.get("code_challenge"), "S256 without a challenge is not PKCE"


async def test_h4_runtime_data(hass, coordinator):
    entry = coordinator.entry
    entry.runtime_data = None
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
        ),
    ):
        await async_setup_entry(hass, entry)
    assert getattr(entry, "runtime_data", None) is coordinator


async def test_h5_entity_name(coordinator):
    sensor = AirbeldSensor(
        coordinator,
        "device-42",
        coordinator.data["device-42"]["device"],
        "temperature",
        coordinator.data["device-42"]["telemetry"]["temperature"],
    )
    assert sensor.has_entity_name


async def test_h6_discover_after_refresh(hass, coordinator):
    entry = coordinator.entry
    entities = []
    await setup_sensors(hass, entry, lambda items, **kwargs: entities.extend(items))
    assert len(entities) == 1
    changed = dict(coordinator.data)
    changed["device-84"] = coordinator.data["device-42"]
    coordinator.inventory["device-84"] = coordinator.inventory["device-42"]
    coordinator.async_set_updated_data(changed)
    await hass.async_block_till_done()
    assert {entity.unique_id for entity in entities} == {
        entities[0].unique_id,
        sensor_unique_id(
            coordinator.environment, coordinator.subject, "device-84", "temperature"
        ),
    }


async def test_h7_device_classes(coordinator):
    expected = SensorDeviceClass.PM4
    sensor = AirbeldSensor(
        coordinator,
        "device-42",
        coordinator.data["device-42"]["device"],
        "pm4",
        {"display_name": "PM4", "unit": "µg/m³"},
    )
    assert {
        "pm4": sensor.device_class,
        "voc": SENSOR_DEVICE_CLASSES.get("voc"),
        "nox": SENSOR_DEVICE_CLASSES.get("nox"),
    } == {"pm4": expected, "voc": None, "nox": None}
