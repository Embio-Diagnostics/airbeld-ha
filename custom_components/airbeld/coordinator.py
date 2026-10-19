"""DataUpdateCoordinator for the v2 inventory and readings facade."""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from aiohttp import ClientResponseError
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from airbeld.exceptions import AirbeldError, AuthError

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .identity import device_identifier

_LOGGER = logging.getLogger(__name__)
AUTH_REQUIRED = "Sign in to airbeld™ again"
API_UNAVAILABLE = "Error communicating with API"
ABSENCE_LIMIT = 3
DEVICE_IDENTITY_PARTS = 3

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

    from airbeld import AirbeldClient


class AirbeldDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """One account's inventory and telemetry; no cross-entry cache."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AirbeldClient,
        session: OAuth2Session,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the runtime for exactly one account and environment."""
        self.client = client
        self.session = session
        self.entry = entry
        self.environment = entry.data["environment"]
        self.subject = entry.data["sub"]
        self.inventory: dict[str, Any] = {}
        self.absences: dict[str, int] = {}
        self.removal_generation: dict[str, int] = {}
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch v2 inventory and its latest readings through the real SDK."""
        try:
            await self.session.async_ensure_token_valid()
            self.client.set_token(self.session.token["access_token"])
            devices = await self.client.list_devices()
            # The SDK parses the entire unpaginated array before returning. A
            # contract/fetch failure above cannot advance any absence counters.
            self._reconcile_inventory(devices)
            readings = await self.client.latest_readings(
                [device.uid for device in devices]
            )
        except AuthError as err:
            raise ConfigEntryAuthFailed(AUTH_REQUIRED) from err
        except AirbeldError as err:
            raise UpdateFailed(API_UNAVAILABLE) from err
        except ClientResponseError as err:
            if err.status in (400, 401, 403):
                raise ConfigEntryAuthFailed(AUTH_REQUIRED) from err
            raise UpdateFailed(API_UNAVAILABLE) from err

        data = {device.uid: {"device": device, "telemetry": {}} for device in devices}
        for reading in readings:
            if reading.uid not in data or reading.status != "ok":
                continue
            for key, metric in (reading.sensors or {}).items():
                samples = [
                    sample for sample in metric.values if sample.value is not None
                ]
                if samples:
                    data[reading.uid]["telemetry"][key] = {
                        "value": max(
                            samples, key=lambda sample: sample.timestamp
                        ).value,
                        "display_name": metric.display_name or metric.name,
                        "unit": metric.unit,
                        "description": metric.description,
                    }
        return data

    def _reconcile_inventory(self, devices: list[Any]) -> None:  # noqa: PLR0912 — keep inventory counting and entry-scoped cleanup together
        """Count complete inventories independently of telemetry failures."""
        self.inventory = {device.uid: device for device in devices}
        registry = dr.async_get(self.hass)
        entities = er.async_get(self.hass)
        for row in dr.async_entries_for_config_entry(registry, self.entry.entry_id):
            for domain, identifier in row.identifiers:
                if domain != DOMAIN:
                    continue
                try:
                    identity = json.loads(identifier)
                except (ValueError, TypeError):
                    continue
                if (
                    isinstance(identity, list)
                    and len(identity) == DEVICE_IDENTITY_PARTS
                    and identity[:2] == [self.environment, self.subject]
                ):
                    self.absences.setdefault(identity[2], 0)
        unresolved = set(self.entry.data.get("unresolved_legacy", []))
        for uid in set(self.absences) | set(self.inventory):
            if uid in unresolved:
                continue
            if uid in self.inventory:
                self.absences[uid] = 0
                continue
            self.absences[uid] += 1
            if self.absences[uid] < ABSENCE_LIMIT:
                continue
            identifier = (
                DOMAIN,
                device_identifier(self.environment, self.subject, uid),
            )
            row = next(
                (
                    row
                    for row in dr.async_entries_for_config_entry(
                        registry, self.entry.entry_id
                    )
                    if identifier in row.identifiers
                ),
                None,
            )
            if row:
                for entity in er.async_entries_for_config_entry(
                    entities, self.entry.entry_id
                ):
                    if entity.device_id == row.id:
                        entities.async_remove(entity.entity_id)
                registry.async_remove_device(row.id)
            del self.absences[uid]
            self.removal_generation[uid] = self.removal_generation.get(uid, 0) + 1
        # Initial legacy setup must let migration rewrite the old row first.
        # Subsequent inventories create rows even when telemetry repeatedly fails
        # (the standard coordinator does not notify listeners on every failure).
        if getattr(
            self.entry, "runtime_data", None
        ) is self and not self.entry.data.get("migration_pending"):
            for uid, device in self.inventory.items():
                registry.async_get_or_create(
                    config_entry_id=self.entry.entry_id,
                    identifiers={
                        (DOMAIN, device_identifier(self.environment, self.subject, uid))
                    },
                    name=device.display_name or device.name,
                    manufacturer="airbeld™",
                    model=device.type or device.name,
                )
