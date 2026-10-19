"""Exercise the upgrade at real SDK, HA registry and OAuth boundaries."""

import asyncio
import base64
import hashlib
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import orjson
import pytest
from aiohttp import ClientResponseError
from airbeld.exceptions import AuthError, UpstreamError
from cryptography.hazmat.primitives.asymmetric import rsa
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder import migration as recorder_migration
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import config_entry_oauth2_flow as oauth
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_recorder_block_till_done,
)
from sqlalchemy.orm import Session

from custom_components.airbeld import (
    async_migrate_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.airbeld.config_flow import (
    OAuth2FlowHandler,
    async_register_implementation,
)
from custom_components.airbeld.const import DOMAIN
from custom_components.airbeld.diagnostics import async_get_config_entry_diagnostics
from custom_components.airbeld.identity import (
    account_id,
    async_legacy_subject,
    async_subject,
    device_identifier,
    sensor_unique_id,
)
from custom_components.airbeld.migration import async_complete_migration
from custom_components.airbeld.repairs import async_create_fix_flow
from custom_components.airbeld.sensor import async_setup_entry as setup_sensors


def seed(hass, entry, pk, keys):
    devices, entities = dr.async_get(hass), er.async_get(hass)
    device = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, str(pk))}, name="Kitchen"
    )
    area = ar.async_get(hass).async_get_or_create("Kitchen")
    device = devices.async_update_device(
        device.id, name_by_user="My monitor", area_id=area.id
    )
    rows = []
    for key in keys:
        row = entities.async_get_or_create(
            "sensor",
            DOMAIN,
            f"airbeld_{pk}_{key}",
            config_entry=entry,
            device_id=device.id,
            suggested_object_id=f"kitchen_{key}",
            original_device_class="aqi" if key in ("voc", "nox") else "temperature",
        )
        row = entities.async_update_entity(
            row.entity_id,
            name=f"Custom {key}",
            area_id=area.id,
            disabled_by=er.RegistryEntryDisabler.USER,
        )
        rows.append(row)
    return device, rows


@pytest.fixture
def recorder_db_url():
    """Keep the history acceptance test's database isolated and in memory."""
    return "sqlite://"


@pytest.mark.parametrize(
    ("status", "expected"), [(400, ConfigEntryAuthFailed), (503, ConfigEntryNotReady)]
)
async def test_token_refresh_setup_failure_mapping(hass, coordinator, status, expected):
    error = ClientResponseError(
        SimpleNamespace(real_url="https://auth.invalid"), (), status=status
    )
    with (
        patch(
            "custom_components.airbeld.config_entry_oauth2_flow.OAuth2Session",
            return_value=coordinator.session,
        ),
        patch.object(
            coordinator.session, "async_ensure_token_valid", side_effect=error
        ),
        pytest.raises(expected),
    ):
        await async_setup_entry(hass, coordinator.entry)


@pytest.fixture
def history_recorder(request):
    """Supply HA's TYPE_CHECKING annotations to Python 3.14 fixture autospec."""
    with (
        patch.object(recorder_migration, "Recorder", Recorder, create=True),
        patch.object(recorder_migration, "Session", Session, create=True),
        patch.object(recorder_helper, "Session", Session, create=True),
    ):
        yield request.getfixturevalue("async_setup_recorder_instance")


async def test_direct_upgrade_journal_resume_and_unresolved(hass, coordinator):  # noqa: PLR0915 — one interrupted direct-upgrade sequence
    entry = coordinator.entry
    hass.config_entries.async_update_entry(
        entry, version=1, data={**entry.data, "migration_pending": True}
    )
    device, rows = seed(hass, entry, 42, ["temperature", "voc", "nox"])
    missing_device, missing_rows = seed(hass, entry, 99, ["temperature"])
    assert await async_migrate_entry(hass, entry)
    assert entry.version == 2
    assert entry.data["migration_pending"]
    registry = er.async_get(hass)
    original = registry.async_update_entity
    rewrites = 0

    def interrupt(entity_id, **kwargs: Any):
        nonlocal rewrites
        result = original(entity_id, **kwargs)
        rewrites += 1
        if rewrites == 1:
            message = "power lost after registry write"
            raise RuntimeError(message)
        return result

    with (
        patch.object(registry, "async_update_entity", side_effect=interrupt),
        pytest.raises(RuntimeError, match="power lost"),
    ):
        await async_complete_migration(hass, entry, coordinator)
    assert entry.data["migration_pending"]
    assert "42" not in entry.data.get("legacy_migration_done", {})
    # The registries can reach disk before the per-id marker. Reload that partial
    # rewrite: the source journal must still carry the now-scoped ordinary row.
    entity_snapshot = orjson.loads(orjson.dumps(registry._data_to_save()))
    device_snapshot = orjson.loads(orjson.dumps(dr.async_get(hass)._data_to_save()))
    await hass.async_block_till_done()
    stored = await hass.config_entries._store.async_load()
    stored_entry = next(
        item for item in stored["entries"] if item["entry_id"] == entry.entry_id
    )
    assert (
        stored_entry["data"]["legacy_migration_rows"]["42"][0]["entity_id"]
        == rows[0].entity_id
    )
    # Rebuild the registries from serialized partial-interruption rows and the entry
    # from its saved journal, discarding the interrupted in-memory rewrite.
    entity_store = registry._store
    device_store = dr.async_get(hass)._store
    hass.data.pop(er.DATA_REGISTRY)
    hass.data.pop(dr.DATA_REGISTRY)
    hass.data[dr.DATA_REGISTRY] = dr.DeviceRegistry(hass)
    hass.data[er.DATA_REGISTRY] = er.EntityRegistry(hass)
    with patch.object(
        dr.async_get(hass)._store, "async_load", return_value=device_snapshot
    ):
        await dr.async_get(hass).async_load()
    with patch.object(
        er.async_get(hass)._store, "async_load", return_value=entity_snapshot
    ):
        await er.async_get(hass).async_load()
    registry = er.async_get(hass)
    object.__setattr__(entry, "data", stored_entry["data"])
    await async_complete_migration(hass, entry, coordinator)
    assert not entry.data["migration_pending"]
    assert entry.data["legacy_migration_done"] == {"42": "device-42"}
    assert len(entry.data["legacy_migration_rows"]["42"]) == 3
    assert entry.data["unresolved_legacy"] == ["99"]
    assert registry.async_get(missing_rows[0].entity_id) == missing_rows[0]
    assert dr.async_get(hass).async_get(missing_device.id) == missing_device
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"unresolved_{entry.entry_id}")
    for row in rows:
        current = registry.async_get(row.entity_id)
        assert current.entity_id == row.entity_id
        assert current.name == row.name
        assert current.area_id == row.area_id
        assert current.disabled_by == row.disabled_by
        assert current.device_id == device.id
    assert registry.async_get(rows[0].entity_id).unique_id == sensor_unique_id(
        coordinator.environment, coordinator.subject, "device-42", "temperature"
    )
    for row in rows[1:]:
        assert registry.async_get(row.entity_id).unique_id == row.unique_id
        assert entry.data["legacy_voc_nox"][row.entity_id]["uid"] == "device-42"
    assert dr.async_get(hass).async_get(device.id).identifiers == {
        (
            DOMAIN,
            device_identifier(
                coordinator.environment, coordinator.subject, "device-42"
            ),
        )
    }
    migrated_device = dr.async_get(hass).async_get(device.id)
    assert migrated_device.name_by_user == device.name_by_user
    assert migrated_device.area_id == device.area_id
    for key in ("voc", "nox"):
        coordinator.data["device-42"]["telemetry"][key] = {
            "display_name": key,
            "unit": "-",
            "value": 42,
        }
    sensors = []
    await setup_sensors(hass, entry, lambda items, **kw: sensors.extend(items))
    assert {sensor.unique_id for sensor in sensors} == {
        sensor_unique_id(
            coordinator.environment, coordinator.subject, "device-42", "temperature"
        ),
        sensor_unique_id(
            coordinator.environment, coordinator.subject, "device-42", "voc_index"
        ),
        sensor_unique_id(
            coordinator.environment, coordinator.subject, "device-42", "nox_index"
        ),
    }
    assert all(sensor.native_value is not None for sensor in sensors)
    before = dict(entry.data)
    with patch.object(
        coordinator.client,
        "resolve_legacy_device_ids",
        side_effect=AssertionError("must not re-resolve"),
    ):
        await async_complete_migration(hass, entry, coordinator)
    assert dict(entry.data) == before
    # legacyId is null: resolver, not the cohort list field, supplied this mapping.
    assert coordinator.test_inventory[0]["legacyId"] is None
    resolver = [r for r in coordinator.test_requests if r.url.path.endswith("resolve")]
    assert len(resolver) == 2
    assert b"42" in resolver[0].content
    assert entity_store.key == registry._store.key
    assert device_store.key == dr.async_get(hass)._store.key


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AuthError(), ConfigEntryAuthFailed),
        (UpstreamError("HTTP 503", 503), ConfigEntryNotReady),
    ],
)
async def test_migration_auth_and_backend_retry(hass, coordinator, error, expected):
    entry = coordinator.entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "migration_pending": True}
    )
    _, rows = seed(hass, entry, 42, ["temperature"])
    with (
        patch.object(
            coordinator.client, "resolve_legacy_device_ids", side_effect=error
        ),
        pytest.raises(expected),
    ):
        await async_complete_migration(hass, entry, coordinator)
    assert entry.data["migration_pending"]
    assert (
        er.async_get(hass).async_get(rows[0].entity_id).unique_id == rows[0].unique_id
    )
    await async_complete_migration(hass, entry, coordinator)
    assert entry.data["legacy_migration_done"] == {"42": "device-42"}


@pytest.mark.parametrize("registration", ["setup", "flow"])
async def test_pkce_wire_both_paths(hass, registration, aioclient_mock):
    if registration == "setup":
        await async_setup(hass, {})
    else:
        await async_register_implementation(hass)
    implementation = (await oauth.async_get_implementations(hass, DOMAIN))[DOMAIN]
    flow = OAuth2FlowHandler()
    flow.hass, flow.flow_impl, flow.flow_id = hass, implementation, "pkce-test"
    with patch.object(
        type(implementation),
        "redirect_uri",
        new=property(lambda self: "http://localhost:8123/auth/external/callback"),
    ):
        url = await flow.async_generate_authorize_url()
        aioclient_mock.post(
            "https://auth.embiodiagnostics.eu/oauth/token",
            json={"access_token": "test", "expires_in": 3600},
        )
        await implementation.async_resolve_external_data(
            {
                "code": "test-code",
                "state": {"redirect_uri": implementation.redirect_uri},
            }
        )
    params = parse_qs(urlparse(url).query)
    request = aioclient_mock.mock_calls[-1][2]
    verifier = request["code_verifier"]
    assert len(verifier) >= 43
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    assert params["code_challenge"] == [challenge]
    assert params["code_challenge_method"] == ["S256"]
    assert request["code"] == "test-code"


async def test_reauth_refuses_account_and_preserves_token(hass, coordinator):
    entry = coordinator.entry
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.context = {"source": "reauth", "entry_id": entry.entry_id}
    with patch(
        "custom_components.airbeld.config_flow.async_subject",
        return_value="auth0|other",
    ):
        result = await flow.async_oauth_create_entry({"token": {"access_token": "new"}})
    assert result["reason"] == "wrong_account"
    assert entry.data["token"]["access_token"] == "test-only"  # noqa: S105 — dummy fixture token
    with (
        patch(
            "custom_components.airbeld.config_flow.async_subject",
            return_value="auth0|one",
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await flow.async_oauth_create_entry({"token": {"access_token": "new"}})
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"]["access_token"] == "new"  # noqa: S105 — dummy fixture token


async def test_new_duplicate_flow_aborts(hass, coordinator):
    entry = coordinator.entry
    hass.config_entries.async_update_entry(
        entry, unique_id=account_id(coordinator.environment, coordinator.subject)
    )
    flow = OAuth2FlowHandler()
    flow.hass, flow.context = hass, {"source": "user"}
    flow.handler = DOMAIN
    with (
        patch(
            "custom_components.airbeld.config_flow.async_subject",
            return_value=coordinator.subject,
        ),
        pytest.raises(AbortFlow) as caught,
    ):
        await flow.async_oauth_create_entry(
            {
                "environment": coordinator.environment,
                "token": {"access_token": "test"},
            }
        )
    assert caught.value.reason == "already_configured"


async def test_old_duplicate_reverse_setup_order(hass, coordinator):
    oldest = coordinator.entry
    hass.config_entries.async_update_entry(
        oldest,
        version=1,
        data={key: value for key, value in oldest.data.items() if key != "sub"},
    )
    later = MockConfigEntry(domain=DOMAIN, version=1, data=dict(oldest.data))
    later.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        later, data={**later.data, "token": {**later.data["token"], "expires_at": 1}}
    )
    object.__setattr__(later, "created_at", oldest.created_at + timedelta(seconds=1))
    object.__setattr__(oldest, "state", ConfigEntryState.SETUP_IN_PROGRESS)
    _, rows = seed(hass, oldest, 42, ["temperature"])
    with (
        patch(
            "custom_components.airbeld.get_async_client",
            return_value=coordinator.test_shared,
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ) as forward,
        patch(
            "custom_components.airbeld.async_legacy_subject", return_value="auth0|one"
        ) as subject,
        patch.object(
            oauth.OAuth2Session, "async_ensure_token_valid", new=AsyncMock()
        ) as validate,
    ):
        assert not await async_setup_entry(hass, later)
        assert forward.await_count == 0
        assert validate.await_count == 0
        assert len(coordinator.test_requests) == 3
        assert [request.url.path for request in coordinator.test_requests] == [
            "/api/v2/devices/",
            "/api/v2/readings/batch/",
            "/api/v2/devices/device-42/",
        ]
        assert (
            er.async_get(hass).async_get(rows[0].entity_id).unique_id
            == rows[0].unique_id
        )
        assert await async_setup_entry(hass, oldest)
        assert forward.await_count == 1
        assert subject.await_count == 2
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"duplicate_{later.entry_id}")


@pytest.mark.parametrize(
    ("second_environment", "second_sub"),
    [("https://backend.invalid", "auth0|two"), ("https://other.invalid", "auth0|one")],
)
async def test_copy_per_account_concurrent_setup_and_isolation(
    hass, coordinator, second_environment, second_sub
):
    one = coordinator.entry
    two = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={**one.data, "environment": second_environment, "sub": second_sub},
    )
    two.add_to_hass(hass)
    object.__setattr__(one, "state", ConfigEntryState.SETUP_IN_PROGRESS)
    object.__setattr__(two, "state", ConfigEntryState.SETUP_IN_PROGRESS)
    transport = coordinator.test_shared._transport

    def respond(request):
        rewritten = httpx.Request(
            request.method,
            str(request.url).replace("other.invalid", "backend.invalid"),
            headers=request.headers,
            content=request.content,
        )
        return transport.handler(rewritten)

    coordinator.test_shared._transport = httpx.MockTransport(respond)
    with (
        patch(
            "custom_components.airbeld.get_async_client",
            return_value=coordinator.test_shared,
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ),
    ):
        assert await asyncio.gather(
            async_setup_entry(hass, one), async_setup_entry(hass, two)
        ) == [True, True]
    entities_one, entities_two = [], []
    await setup_sensors(hass, one, lambda items, **kw: entities_one.extend(items))
    await setup_sensors(hass, two, lambda items, **kw: entities_two.extend(items))
    assert entities_one[0].unique_id != entities_two[0].unique_id
    assert entities_one[0].coordinator is one.runtime_data
    assert entities_two[0].coordinator is two.runtime_data
    devices = dr.async_get(hass)
    device_rows = []
    for entry, sensors in [(one, entities_one), (two, entities_two)]:
        device_rows.append(
            devices.async_get_or_create(
                config_entry_id=entry.entry_id, **sensors[0].device_info
            )
        )
    assert len(devices.devices) == 2
    assert device_rows[0].identifiers != device_rows[1].identifiers
    await two.runtime_data.async_refresh()
    assert entities_two[0].native_value == 23.5
    one.runtime_data.async_set_updated_data({})
    assert not entities_one[0].available
    assert entities_two[0].native_value == 23.5
    assert entities_two[0].available
    with patch.object(
        hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=True)
    ):
        assert await async_unload_entry(hass, one)
    assert not coordinator.test_shared.is_closed
    assert entities_two[0].coordinator is two.runtime_data
    devices.async_remove_device(device_rows[0].id)
    assert devices.async_get(device_rows[1].id) == device_rows[1]


async def test_identity_uses_authenticated_userinfo(hass, aioclient_mock):
    url = "https://auth.embiodiagnostics.eu/userinfo"
    aioclient_mock.get(url, json={"sub": "auth0|verified"})
    assert await async_subject(hass, "test-only") == "auth0|verified"
    assert aioclient_mock.mock_calls[-1][3]["Authorization"] == "Bearer test-only"
    aioclient_mock.clear_requests()
    aioclient_mock.get(url, status=401)
    with pytest.raises(ConfigEntryAuthFailed):
        await async_subject(hass, "invalid")


async def test_unresolved_repair_removes_only_confirmed_entry_rows(hass, coordinator):
    entry = coordinator.entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "migration_pending": True}
    )
    mapped_device, mapped_rows = seed(hass, entry, 42, ["temperature"])
    missing_device, missing_rows = seed(hass, entry, 99, ["temperature"])
    sibling = MockConfigEntry(
        domain=DOMAIN, version=2, data={**entry.data, "sub": "auth0|two"}
    )
    sibling.add_to_hass(hass)
    # Another entry's ordinary registry row is not a deletion target.
    sibling_row = er.async_get(hass).async_get_or_create(
        "sensor", DOMAIN, "sibling_99_temperature", config_entry=sibling
    )
    await async_complete_migration(hass, entry, coordinator)
    assert (await async_get_config_entry_diagnostics(hass, entry))[
        "unresolved_legacy"
    ] == ["99"]
    flow = await async_create_fix_flow(
        hass, f"unresolved_{entry.entry_id}", {"entry_id": entry.entry_id}
    )
    flow.hass, flow.handler, flow.issue_id = (
        hass,
        DOMAIN,
        f"unresolved_{entry.entry_id}",
    )
    flow.data = {"entry_id": entry.entry_id}
    assert (await flow.async_step_confirm())["type"] == "form"
    assert er.async_get(hass).async_get(missing_rows[0].entity_id)
    assert (await flow.async_step_confirm({}))["type"] == "create_entry"
    assert er.async_get(hass).async_get(missing_rows[0].entity_id) is None
    assert dr.async_get(hass).async_get(missing_device.id) is None
    assert er.async_get(hass).async_get(mapped_rows[0].entity_id)
    assert dr.async_get(hass).async_get(mapped_device.id)
    assert er.async_get(hass).async_get(sibling_row.entity_id)
    assert entry.data["unresolved_legacy"] == []


async def test_migration_durable_save_order_and_second_device_resume(hass, coordinator):
    entry = coordinator.entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "migration_pending": True}
    )
    seed(hass, entry, 42, ["temperature"])
    seed(hass, entry, 84, ["temperature"])
    coordinator.data["device-84"] = coordinator.data["device-42"]
    pairs = [
        SimpleNamespace(id=42, uid="device-42"),
        SimpleNamespace(id=84, uid="device-84"),
    ]
    events = []

    async def save_entry(_data):
        events.append(("entry", dict(entry.data)))

    async def save_devices(_data):
        events.append(("devices", None))

    async def save_entities(_data):
        events.append(("entities", None))

    with (
        patch.object(
            coordinator.client, "resolve_legacy_device_ids", return_value=pairs
        ),
        patch.object(hass.config_entries._store, "async_save", side_effect=save_entry),
        patch.object(dr.async_get(hass)._store, "async_save", side_effect=save_devices),
        patch.object(
            er.async_get(hass)._store, "async_save", side_effect=save_entities
        ),
    ):
        await async_complete_migration(hass, entry, coordinator)
    assert [kind for kind, _ in events] == [
        "entry",
        "devices",
        "entities",
        "entry",
        "devices",
        "entities",
        "entry",
        "entry",
    ]
    assert not events[0][1].get("legacy_migration_done")
    assert events[3][1]["legacy_migration_done"] == {"42": "device-42"}
    assert events[6][1]["legacy_migration_done"] == {
        "42": "device-42",
        "84": "device-84",
    }
    assert not events[-1][1]["migration_pending"]


async def test_legacy_identity_verifies_expired_signature_and_reauth(
    hass, coordinator, aioclient_mock
):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key(), as_dict=True)
    public["kid"] = "legacy-test"
    aioclient_mock.get(
        "https://auth.embiodiagnostics.eu/.well-known/jwks.json",
        json={"keys": [public]},
    )
    claims = {
        "sub": "auth0|one",
        "iss": "https://auth.embiodiagnostics.eu/",
        "aud": "https://airbeld-drf/api",
        "exp": 1,
    }
    token = jwt.encode(
        claims, private, algorithm="RS256", headers={"kid": "legacy-test"}
    )
    assert await async_legacy_subject(hass, token) == "auth0|one"
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(
        {**claims, "sub": "auth0|other"},
        attacker,
        algorithm="RS256",
        headers={"kid": "legacy-test"},
    )
    with pytest.raises(ConfigEntryAuthFailed):
        await async_legacy_subject(hass, forged)
    entry = coordinator.entry
    hass.config_entries.async_update_entry(
        entry,
        data={key: value for key, value in entry.data.items() if key != "sub"}
        | {
            "token": {"access_token": token, "expires_at": 1},
            "migration_pending": True,
        },
    )
    flow = OAuth2FlowHandler()
    flow.hass, flow.context = hass, {"source": "reauth", "entry_id": entry.entry_id}
    with patch(
        "custom_components.airbeld.config_flow.async_subject",
        return_value="auth0|other",
    ):
        assert (
            await flow.async_oauth_create_entry({"token": {"access_token": "new"}})
        )["reason"] == "wrong_account"
    with (
        patch(
            "custom_components.airbeld.config_flow.async_subject",
            return_value="auth0|one",
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        assert (
            await flow.async_oauth_create_entry({"token": {"access_token": "new"}})
        )["reason"] == "reauth_successful"
    assert entry.data["sub"] == "auth0|one"
    _, rows = seed(hass, entry, 42, ["temperature"])
    await async_complete_migration(hass, entry, coordinator)
    assert er.async_get(hass).async_get(
        rows[0].entity_id
    ).unique_id == sensor_unique_id(
        coordinator.environment, coordinator.subject, "device-42", "temperature"
    )


async def test_migration_keeps_recorded_history(history_recorder, hass, coordinator):
    await history_recorder(hass)
    entry = coordinator.entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "migration_pending": True}
    )
    _, rows = seed(hass, entry, 42, ["temperature"])
    start = dt_util.utcnow() - timedelta(seconds=1)
    hass.states.async_set(rows[0].entity_id, "19.0")
    await hass.async_block_till_done()
    await async_recorder_block_till_done(hass)
    await async_complete_migration(hass, entry, coordinator)
    history = await hass.async_add_executor_job(
        get_significant_states, hass, start, None, [rows[0].entity_id]
    )
    assert history[rows[0].entity_id][0].state == "19.0"
    assert (
        er.async_get(hass).async_get(rows[0].entity_id).entity_id == rows[0].entity_id
    )
