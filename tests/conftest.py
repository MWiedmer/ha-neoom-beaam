"""Fixtures for neoom BEAAM tests."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import custom_components

import pytest

from homeassistant.const import CONF_API_KEY, CONF_HOST

from pytest_homeassistant_custom_component.common import MockConfigEntry

# The test harness ships its own custom_components package; add ours to it.
_OURS = str(Path(__file__).parents[1] / "custom_components")
if _OURS not in custom_components.__path__:
    custom_components.__path__.append(_OURS)

DOMAIN = "neoom_beaam"
HOST = "192.0.2.10"
BASE = f"http://{HOST}/api/v1"
SITE_ID = "0756c8be-13e5-494c-9331-8dfc1a30d28a"
METER = "0c7bc039-50c1-4b01-93bd-76ca45d55bff"
BATTERY = "d4f65a33-ee5c-421d-855d-2d5682a4bc4d"

SITE_CONFIG: dict[str, Any] = {
    "siteId": SITE_ID,
    "versionTimestamp": 1744812611,
    "siteInfo": {"geoCoordinates": {"latitude": 48.48, "longitude": 14.49}},
    "externalPlantControls": {},
    "things": {
        METER: {
            "name": "Netzzähler",
            "type": "ELECTRICITY_METER_AC",
            "dataPoints": {
                "dp-conn": {"key": "CONNECTION", "dataType": "BOOLEAN", "unitOfMeasure": "None", "controllable": False},
                "dp-v1": {"key": "VOLTAGE_P1", "dataType": "NUMBER", "unitOfMeasure": "V", "controllable": False},
                "dp-p": {"key": "ACTIVE_POWER", "dataType": "NUMBER", "unitOfMeasure": "W", "controllable": False},
                "dp-imp": {"key": "CONSUMED_ENERGY", "dataType": "NUMBER", "unitOfMeasure": "Wh", "controllable": False},
            },
        },
        BATTERY: {
            "name": "Speicher",
            "type": "BATTERY",
            "dataPoints": {
                "dp-soc": {"key": "STATE_OF_CHARGE", "dataType": "NUMBER", "unitOfMeasure": "%", "controllable": False},
                "dp-tp": {"key": "TARGET_POWER", "dataType": "NUMBER", "unitOfMeasure": "W", "controllable": True},
                "dp-onoff": {"key": "ON_OFF", "dataType": "BOOLEAN", "unitOfMeasure": "None", "controllable": True},
                "dp-cap": {"key": "INSTALLED_CAPACITY", "dataType": "NUMBER", "unitOfMeasure": "Wh", "controllable": False},
                "dp-temps": {"key": "RACK_TEMPERATURES", "dataType": "NUMBER_ARRAY[]", "unitOfMeasure": "°C", "controllable": False},
                "dp-sn": {"key": "SERIAL_NUMBER", "dataType": "STRING", "unitOfMeasure": "None", "controllable": False},
            },
        },
    },
    "energyFlow": {
        "dataPoints": {
            "ef-suff": {"key": "SELF_SUFFICIENCY", "dataType": "NUMBER", "unitOfMeasure": "%"},
            "ef-grid": {"key": "POWER_GRID", "dataType": "NUMBER", "unitOfMeasure": "W"},
            "ef-prod": {"key": "ENERGY_PRODUCED", "dataType": "NUMBER", "unitOfMeasure": "Wh"},
            "ef-frac": {"key": "FRACTION_PV_TO_CONSUMPTION", "dataType": "NUMBER", "unitOfMeasure": "None"},
            "ef-heat": {"key": "POWER_HEATING", "dataType": "NUMBER", "unitOfMeasure": "W"},
        }
    },
}

SITE_STATE = {"energyFlow": {"states": [
    {"dataPointId": "ef-suff", "key": "SELF_SUFFICIENCY", "value": 85, "ts": 1},
    {"dataPointId": "ef-grid", "key": "POWER_GRID", "value": -3994, "ts": 1},
    {"dataPointId": "ef-prod", "key": "ENERGY_PRODUCED", "value": 1234567, "ts": 1},
    {"dataPointId": "ef-frac", "key": "FRACTION_PV_TO_CONSUMPTION", "value": 0.5698924731182796, "ts": 1},
    {"dataPointId": "ef-heat", "key": "POWER_HEATING", "value": None, "ts": 1},
]}}

METER_STATES = {"thingId": METER, "states": [
    {"dataPointId": "dp-conn", "key": "CONNECTION", "value": True, "ts": 1},
    {"dataPointId": "dp-v1", "key": "VOLTAGE_P1", "value": 229.7, "ts": 1},
    {"dataPointId": "dp-p", "key": "ACTIVE_POWER", "value": -907, "ts": 1},
    {"dataPointId": "dp-imp", "key": "CONSUMED_ENERGY", "value": 5000000, "ts": 1},
]}

BATTERY_STATES = {"thingId": BATTERY, "states": [
    {"dataPointId": "dp-soc", "key": "STATE_OF_CHARGE", "value": 73, "ts": 1},
    {"dataPointId": "dp-tp", "key": "TARGET_POWER", "value": 0, "ts": 1},
    {"dataPointId": "dp-onoff", "key": "ON_OFF", "value": True, "ts": 1},
    {"dataPointId": "dp-cap", "key": "INSTALLED_CAPACITY", "value": 10000, "ts": 1},
    {"dataPointId": "dp-temps", "key": "RACK_TEMPERATURES", "value": [21.5, 22.0], "ts": 1},
    {"dataPointId": "dp-sn", "key": "SERIAL_NUMBER", "value": "SN123", "ts": 1},
]}

BATTERY_SETTINGS = {"thingId": BATTERY, "settings": [
    {"key": "BATTERY_CHARGE_FROM_GRID_ALLOWED", "value": "false"},
    {"key": "PRIORITY", "value": "2"},
    {"key": "OPERATING_MODE_EMS", "value": "SELF_CONSUMPTION"},
]}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_beaam(aioclient_mock):
    """Register all BEAAM endpoints on the aiohttp mocker."""
    aioclient_mock.get(f"{BASE}/site/configuration", json=copy.deepcopy(SITE_CONFIG))
    aioclient_mock.get(f"{BASE}/site/state", json=copy.deepcopy(SITE_STATE))
    aioclient_mock.get(f"{BASE}/things/{METER}/states", json=copy.deepcopy(METER_STATES))
    aioclient_mock.get(f"{BASE}/things/{BATTERY}/states", json=copy.deepcopy(BATTERY_STATES))
    aioclient_mock.get(f"{BASE}/things/{METER}/settings", status=404)
    aioclient_mock.get(f"{BASE}/things/{BATTERY}/settings", json=copy.deepcopy(BATTERY_SETTINGS))
    aioclient_mock.post(
        f"{BASE}/things/{BATTERY}/commands",
        json=[{"key": "TARGET_POWER", "status": "SUCCESSFUL"}],
    )
    aioclient_mock.put(f"{BASE}/things/{BATTERY}/settings", status=200)
    return aioclient_mock


@pytest.fixture
def config_entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SITE_ID,
        title=f"BEAAM ({HOST})",
        data={CONF_HOST: HOST, CONF_API_KEY: "sk_beaam_test"},
    )
    entry.add_to_hass(hass)
    return entry
