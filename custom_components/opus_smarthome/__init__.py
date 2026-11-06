"""OPUS SmartHome integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from pyopus_smarthome import OpusClient

from .const import DOMAIN, PLATFORMS
from .coordinator import OpusCoordinator
from .ezr import EzrCoordinator, find_ezr_host, find_heat_controller

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
    await _async_setup_ezr(hass, entry, coordinator)
    await coordinator.start_stream()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_setup_ezr(
    hass: HomeAssistant, entry: OpusConfigEntry, coordinator: OpusCoordinator
) -> None:
    """Poll the floor-heating controller if OPUS reports one."""
    controller = find_heat_controller(coordinator.data)
    host = find_ezr_host(coordinator.data)
    if controller is None or host is None:
        return

    ezr = EzrCoordinator(hass, entry, host, controller.device_id)
    # Entities are created from the OPUS device list, so a controller that is
    # unreachable right now only leaves them unavailable until the next poll.
    await ezr.async_refresh()
    if not ezr.last_update_success:
        _LOGGER.warning("Heating controller at %s is not reachable yet", host)
    coordinator.ezr = ezr


async def async_unload_entry(hass: HomeAssistant, entry: OpusConfigEntry) -> bool:
    """Unload an OPUS SmartHome config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: OpusCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.stop_stream()
        await coordinator.client.close()
    return unload_ok
