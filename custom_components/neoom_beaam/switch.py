"""Switches for the neoom BEAAM integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DT_BOOLEAN
from .coordinator import BeaamConfigEntry, BeaamCoordinator, DataPointInfo
from .entity import BeaamDataPointEntity, BeaamSettingEntity, setting_items

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeaamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [
        BeaamCommandSwitch(coordinator, dp)
        for dp in coordinator.data_points.values()
        if dp.controllable and dp.data_type == DT_BOOLEAN
    ]
    entities.extend(
        BeaamSettingSwitch(coordinator, thing_id, key)
        for thing_id, key, value in setting_items(coordinator)
        if isinstance(value, bool)
    )
    async_add_entities(entities)


class BeaamCommandSwitch(BeaamDataPointEntity, SwitchEntity):
    """A controllable boolean data point (e.g. ON_OFF, ENABLE_CHARGING)."""

    def __init__(self, coordinator: BeaamCoordinator, dp: DataPointInfo) -> None:
        super().__init__(coordinator, dp)
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool | None:
        value = self.raw_value
        return None if value is None else bool(value)

    async def _async_set(self, value: bool) -> None:
        assert self.dp.thing_id is not None
        await self.coordinator.async_send_command(
            self.dp.thing_id, self.dp.key, value, self.dp.id
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)


class BeaamSettingSwitch(BeaamSettingEntity, SwitchEntity):
    """A boolean thing setting (e.g. BATTERY_CHARGE_FROM_GRID_ALLOWED)."""

    @property
    def is_on(self) -> bool | None:
        value = self.raw_value
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)
