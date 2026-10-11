"""Constants for the neoom BEAAM integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "neoom_beaam"

DEFAULT_SCAN_INTERVAL: Final = 15  # seconds
MIN_SCAN_INTERVAL: Final = 5
MAX_SCAN_INTERVAL: Final = 3600

# How often the site configuration is re-read to detect added/removed devices.
CONFIG_CHECK_INTERVAL: Final = timedelta(minutes=10)

# Limit parallel requests so the BEAAM is not flooded on sites with many things.
MAX_PARALLEL_REQUESTS: Final = 4

# Data types as reported by the BEAAM
DT_BOOLEAN: Final = "BOOLEAN"
DT_NUMBER: Final = "NUMBER"
DT_STRING: Final = "STRING"
ARRAY_DATA_TYPES: Final = {"BOOLEAN_ARRAY[]", "NUMBER_ARRAY[]", "STRING_ARRAY[]"}

# Command response statuses that count as success
COMMAND_OK_STATUSES: Final = {"SUCCESSFUL", "PENDING"}

# Unitless energy flow shares (FRACTION_PV_TO_GRID, ...) delivered as 0..1.
FRACTION_PREFIX: Final = "FRACTION_"

# Keys whose values are state/mode codes rather than measurements.
CODE_KEYS: Final = {
    "STATE_CODE",
    "ERROR_CODES",
    "OPERATING_MODE",
    "OPERATING_MODES",
    "OPERATING_MODE_SG_READY",
    "OPERATING_MODE_REACTIVE",
    "CP_STATE_CODE",
    "EV_STATE_CODE",
    "CONTROL_STATE",
    "CONTROLLER_MODE",
    "POWER_CONTROL_MODE",
    "PHASE_SWITCHING_MODE",
    "BATTERY_BALANCING_MODE",
    "BATTERY_BALANCING_STATE",
    "COOLING_UNIT_STATE",
    "STATION_AVAILABILITY",
    "GRID_LIMITATION_BITMASK",
    "LOAD_SHEDDING_LEVELS",
    "CHARGING_PROCESS_ID",
    "CHARGING_PROCESS_START_TIME",
    "LOCK_UNTIL",
    "LAST_RFID_CARD",
    "SERIAL_NUMBER",
    "FIRMWARE_VERSION",
    "MAX_CELL_TEMPERATURE_NUMBER",
    "MIN_CELL_TEMPERATURE_NUMBER",
    "MAX_CELL_VOLTAGE_NUMBER",
    "MIN_CELL_VOLTAGE_NUMBER",
}

DIAGNOSTIC_KEYS: Final = {
    "CONNECTION",
    "CONNECTIONS",
    "CONNECTION_TRADER",
    "CONNECTION_TRADER_BACKEND",
    "CONNECTION_SYSTEM",
    "STATE_CODE",
    "ERROR_CODES",
    "SERIAL_NUMBER",
    "FIRMWARE_VERSION",
    "HEATSINK_TEMPERATURES",
    "RACK_TEMPERATURES",
    "RACK_HUMIDITIES",
    "CHARGING_PROCESS_ID",
    "LAST_RFID_CARD",
    "MAX_CELL_TEMPERATURE_NUMBER",
    "MIN_CELL_TEMPERATURE_NUMBER",
    "MAX_CELL_VOLTAGE_NUMBER",
    "MIN_CELL_VOLTAGE_NUMBER",
}

# Wh values that are a stored amount / capacity rather than a lifetime counter.
ENERGY_STORAGE_KEYS: Final = {
    "CAPACITY",
    "INSTALLED_CAPACITY",
    "OVERALL_INSTALLED_CAPACITY",
    "OVERALL_AVAILABLE_CAPACITY",
    "REMAINING_ENERGY_CHARGE",
    "REMAINING_ENERGY_DISCHARGE",
    "OVERALL_REMAINING_ENERGY_CHARGE",
    "OVERALL_REMAINING_ENERGY_DISCHARGE",
}

BATTERY_SOC_KEYS: Final = {"STATE_OF_CHARGE", "OVERALL_STATE_OF_CHARGE"}

# Setpoints that may be negative (e.g. negative TARGET_POWER = discharge battery).
SIGNED_SETPOINT_KEYS: Final = {
    "TARGET_POWER",
    "TARGET_POWER_SETPOINT",
    "TARGET_LOCAL_POWER_OFFSET",
    "LOCAL_POWER_SETPOINT",
    "OVERALL_TARGET_POWER_SETPOINT",
    "SLAVE_TARGET_POWER",
    "THIRDPARTY_TARGET_POWER",
    "TARGET_POWER_REACTIVE",
    "SLAVE_TARGET_POWER_REACTIVE",
    "THIRDPARTY_TARGET_POWER_REACTIVE",
    "HC_PARALLEL_SHIFT",
}

POWER_FACTOR_KEYS: Final = {
    "POWER_FACTOR",
    "TARGET_POWER_FACTOR",
    "SLAVE_TARGET_POWER_FACTOR",
    "THIRDPARTY_TARGET_POWER_FACTOR",
}

# Thing settings carry no unit in the API; these are the known ones.
SETTING_UNITS: Final = {
    "POWER_THRESHOLD_RECOMMENDED_OP": "W",
    "POWER_THRESHOLD_NORMAL_OP": "W",
    "GRID_FEED_IN_PRIORITIZATION_POWER": "W",
    "GRIID_CHARGING_ENERGY": "Wh",
}

# Words kept upper-case when turning a data point key into an entity name.
NAME_ACRONYMS: Final = {
    "AC", "CMS", "COP", "CP", "DC", "EMS", "EPS", "EV", "HC", "ID", "OP",
    "P1", "P2", "P3", "PV", "RFID", "SG", "SOC",
}

SERVICE_SEND_COMMAND: Final = "send_command"
SERVICE_UPDATE_SETTING: Final = "update_setting"
SERVICE_PUSH_STATES: Final = "push_states"

ATTR_DEVICE_ID: Final = "device_id"
ATTR_KEY: Final = "key"
ATTR_VALUE: Final = "value"
ATTR_STATES: Final = "states"
