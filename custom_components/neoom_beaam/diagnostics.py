"""Diagnostics for the neoom BEAAM integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import BeaamConfigEntry

TO_REDACT = {CONF_API_KEY, "latitude", "longitude", "SERIAL_NUMBER"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BeaamConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "site_configuration": async_redact_data(coordinator.site_config, TO_REDACT),
        "setting_things": sorted(coordinator.setting_things),
        "states": {
            dp_id: {"key": dp.key, "value": data.states.get(dp_id)}
            for dp_id, dp in coordinator.data_points.items()
            if dp.key != "SERIAL_NUMBER"
        },
        "settings": data.settings,
        "unavailable_things": sorted(data.unavailable_things),
    }
