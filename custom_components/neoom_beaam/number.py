"""Number entities (controllable setpoints) for the neoom BEAAM integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    BATTERY_SOC_KEYS,
    DT_NUMBER,
    POWER_FACTOR_KEYS,
    SETTING_UNITS,
    SIGNED_SETPOINT_KEYS,
)
from .coordinator import BeaamConfigEntry, BeaamCoordinator, DataPointInfo
from .entity import BeaamDataPointEntity, BeaamSettingEntity, setting_items

PARALLEL_UPDATES = 1

MAX_POWER = 100_000  # W – generous upper bound for a residential/commercial site

UNIT_DEVICE_CLASS: dict[str, tuple[NumberDeviceClass, str]] = {
    "W": (NumberDeviceClass.POWER, "W"),
    "Wh": (NumberDeviceClass.ENERGY, "Wh"),
    "VA": (NumberDeviceClass.APPARENT_POWER, "VA"),
    "VAr": (NumberDeviceClass.REACTIVE_POWER, "var"),
    "A": (NumberDeviceClass.CURRENT, "A"),
    "V": (NumberDeviceClass.VOLTAGE, "V"),
    "°C": (NumberDeviceClass.TEMPERATURE, "°C"),
    "Hz": (NumberDeviceClass.FREQUENCY, "Hz"),
}


def _limits(key: str, unit: str | None) -> tuple[float, float, float]:
    """Best-guess (min, max, step); the BEAAM does not publish ranges."""
    if unit == "%":
        return 0, 100, 1
    if key in POWER_FACTOR_KEYS:
        return -1, 1, 0.01
    if unit in ("W", "VA", "VAr"):
        return (-MAX_POWER if key in SIGNED_SETPOINT_KEYS else 0), MAX_POWER, 1
    if unit == "Wh":
        return 0, 1_000_000, 1
    if unit == "A":
        return 0, 125, 1
    if unit in ("°C", "K"):
        return -50, 150, 0.5
    if key in SIGNED_SETPOINT_KEYS:
        return -1_000_000, 1_000_000, 0.1
    return 0, 1_000_000, 1


def _apply_unit(entity: NumberEntity, key: str, unit: str | None) -> None:
    entity._attr_native_min_value, entity._attr_native_max_value, entity._attr_native_step = (
        _limits(key, unit)
    )
    if unit in UNIT_DEVICE_CLASS:
        entity._attr_device_class, entity._attr_native_unit_of_measurement = UNIT_DEVICE_CLASS[unit]
    elif unit:
        entity._attr_native_unit_of_measurement = unit
    if key in BATTERY_SOC_KEYS or unit == "%":
        entity._attr_mode = NumberMode.SLIDER
    else:
        entity._attr_mode = NumberMode.BOX


def _to_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_api(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeaamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [
        BeaamCommandNumber(coordinator, dp)
        for dp in coordinator.data_points.values()
        if dp.controllable and dp.data_type == DT_NUMBER
    ]
    entities.extend(
        BeaamSettingNumber(coordinator, thing_id, key)
        for thing_id, key, value in setting_items(coordinator)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )
    async_add_entities(entities)


class BeaamCommandNumber(BeaamDataPointEntity, NumberEntity):
    """A controllable numeric data point, written via /things/{id}/commands."""

    def __init__(self, coordinator: BeaamCoordinator, dp: DataPointInfo) -> None:
        super().__init__(coordinator, dp)
        self._attr_entity_category = EntityCategory.CONFIG
        _apply_unit(self, dp.key, dp.unit)

    @property
    def native_value(self) -> float | None:
        return _to_number(self.raw_value)

    async def async_set_native_value(self, value: float) -> None:
        assert self.dp.thing_id is not None
        await self.coordinator.async_send_command(
            self.dp.thing_id, self.dp.key, _to_api(value), self.dp.id
        )


class BeaamSettingNumber(BeaamSettingEntity, NumberEntity):
    """A numeric thing setting, written via /things/{id}/settings."""

    def __init__(self, coordinator: BeaamCoordinator, thing_id: str, key: str) -> None:
        super().__init__(coordinator, thing_id, key)
        _apply_unit(self, key, SETTING_UNITS.get(key))

    @property
    def native_value(self) -> float | None:
        return _to_number(self.raw_value)

    async def async_set_native_value(self, value: float) -> None:
        await self._async_set(_to_api(value))
