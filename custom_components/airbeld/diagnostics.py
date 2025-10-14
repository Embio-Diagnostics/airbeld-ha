"""Diagnostics support for Airbeld."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Get coordinator data
    data = coordinator.data
    
    # Redact sensitive information
    diagnostics_data = {
        "entry": {
            "title": entry.title,
            "data": {
                # Redact access token
                "access_token": "**REDACTED**"
            },
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
            "update_interval": str(coordinator.update_interval),
        },
        "devices": {},
    }
    
    # Add device information (redact sensitive fields)
    for device_id, device_data in data.items():
        device = device_data["device"]
        telemetry = device_data["telemetry"]
        
        diagnostics_data["devices"][device_id] = {
            "device_info": {
                "id": device.id,
                "name": device.name,
                "status": getattr(device, "status", "unknown"),
                "model": getattr(device, "model", None),
                "firmware_version": getattr(device, "firmware_version", None),
                # Add other non-sensitive device attributes
            },
            "telemetry_sensors": list(telemetry.keys()),
            "telemetry_sample": {
                # Include sample values but not full history
                sensor_type: value 
                for sensor_type, value in telemetry.items()
            } if telemetry else {},
        }
    
    return diagnostics_data