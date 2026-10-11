"""Base entities for the neoom BEAAM integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DIAGNOSTIC_KEYS
from .coordinator import BeaamCoordinator, DataPointInfo, pretty_key


class BeaamEntity(CoordinatorEntity[BeaamCoordinator]):
    """Entity attached to the BEAAM or one of its things."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BeaamCoordinator, thing_id: str | None) -> None:
        super().__init__(coordinator)
        self._thing_id = thing_id
        self._attr_device_info = coordinator.device_info(thing_id)

    @property
    def available(self) -> bool:
        return super().available and (
            self._thing_id is None
            or self._thing_id not in self.coordinator.data.unavailable_things
        )


class BeaamDataPointEntity(BeaamEntity):
    """Entity backed by one data point."""

    def __init__(self, coordinator: BeaamCoordinator, dp: DataPointInfo) -> None:
        super().__init__(coordinator, dp.thing_id)
        self.dp = dp
        self._attr_unique_id = f"{coordinator.site_id}_{dp.id}"
        self._attr_name = pretty_key(dp.key)
        if dp.key in DIAGNOSTIC_KEYS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        # Sites only fill the energy flow points they have hardware for
        # (no wallbox -> no POWER_CHARGING_STATIONS); hide the empty ones.
        if not dp.controllable and coordinator.data.states.get(dp.id) is None:
            self._attr_entity_registry_enabled_default = False

    @property
    def raw_value(self) -> Any:
        return self.coordinator.data.states.get(self.dp.id)

    @property
    def available(self) -> bool:
        # Controllable data points may have no state yet but must stay settable.
        return super().available and (
            self.dp.controllable or self.dp.id in self.coordinator.data.states
        )


def parse_setting(value: Any) -> Any:
    """Settings arrive as strings ('true', '1', 'EXCESS_CONSUMPTION'); return a typed value."""
    if not isinstance(value, str):
        return value
    lowered = value.strip().lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        number = float(value)
    except ValueError:
        return value
    return int(number) if number.is_integer() else number


def encode_setting(new: Any, current_raw: Any) -> Any:
    """Send a value back in the same representation the BEAAM reported it."""
    if not isinstance(current_raw, str):
        return new
    if isinstance(new, bool):
        return "true" if new else "false"
    if isinstance(new, float) and new.is_integer():
        new = int(new)
    return str(new)


class BeaamSettingEntity(BeaamEntity):
    """Entity backed by one thing setting (/things/{id}/settings)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: BeaamCoordinator, thing_id: str, key: str) -> None:
        super().__init__(coordinator, thing_id)
        self.key = key
        self._attr_unique_id = f"{coordinator.site_id}_{thing_id}_setting_{key}"
        self._attr_name = pretty_key(key)

    @property
    def _reported_value(self) -> Any:
        return self.coordinator.data.settings.get(self._thing_id, {}).get(self.key)

    @property
    def raw_value(self) -> Any:
        return parse_setting(self._reported_value)

    @property
    def available(self) -> bool:
        return super().available and self.key in self.coordinator.data.settings.get(
            self._thing_id, {}
        )

    async def _async_set(self, value: Any) -> None:
        await self.coordinator.async_update_setting(
            self._thing_id, self.key, encode_setting(value, self._reported_value)
        )


def setting_items(coordinator: BeaamCoordinator) -> list[tuple[str, str, Any]]:
    """All (thing_id, key, typed value) settings known after the first refresh."""
    return [
        (thing_id, key, parse_setting(value))
        for thing_id in sorted(coordinator.setting_things)
        for key, value in coordinator.data.settings.get(thing_id, {}).items()
    ]
