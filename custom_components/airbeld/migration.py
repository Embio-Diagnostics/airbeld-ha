"""Resumable in-place registry upgrade; entity ids and recorder keys never change."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from airbeld.exceptions import AirbeldError, AuthError

from .const import DOMAIN
from .identity import device_identifier, sensor_unique_id

_LOGGER = logging.getLogger(__name__)
LEGACY_ENTITY = re.compile(r"^airbeld_(\d+)_(.+)$")
AUTH_REQUIRED = "Sign in to complete the registry upgrade"
BACKEND_UNAVAILABLE = "Registry upgrade backend unavailable"
DEVICE_WRITE_FAILED = "Device rewrite postcondition failed"
SOURCE_MISSING = "Registry source row missing during upgrade"
ENTITY_WRITE_FAILED = "Registry rewrite postcondition failed"
ASSOCIATION_FAILED = "Device association postcondition failed"

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import AirbeldDataUpdateCoordinator


async def async_complete_migration(  # noqa: PLR0912, PLR0915 — keep journal/write/postcondition ordering together
    hass: HomeAssistant, entry: ConfigEntry, coordinator: AirbeldDataUpdateCoordinator
) -> None:
    """Persist a marker only after all rows for one pk have been checked."""
    if not entry.data.get("migration_pending"):
        return
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    rows = er.async_entries_for_config_entry(entities, entry.entry_id)
    journal = dict(entry.data.get("legacy_migration_rows", {}))
    grouped = {}
    for row in rows:
        if row.platform == DOMAIN and (match := LEGACY_ENTITY.fullmatch(row.unique_id)):
            grouped.setdefault(match[1], []).append((row, match[2]))
    for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and str(identifier).isdigit():
                grouped.setdefault(str(identifier), [])
    for pk, items in grouped.items():
        journal.setdefault(
            pk,
            [
                {"entity_id": row.entity_id, "sensor": key, "unique_id": row.unique_id}
                for row, key in items
            ],
        )
    # Capture the source rows before rewriting them: after interruption an
    # ordinary unique_id no longer contains its pk, but the journal still does.
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "legacy_migration_rows": journal}
    )
    # HA delays registry/config-entry saves. Flush the source journal before any
    # rewrite, then registries before completion markers: a restart must never
    # observe a done marker for a rewrite that exists only in memory.
    await hass.config_entries._store.async_save(hass.config_entries._data_to_save())  # noqa: SLF001 — HA has no public immediate config-entry flush
    done = dict(entry.data.get("legacy_migration_done", {}))
    pending = sorted(set(journal) - set(done))
    try:
        pairs = (
            await coordinator.client.resolve_legacy_device_ids(
                [int(pk) for pk in pending]
            )
            if pending
            else []
        )
    except AuthError as err:
        raise ConfigEntryAuthFailed(AUTH_REQUIRED) from err
    except AirbeldError as err:
        raise ConfigEntryNotReady(BACKEND_UNAVAILABLE) from err
    mapping = {str(pair.id): pair.uid for pair in pairs}
    unresolved = set(entry.data.get("unresolved_legacy", []))
    voc_nox = dict(entry.data.get("legacy_voc_nox", {}))
    env, sub = coordinator.environment, coordinator.subject
    for pk in pending:
        uid = mapping.get(pk)
        if uid not in coordinator.data:
            unresolved.add(pk)
            _LOGGER.warning("Legacy registry id %s is unresolved; left untouched", pk)
            continue
        target = (DOMAIN, device_identifier(env, sub, uid))
        old_devices = [
            device
            for device in dr.async_entries_for_config_entry(devices, entry.entry_id)
            if (DOMAIN, pk) in device.identifiers
            or (DOMAIN, int(pk)) in device.identifiers
        ]
        for device in old_devices:
            identifiers = {
                (domain, value)
                for domain, value in device.identifiers
                if not (domain == DOMAIN and str(value) == pk)
            } | {target}
            devices.async_update_device(device.id, new_identifiers=identifiers)
            if devices.async_get(device.id).identifiers != identifiers:
                raise ConfigEntryNotReady(DEVICE_WRITE_FAILED)
        for source in journal[pk]:
            current = entities.async_get(source["entity_id"])
            if current is None or current.config_entry_id != entry.entry_id:
                raise ConfigEntryNotReady(SOURCE_MISSING)
            key = source["sensor"]
            if key in ("voc", "nox"):
                voc_nox[current.entity_id] = {
                    "uid": uid,
                    "unique_id": source["unique_id"],
                    "sensor": key,
                }
                expected = source["unique_id"]
            else:
                expected = sensor_unique_id(env, sub, uid, key)
                if current.unique_id != expected:
                    entities.async_update_entity(
                        current.entity_id, new_unique_id=expected
                    )
            if entities.async_get(current.entity_id).unique_id != expected:
                raise ConfigEntryNotReady(ENTITY_WRITE_FAILED)
            if (
                current.device_id
                and target not in devices.async_get(current.device_id).identifiers
            ):
                raise ConfigEntryNotReady(ASSOCIATION_FAILED)
        done[pk] = uid
        unresolved.discard(pk)
        await devices._store.async_save(devices._data_to_save())  # noqa: SLF001 — durability barrier before the done marker
        await entities._store.async_save(entities._data_to_save())  # noqa: SLF001 — durability barrier before the done marker
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                "legacy_migration_done": dict(done),
                "legacy_voc_nox": dict(voc_nox),
                "unresolved_legacy": sorted(unresolved),
            },
        )
        await hass.config_entries._store.async_save(hass.config_entries._data_to_save())  # noqa: SLF001 — persist this id's completion after its registries
        _LOGGER.info("Migrated legacy registry id %s in place", pk)
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "legacy_migration_done": done,
            "legacy_voc_nox": voc_nox,
            "unresolved_legacy": sorted(unresolved),
            "migration_pending": False,
        },
    )
    await hass.config_entries._store.async_save(hass.config_entries._data_to_save())  # noqa: SLF001 — persist overall completion after all per-id barriers
    if unresolved:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"unresolved_{entry.entry_id}",
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="unresolved_legacy",
            translation_placeholders={"ids": ", ".join(sorted(unresolved))},
            data={"entry_id": entry.entry_id},
        )
