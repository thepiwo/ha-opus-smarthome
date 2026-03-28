"""Base entity for OPUS SmartHome."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from pyopus_smarthome import Device

from .const import DOMAIN
from .coordinator import OpusCoordinator


class OpusBaseEntity(CoordinatorEntity[OpusCoordinator]):
    """Base class for OPUS SmartHome entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OpusCoordinator, device: Device) -> None:
        super().__init__(coordinator)
        self._device_id = device.device_id
        self._attr_unique_id = f"{DOMAIN}_{device.device_id}"

    @property
    def device(self) -> Device | None:
        """Get the current device data from the coordinator."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._device_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the HA device registry."""
        device = self.device
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device.friendly_id if device else self._device_id,
            manufacturer=device.manufacturer if device else None,
            model=", ".join(device.eeps) if device else None,
        )

    @property
    def available(self) -> bool:
        """Return True if the device data is available."""
        return super().available and self.device is not None
