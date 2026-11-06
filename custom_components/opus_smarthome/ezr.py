"""Möhlenhoff EZR floor-heating controller behind the OPUS gateway.

OPUS exposes the controller's zones as heat areas but not what the controller
actually does (valve duty cycle, pump, boiler relay, lost room units). This
module polls the controller's local XML API for that.

The controller is found through OPUS: the heat-controller device reports its
address in the ``ipAddress`` state, and each heat area's ``physicalDevice``
names the controller zone it maps to.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from pyopus_smarthome import Device, EzrClient, EzrStatus, EzrZone, OpusError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

EZR_SCAN_INTERVAL = timedelta(seconds=60)


def find_heat_controller(devices: dict[str, Device]) -> Device | None:
    """Return the OPUS device that represents the floor-heating controller."""
    for device in devices.values():
        if device.is_heat_controller:
            return device
    return None


def find_ezr_host(devices: dict[str, Device]) -> str | None:
    """Return the controller's IP address as reported by OPUS, if any."""
    controller = find_heat_controller(devices)
    if controller is None:
        return None
    address = controller.get_state("ipAddress")
    if not isinstance(address, str) or not address.strip():
        return None
    return address.strip().split("/", 1)[0]


def heat_zone_devices(devices: dict[str, Device]) -> list[tuple[Device, int]]:
    """Return OPUS heat areas paired with their controller zone number."""
    zones: list[tuple[Device, int]] = []
    for device in devices.values():
        if not device.is_climate or device.is_heat_controller:
            continue
        number = device.heatarea_number
        if number is not None:
            zones.append((device, number))
    return zones


class EzrCoordinator(DataUpdateCoordinator[EzrStatus]):
    """Polls the Möhlenhoff EZR controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        host: str,
        controller_device_id: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_ezr",
            update_interval=EZR_SCAN_INTERVAL,
        )
        self.host = host
        self.controller_device_id = controller_device_id
        self.client = EzrClient(host, session=async_get_clientsession(hass))

    async def _async_update_data(self) -> EzrStatus:
        try:
            return await self.client.get_status()
        except OpusError as err:
            raise UpdateFailed(f"Cannot read heating controller: {err}") from err


class EzrBaseEntity(CoordinatorEntity[EzrCoordinator]):
    """Entity backed by controller data, attached to an existing OPUS device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EzrCoordinator,
        device: Device,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._opus_device_id = device.device_id
        self._attr_unique_id = f"{DOMAIN}_{device.device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.friendly_id or device.device_id,
            manufacturer=device.manufacturer,
            model=", ".join(device.eeps) if device.eeps else None,
        )


class EzrZoneEntity(EzrBaseEntity):
    """Entity for one controller zone."""

    def __init__(
        self,
        coordinator: EzrCoordinator,
        device: Device,
        zone_number: int,
        key: str,
    ) -> None:
        super().__init__(coordinator, device, key)
        self._zone_number = zone_number

    @property
    def zone(self) -> EzrZone | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.zones.get(self._zone_number)

    @property
    def available(self) -> bool:
        return super().available and self.zone is not None
