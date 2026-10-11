"""Config flow for the neoom BEAAM integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import BeaamApiClient, BeaamAuthError, BeaamError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MAX_SCAN_INTERVAL, MIN_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

API_KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): API_KEY_SELECTOR,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): API_KEY_SELECTOR})


class BeaamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a BEAAM using its IP/hostname and local API key."""

    VERSION = 1

    async def _async_validate(
        self, host: str, api_key: str
    ) -> tuple[dict[str, Any] | None, dict[str, str]]:
        client = BeaamApiClient(async_get_clientsession(self.hass), host, api_key)
        try:
            return await client.get_site_configuration(), {}
        except BeaamAuthError:
            return None, {"base": "invalid_auth"}
        except BeaamError as err:
            _LOGGER.debug("Cannot connect to BEAAM at %s: %s", host, err)
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error while validating BEAAM")
            return None, {"base": "unknown"}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            config, errors = await self._async_validate(
                user_input[CONF_HOST], user_input[CONF_API_KEY]
            )
            if config is not None:
                await self.async_set_unique_id(config["siteId"])
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(
                    title=f"BEAAM ({user_input[CONF_HOST]})", data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            config, errors = await self._async_validate(
                entry.data[CONF_HOST], user_input[CONF_API_KEY]
            )
            if config is not None:
                await self.async_set_unique_id(config["siteId"])
                self._abort_if_unique_id_mismatch(reason="wrong_site")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"host": entry.data[CONF_HOST]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            config, errors = await self._async_validate(
                user_input[CONF_HOST], user_input[CONF_API_KEY]
            )
            if config is not None:
                await self.async_set_unique_id(config["siteId"])
                self._abort_if_unique_id_mismatch(reason="wrong_site")
                return self.async_update_reload_and_abort(
                    entry,
                    title=f"BEAAM ({user_input[CONF_HOST]})",
                    data_updates=user_input,
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, user_input or dict(entry.data)
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BeaamOptionsFlow()


class BeaamOptionsFlow(OptionsFlow):
    """Polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    )
                }
            ),
        )
