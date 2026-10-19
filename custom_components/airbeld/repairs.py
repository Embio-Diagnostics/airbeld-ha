"""Explicit user removal of unresolved legacy rows only."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.components.repairs import RepairsFlowResult
    from homeassistant.core import HomeAssistant
from .migration import LEGACY_ENTITY


class UnresolvedLegacyRepairFlow(ConfirmRepairFlow):
    """Remove only the owning entry's unresolved rows on user confirmation."""

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Show confirmation before removing the explicitly unresolved rows."""
        if user_input is None:
            return await super().async_step_confirm()
        entry = self.hass.config_entries.async_get_entry(self.data["entry_id"])
        if entry:
            ids = set(entry.data.get("unresolved_legacy", []))
            entities = er.async_get(self.hass)
            for row in er.async_entries_for_config_entry(entities, entry.entry_id):
                match = LEGACY_ENTITY.fullmatch(row.unique_id)
                if row.platform == DOMAIN and match and match[1] in ids:
                    entities.async_remove(row.entity_id)
            devices = dr.async_get(self.hass)
            for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
                if any(
                    domain == DOMAIN and str(value) in ids
                    for domain, value in device.identifiers
                ):
                    devices.async_remove_device(device.id)
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, "unresolved_legacy": []}
            )
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    _hass: HomeAssistant, _issue_id: str, _data: dict[str, Any] | None
) -> ConfirmRepairFlow:
    """Create the repair flow; HA supplies issue data and context afterwards."""
    return UnresolvedLegacyRepairFlow()
