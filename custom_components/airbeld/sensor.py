"""Support for Airbeld sensors."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_DEVICE_CLASSES
from .coordinator import AirbeldDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airbeld sensors."""
    coordinator: AirbeldDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Create sensors dynamically for each device and ALL available metrics
    for device_id, device_data in coordinator.data.items():
        device = device_data["device"]
        telemetry = device_data["telemetry"]

        # Create a sensor for each metric returned by the SDK
        for sensor_name, metric_data in telemetry.items():
            entities.append(
                AirbeldSensor(
                    coordinator,
                    device_id,
                    device,
                    sensor_name,
                    metric_data,
                )
            )

    async_add_entities(entities, False)


class AirbeldSensor(CoordinatorEntity[AirbeldDataUpdateCoordinator], SensorEntity):
    """Representation of an Airbeld sensor."""

    def __init__(
        self,
        coordinator: AirbeldDataUpdateCoordinator,
        device_id: str,
        device: Any,
        sensor_name: str,
        metric_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._device_id = device_id
        self._device = device
        self._sensor_name = sensor_name

        # Entity attributes - use SDK's display_name
        self._attr_unique_id = f"airbeld_{device_id}_{sensor_name}"
        self._attr_name = f"{device.name} {metric_data['display_name']}"

        # Sensor configuration from SDK metadata
        # For AQI sensors, HA expects None instead of "-"
        unit = metric_data["unit"]
        if unit == "-":
            unit = None
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = SENSOR_DEVICE_CLASSES.get(sensor_name)
        self._attr_state_class = SensorStateClass.MEASUREMENT

        # Store description as extra state attribute if available
        if metric_data.get("description"):
            self._attr_extra_state_attributes = {
                "description": metric_data["description"]
            }

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device.display_name or self._device.name,
            "manufacturer": "Airbeld",
            "model": getattr(self._device, "type", None),
            "sw_version": None,
        }

    @property
    def native_value(self) -> float | None:
        """Return the native value of the sensor."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None

        telemetry = device_data.get("telemetry", {})
        metric_data = telemetry.get(self._sensor_name)

        if metric_data and isinstance(metric_data, dict):
            return metric_data.get("value")

        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        # Check if device data is available
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False

        # Check device status if available (DeviceReadings doesn't have status field)
        # If we successfully fetched data, consider the device online
        device = device_data.get("device")
        if device and hasattr(device, "status"):
            return device.status != "offline"

        # Default to available if we have data (async_get_all_readings_by_date only returns online devices)
        return True