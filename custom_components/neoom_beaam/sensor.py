"""Sensors for the neoom BEAAM integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ARRAY_DATA_TYPES,
    BATTERY_SOC_KEYS,
    CODE_KEYS,
    DT_BOOLEAN,
    DT_NUMBER,
    ENERGY_STORAGE_KEYS,
    FRACTION_PREFIX,
    POWER_FACTOR_KEYS,
)
from .coordinator import BeaamConfigEntry, BeaamCoordinator, DataPointInfo
from .entity import BeaamDataPointEntity, BeaamSettingEntity, setting_items

PARALLEL_UPDATES = 0

# BEAAM unit -> (device class, HA unit, state class, display precision)
UNIT_MAP: dict[str, tuple[SensorDeviceClass | None, str, SensorStateClass, int | None]] = {
    "W": (SensorDeviceClass.POWER, UnitOfPower.WATT, SensorStateClass.MEASUREMENT, 0),
    "Wh": (SensorDeviceClass.ENERGY, UnitOfEnergy.WATT_HOUR, SensorStateClass.TOTAL_INCREASING, 2),
    "V": (SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, SensorStateClass.MEASUREMENT, 1),
    "A": (SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, SensorStateClass.MEASUREMENT, 2),
    "VA": (SensorDeviceClass.APPARENT_POWER, UnitOfApparentPower.VOLT_AMPERE, SensorStateClass.MEASUREMENT, 0),
    "VAr": (SensorDeviceClass.REACTIVE_POWER, UnitOfReactivePower.VOLT_AMPERE_REACTIVE, SensorStateClass.MEASUREMENT, 0),
    "Hz": (SensorDeviceClass.FREQUENCY, UnitOfFrequency.HERTZ, SensorStateClass.MEASUREMENT, 2),
    "%": (None, PERCENTAGE, SensorStateClass.MEASUREMENT, 1),
    "°C": (SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, SensorStateClass.MEASUREMENT, 1),
    "K": (None, "K", SensorStateClass.MEASUREMENT, 1),
    "m3": (SensorDeviceClass.VOLUME, UnitOfVolume.CUBIC_METERS, SensorStateClass.TOTAL_INCREASING, 3),
    "m3/s": (None, "m³/s", SensorStateClass.MEASUREMENT, 4),
    "l": (SensorDeviceClass.VOLUME_STORAGE, UnitOfVolume.LITERS, SensorStateClass.MEASUREMENT, 1),
    "l/h": (None, "L/h", SensorStateClass.MEASUREMENT, 1),
    "Pa": (SensorDeviceClass.PRESSURE, UnitOfPressure.PA, SensorStateClass.MEASUREMENT, 0),
    "s": (SensorDeviceClass.DURATION, UnitOfTime.SECONDS, SensorStateClass.MEASUREMENT, 0),
    "h": (SensorDeviceClass.DURATION, UnitOfTime.HOURS, SensorStateClass.TOTAL_INCREASING, 1),
    "Vr": (None, "Vr", SensorStateClass.MEASUREMENT, 1),
    "Ar": (None, "Ar", SensorStateClass.MEASUREMENT, 2),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeaamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for dp in coordinator.data_points.values():
        if dp.data_type == DT_BOOLEAN:
            continue  # binary_sensor / switch
        if dp.controllable and dp.data_type == DT_NUMBER:
            continue  # number
        entities.append(BeaamSensor(coordinator, dp))
    entities.extend(
        BeaamSettingSensor(coordinator, thing_id, key)
        for thing_id, key, value in setting_items(coordinator)
        if isinstance(value, str)
    )
    async_add_entities(entities)


class BeaamSensor(BeaamDataPointEntity, SensorEntity):
    """A read-only data point."""

    def __init__(self, coordinator: BeaamCoordinator, dp: DataPointInfo) -> None:
        super().__init__(coordinator, dp)
        self._is_array = dp.data_type in ARRAY_DATA_TYPES
        self._is_number = dp.data_type == DT_NUMBER
        self._is_fraction = dp.key.startswith(FRACTION_PREFIX) and dp.unit is None

        if self._is_array:
            self._attr_entity_registry_enabled_default = False
            return
        if not self._is_number:
            return

        if dp.unit in UNIT_MAP:
            device_class, unit, state_class, precision = UNIT_MAP[dp.unit]
            self._attr_device_class = device_class
            self._attr_native_unit_of_measurement = unit
            self._attr_state_class = state_class
            self._attr_suggested_display_precision = precision
            if dp.unit == "Wh":
                self._attr_suggested_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
                if dp.key in ENERGY_STORAGE_KEYS:
                    self._attr_device_class = SensorDeviceClass.ENERGY_STORAGE
                    self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._is_fraction:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 0
        elif dp.unit:
            self._attr_native_unit_of_measurement = dp.unit
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif dp.key in POWER_FACTOR_KEYS:
            self._attr_device_class = SensorDeviceClass.POWER_FACTOR
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif dp.key not in CODE_KEYS:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        else:
            self._attr_suggested_display_precision = 0

        if dp.key in BATTERY_SOC_KEYS:
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> Any:
        value = self.raw_value
        if value is None:
            return None
        if self._is_array:
            return ", ".join(str(v) for v in value)[:255] if isinstance(value, list) else None
        if self._is_number:
            try:
                number = float(value)
            except (TypeError, ValueError):
                return None
            return number * 100 if self._is_fraction else number
        return str(value)[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._is_array and isinstance(self.raw_value, list):
            return {"values": self.raw_value}
        return None


class BeaamSettingSensor(BeaamSettingEntity, SensorEntity):
    """A text-valued thing setting (read-only; write via the update_setting action)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC  # sensors may not be CONFIG

    @property
    def native_value(self) -> str | None:
        value = self.raw_value
        return None if value is None else str(value)[:255]
