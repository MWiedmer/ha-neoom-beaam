"""Config flow tests."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from .conftest import BASE, DOMAIN, HOST, SITE_CONFIG, SITE_ID


async def test_user_flow(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/site/configuration", json=SITE_CONFIG)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": f" {HOST} ", "api_key": "sk_beaam_x"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": HOST, "api_key": "sk_beaam_x"}
    assert result["result"].unique_id == SITE_ID


async def test_user_flow_invalid_auth(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/site/configuration", status=401)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "api_key": "bad"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow(hass, mock_beaam, config_entry):
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 30}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert config_entry.runtime_data.update_interval.total_seconds() == 30
