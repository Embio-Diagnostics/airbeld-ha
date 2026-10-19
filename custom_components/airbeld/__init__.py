"""The airbeld integration, with entry-owned v2 runtime data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import ClientResponseError
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.httpx_client import get_async_client

from airbeld import AirbeldClient

from .config_flow import async_register_implementation
from .const import DOMAIN
from .coordinator import AirbeldDataUpdateCoordinator
from .identity import account_id, async_legacy_subject, environment
from .migration import async_complete_migration

PLATFORMS = [Platform.SENSOR]
ENTRY_VERSION = 2
AUTH_SERVICE_UNAVAILABLE = "Token service unavailable"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Both startup and flow registration use the same real PKCE implementation."""
    await async_register_implementation(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Bump immediately; registry completion waits for authenticated inventory."""
    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry,
            version=2,
            data={
                **entry.data,
                "environment": environment(entry.data),
                "migration_pending": True,
            },
        )
    return entry.version == ENTRY_VERSION


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the winning account entry and finish its registry migration."""
    await async_register_implementation(hass)
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    env = environment(entry.data)
    # Resolve original signed identities before token refresh/reauth can replace
    # credentials. Selection and duplicate refusal below happen without an await.
    for candidate in hass.config_entries.async_entries(DOMAIN):
        if environment(candidate.data) == env and not candidate.data.get("sub"):
            sub = await async_legacy_subject(
                hass, candidate.data["token"]["access_token"]
            )
            hass.config_entries.async_update_entry(
                candidate, data={**candidate.data, "environment": env, "sub": sub}
            )
    # Capture all legacy subjects before assigning any entry identity. No await
    # occurs between winner selection and the duplicate return, so concurrent
    # setup cannot let a later duplicate poll or rewrite the winner's rows.
    sub = entry.data["sub"]
    identity = account_id(env, sub)
    peers = [
        candidate
        for candidate in hass.config_entries.async_entries(DOMAIN)
        if environment(candidate.data) == env and candidate.data.get("sub") == sub
    ]
    winner = min(
        peers, key=lambda candidate: (candidate.created_at, candidate.entry_id)
    )
    if winner is not entry:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"duplicate_{entry.entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="duplicate_account",
        )
        return False
    try:
        await session.async_ensure_token_valid()
    except ConfigEntryAuthFailed:
        raise
    except ClientResponseError as err:
        if err.status in (400, 401, 403):
            raise ConfigEntryAuthFailed(AUTH_SERVICE_UNAVAILABLE) from err
        raise ConfigEntryNotReady(AUTH_SERVICE_UNAVAILABLE) from err
    except Exception as err:
        raise ConfigEntryNotReady(AUTH_SERVICE_UNAVAILABLE) from err
    hass.config_entries.async_update_entry(entry, unique_id=identity)
    ir.async_delete_issue(hass, DOMAIN, f"duplicate_{entry.entry_id}")
    client = AirbeldClient(
        token=session.token["access_token"], base_url=env, client=get_async_client(hass)
    )
    coordinator = AirbeldDataUpdateCoordinator(hass, client, session, entry)
    await coordinator.async_config_entry_first_refresh()
    await async_complete_migration(hass, entry, coordinator)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms without closing HA's injected shared HTTP client."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.sensor_descriptors.clear()
    return unloaded
