"""End-to-end tests against a mocked BEAAM."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import BASE, BATTERY, DOMAIN, SITE_ID


async def _setup(hass, config_entry):
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_creates_entities(hass, mock_beaam, config_entry):
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    # Bearer auth header is sent
    _, _, _, headers = mock_beaam.mock_calls[0]
    assert headers["Authorization"] == "Bearer sk_beaam_test"

    # Energy flow on the BEAAM device; fraction scaled to %
    suff = hass.states.get("sensor.beaam_self_sufficiency")
    assert float(suff.state) == 85.0
    assert suff.attributes["unit_of_measurement"] == "%"

    grid = hass.states.get("sensor.beaam_power_grid")
    assert grid.state == "-3994.0"
    assert grid.attributes["device_class"] == "power"

    produced = hass.states.get("sensor.beaam_energy_produced")
    assert produced.attributes["unit_of_measurement"] == "kWh"
    assert produced.attributes["state_class"] == "total_increasing"
    assert float(produced.state) == 1234.567

    frac = hass.states.get("sensor.beaam_fraction_pv_to_consumption")
    assert frac.attributes["unit_of_measurement"] == "%"
    assert round(float(frac.state), 1) == 57.0

    # Data points without a value on this site are disabled by default
    assert er.async_get(hass).async_get("sensor.beaam_power_heating").disabled_by is not None

    # Thing devices
    assert hass.states.get("sensor.netzzahler_voltage_p1").state == "229.7"
    assert hass.states.get("binary_sensor.netzzahler_connection").state == "on"
    soc = hass.states.get("sensor.speicher_state_of_charge")
    assert soc.state == "73.0" and soc.attributes["device_class"] == "battery"
    cap = hass.states.get("sensor.speicher_installed_capacity")
    assert cap.attributes["device_class"] == "energy_storage"
    assert cap.attributes["state_class"] == "measurement"

    # Controllables
    tp = hass.states.get("number.speicher_target_power")
    assert tp.state == "0.0" and tp.attributes["min"] == -100000
    assert hass.states.get("switch.speicher_on_off").state == "on"

    # Settings
    assert hass.states.get("switch.speicher_battery_charge_from_grid_allowed").state == "off"
    assert float(hass.states.get("number.speicher_priority").state) == 2
    assert hass.states.get("sensor.speicher_operating_mode_ems").state == "SELF_CONSUMPTION"

    # Array sensor is disabled by default
    ent_reg = er.async_get(hass)
    temps = ent_reg.async_get("sensor.speicher_rack_temperatures")
    assert temps.disabled_by is not None

    # Devices
    dev_reg = dr.async_get(hass)
    battery = dev_reg.async_get_device_by_identifier((DOMAIN, BATTERY), config_entry.entry_id)
    assert battery.name == "Speicher"
    assert battery.serial_number == "SN123"
    site = dev_reg.async_get_device_by_identifier((DOMAIN, SITE_ID), config_entry.entry_id)
    assert battery.via_device_id == site.id


async def test_set_target_power(hass, mock_beaam, config_entry):
    await _setup(hass, config_entry)
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.speicher_target_power", "value": -5000},
        blocking=True,
    )
    call = next(c for c in mock_beaam.mock_calls if c[0] == "POST")
    assert str(call[1]) == f"{BASE}/things/{BATTERY}/commands"
    assert call[2] == [{"key": "TARGET_POWER", "value": -5000}]
    assert float(hass.states.get("number.speicher_target_power").state) == -5000


async def test_toggle_setting(hass, mock_beaam, config_entry):
    await _setup(hass, config_entry)
    await hass.services.async_call(
        "switch", "turn_on",
        {"entity_id": "switch.speicher_battery_charge_from_grid_allowed"},
        blocking=True,
    )
    call = next(c for c in mock_beaam.mock_calls if c[0] == "PUT")
    # written back in the same (string) representation the BEAAM reports
    assert call[2] == [{"key": "BATTERY_CHARGE_FROM_GRID_ALLOWED", "value": "true"}]
    assert hass.states.get("switch.speicher_battery_charge_from_grid_allowed").state == "on"


async def test_command_rejected(hass, mock_beaam, config_entry):
    import pytest
    from homeassistant.exceptions import HomeAssistantError

    mock_beaam.clear_requests()
    from .conftest import SITE_CONFIG, SITE_STATE, METER_STATES, BATTERY_STATES, BATTERY_SETTINGS, METER
    mock_beaam.get(f"{BASE}/site/configuration", json=SITE_CONFIG)
    mock_beaam.get(f"{BASE}/site/state", json=SITE_STATE)
    mock_beaam.get(f"{BASE}/things/{METER}/states", json=METER_STATES)
    mock_beaam.get(f"{BASE}/things/{BATTERY}/states", json=BATTERY_STATES)
    mock_beaam.get(f"{BASE}/things/{METER}/settings", status=404)
    mock_beaam.get(f"{BASE}/things/{BATTERY}/settings", json=BATTERY_SETTINGS)
    mock_beaam.post(
        f"{BASE}/things/{BATTERY}/commands", status=500,
        json=[{"key": "TARGET_POWER", "status": "REJECTED", "message": "remote control disabled"}],
    )
    await _setup(hass, config_entry)
    with pytest.raises(HomeAssistantError, match="remote control disabled"):
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": "number.speicher_target_power", "value": 1000},
            blocking=True,
        )


async def test_send_command_action(hass, mock_beaam, config_entry):
    await _setup(hass, config_entry)
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, BATTERY), config_entry.entry_id)
    await hass.services.async_call(
        DOMAIN, "send_command",
        {"device_id": device.id, "key": "TARGET_POWER", "value": 2500},
        blocking=True,
    )
    call = next(c for c in mock_beaam.mock_calls if c[0] == "POST")
    assert call[2] == [{"key": "TARGET_POWER", "value": 2500}]


async def test_auth_failure_starts_reauth(hass, aioclient_mock, config_entry):
    aioclient_mock.get(f"{BASE}/site/configuration", status=401)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_not_ready_when_offline(hass, aioclient_mock, config_entry):
    import aiohttp
    aioclient_mock.get(f"{BASE}/site/configuration", exc=aiohttp.ClientError())
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_diagnostics_redacts_key(hass, mock_beaam, config_entry):
    from custom_components.neoom_beaam.diagnostics import async_get_config_entry_diagnostics
    await _setup(hass, config_entry)
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["entry"]["data"]["api_key"] == "**REDACTED**"
    assert "sk_beaam_test" not in str(diag)
