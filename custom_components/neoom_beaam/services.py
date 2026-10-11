"""Actions (services) for the neoom BEAAM integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .api import BeaamError
from .const import (
    ATTR_DEVICE_ID,
    ATTR_KEY,
    ATTR_STATES,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_PUSH_STATES,
    SERVICE_SEND_COMMAND,
    SERVICE_UPDATE_SETTING,
)
from .coordinator import BeaamCoordinator

KEY_VALUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_KEY): cv.string,
        vol.Required(ATTR_VALUE): vol.Any(bool, int, float, str, list),
    }
)
PUSH_STATES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_STATES): vol.All(dict, vol.Length(min=1)),
    }
)


def _resolve(hass: HomeAssistant, device_id: str) -> tuple[BeaamCoordinator, str]:
    """Map a HA device to (coordinator, BEAAM thing id)."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(f"Unknown device {device_id}")
    thing_id = next((i[1] for i in device.identifiers if i[0] == DOMAIN), None)
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            continue
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("The BEAAM integration is not loaded")
        coordinator: BeaamCoordinator = entry.runtime_data
        if thing_id is None or thing_id not in coordinator.things:
            raise ServiceValidationError(
                "Select a device connected to the BEAAM (battery, meter, ...), "
                "not the BEAAM itself"
            )
        return coordinator, thing_id
    raise ServiceValidationError(f"Device {device_id} does not belong to a BEAAM")


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions."""

    async def send_command(call: ServiceCall) -> None:
        coordinator, thing_id = _resolve(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_send_command(
            thing_id, call.data[ATTR_KEY], call.data[ATTR_VALUE]
        )
        await coordinator.async_request_refresh()

    async def update_setting(call: ServiceCall) -> None:
        coordinator, thing_id = _resolve(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_update_setting(
            thing_id, call.data[ATTR_KEY], call.data[ATTR_VALUE]
        )

    async def push_states(call: ServiceCall) -> None:
        coordinator, thing_id = _resolve(hass, call.data[ATTR_DEVICE_ID])
        states: dict[str, Any] = call.data[ATTR_STATES]
        try:
            await coordinator.client.push_states(
                thing_id, [{"key": k, "value": v} for k, v in states.items()]
            )
        except BeaamError as err:
            raise HomeAssistantError(f"Pushing states to BEAAM failed: {err}") from err

    hass.services.async_register(DOMAIN, SERVICE_SEND_COMMAND, send_command, KEY_VALUE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_SETTING, update_setting, KEY_VALUE_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_PUSH_STATES, push_states, PUSH_STATES_SCHEMA)
