"""Data update coordinator for the neoom BEAAM integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import timedelta
import logging
import time
from typing import Any, TypeVar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BeaamApiClient, BeaamAuthError, BeaamError
from .const import (
    CONFIG_CHECK_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_PARALLEL_REQUESTS,
    NAME_ACRONYMS,
)

_LOGGER = logging.getLogger(__name__)
# HA 2026.x links child devices by registry id; older versions only know via_device.
_HAS_VIA_DEVICE_ID = "via_device_id" in DeviceInfo.__annotations__
_T = TypeVar("_T")

type BeaamConfigEntry = ConfigEntry[BeaamCoordinator]


def pretty_key(key: str) -> str:
    """VOLTAGE_P1 -> 'Voltage P1', STATE_OF_CHARGE -> 'State of charge'."""
    words = key.split("_")
    out = []
    for i, word in enumerate(words):
        if word in NAME_ACRONYMS:
            out.append(word)
        elif i == 0:
            out.append(word.capitalize())
        else:
            out.append(word.lower())
    return " ".join(out)


@dataclass(frozen=True, slots=True)
class DataPointInfo:
    """Metadata of a single data point from the site configuration."""

    id: str
    key: str
    data_type: str
    unit: str | None
    controllable: bool
    thing_id: str | None  # None = site-level energy flow data point

    @classmethod
    def from_api(cls, dp_id: str, raw: dict[str, Any], thing_id: str | None) -> DataPointInfo:
        unit = raw.get("unitOfMeasure")
        return cls(
            id=dp_id,
            key=raw.get("key", dp_id),
            data_type=raw.get("dataType", ""),
            unit=None if unit in (None, "None", "") else unit,
            controllable=bool(raw.get("controllable", False)),
            thing_id=thing_id,
        )


@dataclass(slots=True)
class BeaamData:
    """One poll's worth of data."""

    states: dict[str, Any] = field(default_factory=dict)  # dataPointId -> value
    settings: dict[str, dict[str, Any]] = field(default_factory=dict)  # thing -> key -> value
    unavailable_things: set[str] = field(default_factory=set)


class BeaamCoordinator(DataUpdateCoordinator[BeaamData]):
    """Polls the BEAAM site state and the states of all things."""

    config_entry: BeaamConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: BeaamConfigEntry, client: BeaamApiClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.site_config: dict[str, Any] = {}
        self.site_id: str = ""
        self.things: dict[str, dict[str, Any]] = {}
        self.data_points: dict[str, DataPointInfo] = {}
        self.setting_things: set[str] = set()
        self.site_device_id: str | None = None
        self._config_version: Any = None
        self._last_config_check = 0.0
        self._semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

    # ── Setup ───────────────────────────────────────────────────────────────

    async def _async_setup(self) -> None:
        try:
            config = await self.client.get_site_configuration()
        except BeaamAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BeaamError as err:
            raise UpdateFailed(f"Could not read site configuration: {err}") from err
        self._apply_config(config)

        # Find out which things expose settings; others answer 404 or an empty list.
        thing_ids = list(self.things)
        results = await asyncio.gather(
            *(self._limited(self.client.get_thing_settings(t)) for t in thing_ids),
            return_exceptions=True,
        )
        for thing_id, result in zip(thing_ids, results, strict=True):
            if isinstance(result, list) and result:
                self.setting_things.add(thing_id)
            elif isinstance(result, BaseException) and not isinstance(result, BeaamError):
                raise result

    def _apply_config(self, config: dict[str, Any]) -> None:
        self.site_config = config
        self.site_id = config["siteId"]
        self._config_version = config.get("versionTimestamp")
        self._last_config_check = time.monotonic()
        self.things = config.get("things") or {}

        data_points: dict[str, DataPointInfo] = {}
        energy_flow = (config.get("energyFlow") or {}).get("dataPoints") or {}
        for dp_id, raw in energy_flow.items():
            data_points[dp_id] = DataPointInfo.from_api(dp_id, raw, None)
        for thing_id, thing in self.things.items():
            for dp_id, raw in (thing.get("dataPoints") or {}).items():
                data_points[dp_id] = DataPointInfo.from_api(dp_id, raw, thing_id)
        self.data_points = data_points

    async def _check_config_version(self) -> None:
        """Reload the entry when devices were added/removed on the BEAAM."""
        self._last_config_check = time.monotonic()
        try:
            config = await self.client.get_site_configuration()
        except BeaamError as err:
            _LOGGER.debug("Site configuration check failed: %s", err)
            return
        if config.get("versionTimestamp") != self._config_version:
            _LOGGER.info("BEAAM site configuration changed, reloading integration")
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    # ── Polling ─────────────────────────────────────────────────────────────

    async def _limited(self, coro: Awaitable[_T]) -> _T:
        async with self._semaphore:
            return await coro

    async def _async_update_data(self) -> BeaamData:
        if time.monotonic() - self._last_config_check > CONFIG_CHECK_INTERVAL.total_seconds():
            await self._check_config_version()

        data = BeaamData()
        try:
            site_states = await self.client.get_site_state()
        except BeaamAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BeaamError as err:
            raise UpdateFailed(str(err)) from err
        self._store_states(data, site_states)

        thing_ids = list(self.things)
        setting_ids = list(self.setting_things)
        results = await asyncio.gather(
            *(self._limited(self.client.get_thing_states(t)) for t in thing_ids),
            *(self._limited(self.client.get_thing_settings(t)) for t in setting_ids),
            return_exceptions=True,
        )
        state_results = results[: len(thing_ids)]
        setting_results = results[len(thing_ids) :]

        for thing_id, result in zip(thing_ids, state_results, strict=True):
            if isinstance(result, BaseException):
                self._handle_partial_error(thing_id, result)
                data.unavailable_things.add(thing_id)
                continue
            self._store_states(data, result)

        for thing_id, result in zip(setting_ids, setting_results, strict=True):
            if isinstance(result, BaseException):
                self._handle_partial_error(thing_id, result)
                continue
            data.settings[thing_id] = {
                s["key"]: s.get("value") for s in result if isinstance(s, dict) and "key" in s
            }

        return data

    @staticmethod
    def _handle_partial_error(thing_id: str, err: BaseException) -> None:
        if isinstance(err, BeaamAuthError):
            raise ConfigEntryAuthFailed(str(err)) from err
        if not isinstance(err, BeaamError):
            raise err
        _LOGGER.debug("Could not update thing %s: %s", thing_id, err)

    @staticmethod
    def _store_states(data: BeaamData, states: list[dict[str, Any]]) -> None:
        for state in states:
            if isinstance(state, dict) and "dataPointId" in state:
                data.states[state["dataPointId"]] = state.get("value")

    # ── Writing ─────────────────────────────────────────────────────────────

    async def async_send_command(
        self, thing_id: str, key: str, value: Any, dp_id: str | None = None
    ) -> None:
        """Send a command and optimistically update the state."""
        try:
            await self.client.send_commands(thing_id, [{"key": key, "value": value}])
        except BeaamError as err:
            raise HomeAssistantError(f"BEAAM command {key}={value!r} failed: {err}") from err
        if dp_id is not None and self.data is not None:
            self.data.states[dp_id] = value
            self.async_set_updated_data(self.data)

    async def async_update_setting(self, thing_id: str, key: str, value: Any) -> None:
        """Update a thing setting and optimistically update the state."""
        try:
            await self.client.update_settings(thing_id, [{"key": key, "value": value}])
        except BeaamError as err:
            raise HomeAssistantError(f"BEAAM setting {key}={value!r} failed: {err}") from err
        if self.data is not None:
            self.data.settings.setdefault(thing_id, {})[key] = value
            self.async_set_updated_data(self.data)

    # ── Devices ─────────────────────────────────────────────────────────────

    def _thing_state_by_key(self, thing_id: str, key: str) -> Any:
        if self.data is None:
            return None
        for dp in self.data_points.values():
            if dp.thing_id == thing_id and dp.key == key:
                value = self.data.states.get(dp.id)
                return None if value in (None, "") else str(value)
        return None

    def async_register_site_device(self) -> None:
        """Create the BEAAM device so things can reference it as their parent."""
        device = dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.config_entry.entry_id, **self.device_info(None)
        )
        self.site_device_id = device.id

    def device_info(self, thing_id: str | None) -> DeviceInfo:
        """Device for a thing, or the BEAAM itself when thing_id is None."""
        if thing_id is None:
            return DeviceInfo(
                identifiers={(DOMAIN, self.site_id)},
                name="BEAAM",
                manufacturer="neoom",
                model="BEAAM",
                configuration_url=f"{self.client.base_url}/api/",
            )
        thing = self.things.get(thing_id, {})
        thing_type = thing.get("type", "")
        info = DeviceInfo(
            identifiers={(DOMAIN, thing_id)},
            name=(thing.get("name") or "").strip() or pretty_key(thing_type or "Device"),
            model=pretty_key(thing_type) if thing_type else None,
            serial_number=self._thing_state_by_key(thing_id, "SERIAL_NUMBER"),
            sw_version=self._thing_state_by_key(thing_id, "FIRMWARE_VERSION"),
        )
        if _HAS_VIA_DEVICE_ID and self.site_device_id:
            info["via_device_id"] = self.site_device_id
        else:
            info["via_device"] = (DOMAIN, self.site_id)
        return info
