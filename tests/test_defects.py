"""Desired behavior: each strict AssertionError xfail pins an unfixed H defect."""

from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers import config_entry_oauth2_flow
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbeld import async_setup_entry
from custom_components.airbeld.config_flow import (
    OAuth2FlowHandler,
    async_register_implementation,
)
from custom_components.airbeld.const import DOMAIN, SENSOR_DEVICE_CLASSES
from custom_components.airbeld.sensor import AirbeldSensor
from custom_components.airbeld.sensor import async_setup_entry as setup_sensors


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="H1: no entry identity")
async def test_h1_entry_unique_id(hass):
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.context = {"source": config_entries.SOURCE_USER}
    await flow.async_oauth_create_entry({"token": {"access_token": "test-only"}})
    assert flow.unique_id is not None


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="H2: no reauth flow")
async def test_h2_reauth(hass):
    flow = OAuth2FlowHandler()
    flow.hass = hass
    # Stop with the intended AssertionError rather than a missing-method error.
    assert callable(getattr(flow, "async_step_reauth", None))
    result = await flow.async_step_reauth({"token": {"access_token": "test-only"}})
    assert result["type"] in {"form", "external"}


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="H3: fake PKCE")
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


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="H4: no runtime_data")
async def test_h4_runtime_data(hass, coordinator):
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
        ),
    ):
        await async_setup_entry(hass, entry)
    assert getattr(entry, "runtime_data", None) is coordinator


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="H5: missing has_entity_name"
)
async def test_h5_entity_name(coordinator):
    sensor = AirbeldSensor(
        coordinator,
        42,
        coordinator.data[42]["device"],
        "temperature",
        coordinator.data[42]["telemetry"]["temperature"],
    )
    assert sensor.has_entity_name


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="H6: only first refresh creates entities"
)
async def test_h6_discover_after_refresh(hass, coordinator):
    entry = MockConfigEntry(domain=DOMAIN)
    hass.data[DOMAIN] = {entry.entry_id: coordinator}
    entities = []
    await setup_sensors(hass, entry, lambda items, **kwargs: entities.extend(items))
    assert len(entities) == 1
    changed = dict(coordinator.data)
    changed[84] = coordinator.data[42]
    coordinator.async_set_updated_data(changed)
    await hass.async_block_till_done()
    assert {entity.unique_id for entity in entities} == {
        "airbeld_42_temperature",
        "airbeld_84_temperature",
    }


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="H7: wrong device classes"
)
async def test_h7_device_classes(coordinator):
    # PM4 is absent at the floor: never mislabel it as PM10 there.
    expected = getattr(SensorDeviceClass, "PM4", None)
    sensor = AirbeldSensor(
        coordinator,
        42,
        coordinator.data[42]["device"],
        "pm4",
        {"display_name": "PM4", "unit": "µg/m³"},
    )
    assert {
        "pm4": sensor.device_class,
        "voc": SENSOR_DEVICE_CLASSES.get("voc"),
        "nox": SENSOR_DEVICE_CLASSES.get("nox"),
    } == {"pm4": expected, "voc": None, "nox": None}
