"""DataUpdateCoordinator for Airbeld."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import config_entry_oauth2_flow

    from airbeld import AirbeldClient

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AirbeldDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Airbeld API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AirbeldClient,
        session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize."""
        self.client = client
        self.session = session
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Ensure token is still valid and refresh if needed
            await self.session.async_ensure_token_valid()

            # Update client with potentially refreshed token
            current_token = self.session.token[CONF_ACCESS_TOKEN]
            self.client.set_token(current_token)

            # Fetch all devices with latest readings in a single API call
            device_readings_list = await self.client.async_get_all_readings_by_date()
            _LOGGER.debug("Fetched data for %d devices", len(device_readings_list))

        except Exception as err:
            # Enhanced error logging for API issues
            error_details = str(err)
            if hasattr(err, "status_code"):
                error_details = f"HTTP {err.status_code}: {error_details}"
            if hasattr(err, "response_body"):
                error_details = f"{error_details} | Response: {err.response_body}"

            _LOGGER.exception("Error communicating with Airbeld API: %s", error_details)

            error_msg = f"Error communicating with API: {err}"
            raise UpdateFailed(error_msg) from err

        # Process each device's readings
        data = {}
        for device_reading in device_readings_list:
            # DeviceReadings object with id, name, sensors, etc.
            device_data = {
                "device": device_reading,
                "telemetry": {},
            }

            # Store full metric objects with metadata from SDK
            for sensor_name, metric in device_reading.sensors.items():
                try:
                    latest_value = device_reading.get_latest_value(sensor_name)
                    if latest_value is not None:
                        # Store both the value and the full metric for metadata
                        device_data["telemetry"][sensor_name] = {
                            "value": latest_value,
                            "display_name": metric.display_name or metric.name,
                            "unit": metric.unit,
                            "description": metric.description,
                        }
                except Exception:  # noqa: BLE001
                    # Intentionally broad - don't let one sensor error break all updates
                    _LOGGER.debug(
                        "Failed to process %s sensor on device %s",
                        sensor_name,
                        device_reading.id,
                        exc_info=True,
                    )

            data[device_reading.id] = device_data

        return data
