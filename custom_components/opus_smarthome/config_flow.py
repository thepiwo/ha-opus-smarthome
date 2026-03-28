"""Config flow for OPUS SmartHome."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required("eurid"): str,
    }
)


class OpusSmartHomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OPUS SmartHome."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            eurid = user_input["eurid"].strip().upper()

            try:
                from pyopus_smarthome import OpusClient

                client = OpusClient(
                    user_input[CONF_HOST],
                    eurid=eurid,
                    port=user_input[CONF_PORT],
                )
                try:
                    gateway = await client.get_system_info()
                finally:
                    await client.close()

            except Exception:
                _LOGGER.exception("Failed to connect to OPUS gateway")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(gateway.eurid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"OPUS Gateway ({gateway.eurid[-8:]})",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        "eurid": gateway.eurid,
                        "serial": gateway.serial,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
