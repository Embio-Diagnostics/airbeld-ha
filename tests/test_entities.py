"""Task 22 at the SDK, live entity platform, registries and recorder boundary."""

import json
from datetime import timedelta
from unittest.mock import patch

import httpx
import pytest
from homeassistant.components.recorder.db_schema import Statistics
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.recorder.models import (
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    get_metadata,
)
from homeassistant.components.recorder.tasks import StatisticsTask
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_recorder_block_till_done,
)

from custom_components.airbeld.const import DOMAIN
from custom_components.airbeld.diagnostics import async_get_config_entry_diagnostics
from custom_components.airbeld.identity import device_identifier, sensor_unique_id
from tests import test_upgrade
from tests.test_upgrade import seed


@pytest.fixture
def recorder_db_url():
    """Use an isolated in-memory recorder for the direct candidate upgrade."""
    return "sqlite://"


@pytest.fixture
def entity_history_recorder(request):
    """Reuse the supported-version recorder annotation workaround."""
    yield from test_upgrade.history_recorder.__wrapped__(request)


async def load(hass, coordinator):
    """Use HA's real sensor platform, not registry rows made by the test."""
    with patch(
        "custom_components.airbeld.get_async_client",
        return_value=coordinator.test_shared,
    ):
        assert await hass.config_entries.async_setup(coordinator.entry.entry_id)
        await hass.async_block_till_done()
    return coordinator.entry.runtime_data


def device_row(hass, coordinator, uid="device-42"):
    identifier = (
        DOMAIN,
        device_identifier(coordinator.environment, coordinator.subject, uid),
    )
    return next(
        (
            row
            for row in dr.async_entries_for_config_entry(
                dr.async_get(hass), coordinator.entry.entry_id
            )
            if identifier in row.identifiers
        ),
        None,
    )


async def test_inventory_discovery_absences_failures_and_reset(hass, coordinator):
    current = await load(hass, coordinator)
    registry = er.async_get(hass)
    original = device_row(hass, current)
    coordinator.test_inventory.append(
        {
            "uid": "new-device",
            "name": "New",
            "displayName": "Office",
            "status": "online",
        }
    )
    coordinator.test_payload["results"].append(
        {**coordinator.test_payload["results"][0], "uid": "new-device"}
    )
    await current.async_refresh()
    await hass.async_block_till_done()
    new_row = device_row(hass, current, "new-device")
    assert new_row is not None
    assert any(row.device_id == new_row.id for row in registry.entities.values())
    coordinator.test_inventory.pop(0)
    await current.async_refresh()
    assert current.absences["device-42"] == 1
    transport = coordinator.test_shared._transport

    def fail_inventory(request):
        if request.url.path == "/api/v2/devices/":
            return httpx.Response(503, json={})
        return transport.handler(request)

    coordinator.test_shared._transport = httpx.MockTransport(fail_inventory)
    await current.async_refresh()
    assert current.absences["device-42"] == 1
    assert dr.async_get(hass).async_get(original.id)

    def partial_inventory(request):
        if request.url.path == "/api/v2/devices/":
            return httpx.Response(
                200, json=[coordinator.test_inventory[0], {"uid": "bad"}]
            )
        return transport.handler(request)

    coordinator.test_shared._transport = httpx.MockTransport(partial_inventory)
    await current.async_refresh()
    assert current.absences["device-42"] == 1
    coordinator.test_shared._transport = transport
    coordinator.test_inventory.append(
        {
            "uid": "device-42",
            "name": "Monitor",
            "displayName": "Kitchen",
            "status": "offline",
        }
    )
    for _ in range(3):
        await current.async_refresh()
    assert current.absences["device-42"] == 0
    assert dr.async_get(hass).async_get(original.id)
    coordinator.test_inventory.pop()

    def fail_telemetry(request):
        if request.url.path == "/api/v2/readings/batch/":
            return httpx.Response(503, json={})
        return transport.handler(request)

    coordinator.test_shared._transport = httpx.MockTransport(fail_telemetry)
    await current.async_refresh()
    assert current.absences["device-42"] == 1
    assert dr.async_get(hass).async_get(new_row.id)
    coordinator.test_shared._transport = transport
    await current.async_refresh()
    assert dr.async_get(hass).async_get(original.id)
    await current.async_refresh()
    await hass.async_block_till_done()
    assert dr.async_get(hass).async_get(original.id) is None
    assert not any(row.device_id == original.id for row in registry.entities.values())
    # A rediscovered device must also regain its sensor after a prior cleanup.
    coordinator.test_inventory.append(
        {
            "uid": "device-42",
            "name": "Monitor",
            "displayName": "Kitchen",
            "status": "online",
        }
    )
    await current.async_refresh()
    await hass.async_block_till_done()
    assert device_row(hass, current)
    assert registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        sensor_unique_id(
            current.environment, current.subject, "device-42", "temperature"
        ),
    )


@pytest.mark.parametrize(
    ("status", "stale"), [("offline", False), ("online", True), ("online", False)]
)
async def test_inventory_present_availability(hass, coordinator, status, stale):
    coordinator.test_inventory[0].update(status=status, stale=stale)
    current = await load(hass, coordinator)
    for _ in range(4):
        await current.async_refresh()
    await hass.async_block_till_done()
    assert device_row(hass, current)
    assert current.absences["device-42"] == 0
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor",
        DOMAIN,
        sensor_unique_id(
            current.environment, current.subject, "device-42", "temperature"
        ),
    )
    state = hass.states.get(entity_id)
    assert state.name == "Kitchen Temperature"
    assert (state.state == "unavailable") == (status == "offline" or stale)


@pytest.mark.parametrize("sibling_loaded", [True, False])
async def test_cleanup_isolated_from_sibling_and_unresolved(
    hass, coordinator, sibling_loaded
):
    current = await load(hass, coordinator)
    sibling = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={**coordinator.entry.data, "sub": "auth0|sibling"},
    )
    sibling.add_to_hass(hass)
    with patch(
        "custom_components.airbeld.get_async_client",
        return_value=coordinator.test_shared,
    ):
        assert await hass.config_entries.async_setup(sibling.entry_id)
        await hass.async_block_till_done()
    sibling_device = device_row(hass, sibling.runtime_data)
    sibling_entities = er.async_entries_for_config_entry(
        er.async_get(hass), sibling.entry_id
    )
    if not sibling_loaded:
        assert await hass.config_entries.async_unload(sibling.entry_id)
    missing_device, missing_entities = seed(hass, current.entry, 99, ["temperature"])
    hass.config_entries.async_update_entry(
        current.entry, data={**current.entry.data, "unresolved_legacy": ["99"]}
    )
    own = device_row(hass, current)
    coordinator.test_inventory.clear()
    for _ in range(3):
        await current.async_refresh()
    await hass.async_block_till_done()
    assert dr.async_get(hass).async_get(own.id) is None
    assert dr.async_get(hass).async_get(sibling_device.id) == sibling_device
    for row in sibling_entities + missing_entities:
        assert er.async_get(hass).async_get(row.entity_id) == row
    assert dr.async_get(hass).async_get(missing_device.id) == missing_device


@pytest.mark.parametrize("pre_disabled", [True, False])
async def test_direct_012_indexes_once_with_recorder(
    hass, coordinator, entity_history_recorder, pre_disabled
):
    await entity_history_recorder(hass)
    entry = coordinator.entry
    hass.config_entries.async_update_entry(
        entry, version=1, data={**entry.data, "migration_pending": True}
    )
    _, old = seed(hass, entry, 42, ["voc", "nox", "temperature"])
    registry = er.async_get(hass)
    if not pre_disabled:
        for row in old[:2]:
            registry.async_update_entity(row.entity_id, disabled_by=None)
    start = dt_util.utcnow() - timedelta(seconds=1)
    for row in old[:2]:
        hass.states.async_set(
            row.entity_id, "19", {"state_class": "measurement", "device_class": "aqi"}
        )
    await hass.async_block_till_done()
    await async_recorder_block_till_done(hass)
    # Seed the pre-existing recorder statistics as well as 0.1.2 registry rows.
    # The new statistics below must instead be produced by the candidate sensor.
    for row in old[:2]:
        recorder_helper.get_instance(hass).async_import_statistics(
            {
                "statistic_id": row.entity_id,
                "source": "recorder",
                "name": None,
                "mean_type": StatisticMeanType.ARITHMETIC,
                "has_sum": False,
                "unit_of_measurement": None,
                **(
                    {"unit_class": "unitless"}
                    if "unit_class" in StatisticMetaData.__annotations__
                    else {}
                ),
            },
            [
                {
                    "start": start.replace(minute=0, second=0, microsecond=0)
                    - timedelta(hours=1),
                    "mean": 19,
                    "min": 19,
                    "max": 19,
                }
            ],
            Statistics,
        )
    await async_recorder_block_till_done(hass)
    before_metadata = await hass.async_add_executor_job(get_metadata, hass)
    assert {row.entity_id for row in old[:2]} <= set(before_metadata)
    for key in ("voc", "nox"):
        coordinator.test_payload["results"][0]["sensors"][key] = {
            **coordinator.test_payload["results"][0]["sensors"]["temperature"],
            "name": key,
            "displayName": key,
            "unit": "-",
        }
    current = await load(hass, coordinator)
    new_ids = []
    for row in old[:2]:
        key = "voc" if row == old[0] else "nox"
        retired = registry.async_get(row.entity_id)
        assert retired.unique_id == row.unique_id
        assert retired.disabled_by == (
            er.RegistryEntryDisabler.USER
            if pre_disabled
            else er.RegistryEntryDisabler.INTEGRATION
        )
        replacement_id = registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            sensor_unique_id(
                current.environment, current.subject, "device-42", f"{key}_index"
            ),
        )
        assert replacement_id is not None
        assert replacement_id != row.entity_id
        assert replacement_id.endswith(f"{key}_index")
        state = hass.states.get(replacement_id)
        assert "device_class" not in state.attributes
        assert state.attributes["state_class"] == "measurement"
        new_ids.append(replacement_id)
    assert (
        registry.async_get(old[2].entity_id).disabled_by
        == er.RegistryEntryDisabler.USER
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    current = await load(hass, coordinator)
    await current.async_refresh()
    await hass.async_block_till_done()
    assert (
        len([row for row in registry.entities.values() if row.entity_id in new_ids])
        == 2
    )
    await async_recorder_block_till_done(hass)
    history = await hass.async_add_executor_job(
        get_significant_states, hass, start, None, [row.entity_id for row in old[:2]]
    )
    assert all(history[row.entity_id][0].state == "19" for row in old[:2])
    # Let HA's real sensor statistics compiler create independent metadata.
    recorder_helper.get_instance(hass).queue_task(
        StatisticsTask(
            start.replace(minute=start.minute // 5 * 5, second=0, microsecond=0),
            fire_events=False,
        )
    )
    await async_recorder_block_till_done(hass)
    metadata = await hass.async_add_executor_job(get_metadata, hass)
    assert set(new_ids) <= set(metadata)
    assert all(metadata[entity_id][1]["source"] == "recorder" for entity_id in new_ids)
    for row in old[:2]:
        assert metadata[row.entity_id] == before_metadata[row.entity_id]
    assert (
        len(
            {
                metadata[entity_id][0]
                for entity_id in new_ids + [row.entity_id for row in old[:2]]
            }
        )
        == 4
    )


async def test_diagnostics_redacts_entry_recursively(hass, coordinator):
    result = await async_get_config_entry_diagnostics(hass, coordinator.entry)
    encoded = json.dumps(result)
    assert "test-only" not in encoded
    assert "auth0|one" not in encoded
    assert result["entry"]["data"]["token"] == "**REDACTED**"  # noqa: S105 — HA redaction sentinel
    assert result["entry"]["data"]["sub"] == "**REDACTED**"


async def test_three_absences_with_failed_telemetry_do_not_resurrect(hass, coordinator):
    current = await load(hass, coordinator)
    own = device_row(hass, current)
    coordinator.test_inventory[:] = [
        {"uid": "other", "name": "Other", "displayName": "Other"}
    ]
    transport = coordinator.test_shared._transport

    def fail_telemetry(request):
        if request.url.path == "/api/v2/readings/batch/":
            return httpx.Response(503, json={})
        return transport.handler(request)

    coordinator.test_shared._transport = httpx.MockTransport(fail_telemetry)
    for attempt in range(4):
        if attempt == 1:
            coordinator.test_inventory.append(
                {"uid": "later", "name": "Later", "displayName": "Later"}
            )
        await current.async_refresh()
        await hass.async_block_till_done()
    assert dr.async_get(hass).async_get(own.id) is None
    assert not er.async_entries_for_config_entry(
        er.async_get(hass), current.entry.entry_id
    )
    assert device_row(hass, current, "other") is not None
    assert device_row(hass, current, "later") is not None


async def test_pm4_keeps_registry_and_statistic(
    hass, coordinator, entity_history_recorder
):
    await entity_history_recorder(hass)
    entry = coordinator.entry
    hass.config_entries.async_update_entry(
        entry, version=1, data={**entry.data, "migration_pending": True}
    )
    _, rows = seed(hass, entry, 42, ["pm4"])
    registry = er.async_get(hass)
    old = registry.async_update_entity(
        rows[0].entity_id,
        disabled_by=None,
        original_device_class="pm10",
        unit_of_measurement="µg/m³",
    )
    recorder_helper.get_instance(hass).async_import_statistics(
        {
            "statistic_id": old.entity_id,
            "source": "recorder",
            "name": None,
            "mean_type": StatisticMeanType.ARITHMETIC,
            "has_sum": False,
            "unit_of_measurement": "µg/m³",
            **(
                {"unit_class": "mass_concentration"}
                if "unit_class" in StatisticMetaData.__annotations__
                else {}
            ),
        },
        [
            {
                "start": dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
                - timedelta(hours=1),
                "mean": 19,
                "min": 19,
                "max": 19,
            }
        ],
        Statistics,
    )
    await async_recorder_block_till_done(hass)
    before = await hass.async_add_executor_job(get_metadata, hass)
    coordinator.test_payload["results"][0]["sensors"]["pm4"] = {
        **coordinator.test_payload["results"][0]["sensors"]["temperature"],
        "name": "pm4",
        "displayName": "PM4",
        "unit": "µg/m³",
    }
    await load(hass, coordinator)
    assert registry.async_get(old.entity_id).unique_id == sensor_unique_id(
        entry.data["environment"], entry.data["sub"], "device-42", "pm4"
    )
    assert hass.states.get(old.entity_id).attributes["device_class"] == "pm4"
    assert hass.states.get(old.entity_id).attributes["unit_of_measurement"] == "μg/m³"
    after = await hass.async_add_executor_job(get_metadata, hass)
    assert after[old.entity_id] == before[old.entity_id]
