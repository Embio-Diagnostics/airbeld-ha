"""Support for Airbeld sensors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSOR_DEVICE_CLASSES
from .coordinator import AirbeldDataUpdateCoordinator
from .identity import device_identifier, sensor_unique_id

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airbeld sensors."""
    coordinator: AirbeldDataUpdateCoordinator = config_entry.runtime_data

    registry = er.async_get(hass)
    for entity_id, legacy in config_entry.data.get("legacy_voc_nox", {}).items():
        row = registry.async_get(entity_id)
        if (
            row
            and row.config_entry_id == config_entry.entry_id
            and row.unique_id == legacy["unique_id"]
            and row.disabled_by is None
        ):
            registry.async_update_entity(
                entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
            )
    added: set[tuple[str, str]] = set()
    generations: dict[str, int] = {}

    @callback
    def discover() -> None:
        """Discover new metrics from the coordinator listener without another timer."""
        for uid, device in coordinator.inventory.items():
            dr.async_get(hass).async_get_or_create(
                config_entry_id=config_entry.entry_id,
                identifiers={
                    (
                        DOMAIN,
                        device_identifier(
                            coordinator.environment, coordinator.subject, uid
                        ),
                    )
                },
                name=device.display_name or device.name,
                manufacturer="airbeld™",
                model=device.type or device.name,
            )
        for uid, generation in coordinator.removal_generation.items():
            if generations.get(uid, 0) != generation:
                added.difference_update({item for item in added if item[0] == uid})
                generations[uid] = generation
        entities = []
        for device_id, device_data in (coordinator.data or {}).items():
            if device_id not in coordinator.inventory:
                continue
            for sensor_name, metric_data in device_data["telemetry"].items():
                identity = (device_id, sensor_name)
                if identity in added:
                    continue
                added.add(identity)
                entities.append(
                    AirbeldSensor(
                        coordinator,
                        device_id,
                        device_data["device"],
                        sensor_name,
                        metric_data,
                    )
                )
        if entities:
            async_add_entities(entities, update_before_add=False)

    config_entry.async_on_unload(coordinator.async_add_listener(discover))
    discover()


class AirbeldSensor(CoordinatorEntity[AirbeldDataUpdateCoordinator], SensorEntity):
    """Representation of an Airbeld sensor."""

    _attr_has_entity_name = True

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

        key = f"{sensor_name}_index" if sensor_name in ("voc", "nox") else sensor_name
        self._attr_unique_id = sensor_unique_id(
            coordinator.environment, coordinator.subject, device_id, key
        )
        self._attr_translation_key = key
        # Unknown SDK metrics retain their server-provided label; known metrics
        # use HA's translated entity names (no device-name prefix in the label).
        if sensor_name not in SENSOR_DEVICE_CLASSES and sensor_name not in (
            "voc",
            "nox",
            "iaq",
            "comfort",
        ):
            self._attr_name = metric_data["display_name"]

        # Sensor configuration from SDK metadata
        # For AQI sensors, HA expects None instead of "-"
        unit = metric_data["unit"]
        if unit == "-":
            unit = None
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = SENSOR_DEVICE_CLASSES.get(sensor_name)
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        # Use display_name as the main title, device.name as the model (subtitle)
        device_name = self._device.display_name or self._device.name
        device_model = self._device.name if self._device.display_name else None

        # Add device type if available (DeviceSummary has it, DeviceReadings doesn't)
        if hasattr(self._device, "type") and self._device.type:
            device_model = f"{device_model or ''} {self._device.type}".strip()

        return {
            "identifiers": {
                (
                    DOMAIN,
                    device_identifier(
                        self.coordinator.environment,
                        self.coordinator.subject,
                        self._device_id,
                    ),
                )
            },
            "name": device_name,
            "manufacturer": "airbeld™",
            "model": device_model,
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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attributes = {}

        # Get current device data
        device_data = self.coordinator.data.get(self._device_id)
        if device_data:
            telemetry = device_data.get("telemetry", {})
            metric_data = telemetry.get(self._sensor_name)

            # Add description if available
            if (
                metric_data
                and isinstance(metric_data, dict)
                and metric_data.get("description")
            ):
                attributes["description"] = metric_data["description"]

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        # Check if device data is available
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return False

        device = device_data.get("device")
        return bool(
            device and device.status == "online" and not getattr(device, "stale", False)
        )
