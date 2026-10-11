"""Binary sensors for the neoom BEAAM integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DT_BOOLEAN
from .coordinator import BeaamConfigEntry, BeaamCoordinator, DataPointInfo
from .entity import BeaamDataPointEntity

PARALLEL_UPDATES = 0

DEVICE_CLASSES: dict[str, BinarySensorDeviceClass] = {
    "CONNECTION": BinarySensorDeviceClass.CONNECTIVITY,
    "CONNECTION_TRADER": BinarySensorDeviceClass.CONNECTIVITY,
    "CONNECTION_TRADER_BACKEND": BinarySensorDeviceClass.CONNECTIVITY,
    "CONNECTION_SYSTEM": BinarySensorDeviceClass.CONNECTIVITY,
    "GRID_CONNECTED": BinarySensorDeviceClass.CONNECTIVITY,
    "OVERALL_GRID_CONNECTED": BinarySensorDeviceClass.CONNECTIVITY,
    "SYSTEM_FAILURE": BinarySensorDeviceClass.PROBLEM,
    "OVERALL_SYSTEM_FAILURE": BinarySensorDeviceClass.PROBLEM,
    "SYSTEM_RUNNING": BinarySensorDeviceClass.RUNNING,
    "OVERALL_SYSTEM_RUNNING": BinarySensorDeviceClass.RUNNING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeaamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BeaamBinarySensor(coordinator, dp)
        for dp in coordinator.data_points.values()
        if dp.data_type == DT_BOOLEAN and not dp.controllable
    )


class BeaamBinarySensor(BeaamDataPointEntity, BinarySensorEntity):
    """A read-only boolean data point."""

    def __init__(self, coordinator: BeaamCoordinator, dp: DataPointInfo) -> None:
        super().__init__(coordinator, dp)
        self._attr_device_class = DEVICE_CLASSES.get(dp.key)

    @property
    def is_on(self) -> bool | None:
        value = self.raw_value
        return None if value is None else bool(value)
