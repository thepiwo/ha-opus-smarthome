"""OPUS SmartHome integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from pyopus_smarthome import OpusClient

from .const import DOMAIN, PLATFORMS
from .coordinator import OpusCoordinator

_LOGGER = logging.getLogger(__name__)

type OpusConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: OpusConfigEntry) -> bool:
    """Set up OPUS SmartHome from a config entry."""
    client = OpusClient(
        entry.data[CONF_HOST],
        eurid=entry.data["eurid"],
        port=entry.data[CONF_PORT],
    )

    coordinator = OpusCoordinator(
        hass,
        client,
        host=entry.data[CONF_HOST],
        eurid=entry.data["eurid"],
        port=entry.data[CONF_PORT],
    )

    await coordinator.async_config_entry_first_refresh()
    await coordinator.start_stream()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpusConfigEntry) -> bool:
    """Unload an OPUS SmartHome config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: OpusCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.stop_stream()
        await coordinator.client.close()
    return unload_ok
