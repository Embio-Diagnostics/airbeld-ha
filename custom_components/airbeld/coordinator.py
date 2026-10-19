"""DataUpdateCoordinator for the v2 inventory and readings facade."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from aiohttp import ClientResponseError
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from airbeld.exceptions import AirbeldError, AuthError

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
AUTH_REQUIRED = "Sign in to airbeld again"
API_UNAVAILABLE = "Error communicating with API"

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
