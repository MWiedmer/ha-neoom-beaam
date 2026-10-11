"""The neoom BEAAM (local API) integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import BeaamApiClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import BeaamConfigEntry, BeaamCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BeaamConfigEntry) -> bool:
    client = BeaamApiClient(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_API_KEY]
    )
    coordinator = BeaamCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    coordinator.async_register_site_device()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BeaamConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: BeaamConfigEntry) -> None:
    entry.runtime_data.update_interval = timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
