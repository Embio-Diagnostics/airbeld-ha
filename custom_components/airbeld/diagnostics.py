"""Diagnostics support for Airbeld."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # Get coordinator data
    data = coordinator.data

    # Redact sensitive information
    diagnostics_data = {
        "entry": {
            "title": entry.title,
            "data": {key: entry.data[key] for key in ("environment", "sub", "token")},
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception)
            if coordinator.last_exception
            else None,
            "update_interval": str(coordinator.update_interval),
        },
        "devices": {},
        "unresolved_legacy": entry.data.get("unresolved_legacy", []),
    }

    # Add device information (redact sensitive fields)
    for device_id, device_data in data.items():
        device = device_data["device"]
        telemetry = device_data["telemetry"]

        diagnostics_data["devices"][device_id] = {
            "device_info": {
                "uid": device.uid,
                "name": device.name,
                "status": getattr(device, "status", "unknown"),
                "model": getattr(device, "model", None),
                "firmware_version": getattr(device, "firmware_version", None),
                # Add other non-sensitive device attributes
            },
            "telemetry_sensors": list(telemetry.keys()),
            # Include sample values but not full history
            "telemetry_sample": dict(telemetry.items()) if telemetry else {},
        }

    return async_redact_data(
        diagnostics_data, {"access_token", "refresh_token", "id_token", "sub", "token"}
    )
