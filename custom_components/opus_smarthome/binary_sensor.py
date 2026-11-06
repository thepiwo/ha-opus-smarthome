"""Binary sensor platform for OPUS SmartHome heating diagnostics."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from pyopus_smarthome import Device

from .const import DOMAIN
from .coordinator import OpusCoordinator
from .entity import OpusBaseEntity
from .ezr import EzrBaseEntity, EzrCoordinator, EzrZoneEntity, heat_zone_devices


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OPUS binary sensor entities."""
    coordinator: OpusCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [
        OpusMissingDataBinarySensor(coordinator, device)
        for device in coordinator.data.values()
        if device.is_climate and not device.is_heat_controller
    ]

    ezr = coordinator.ezr
    controller = (
        coordinator.data.get(ezr.controller_device_id) if ezr is not None else None
    )
    if ezr is not None and controller is not None:
        entities.append(EzrPumpBinarySensor(ezr, controller))
        entities.append(EzrRelayBinarySensor(ezr, controller))
        entities.extend(
            EzrEmergencyModeBinarySensor(ezr, device, number)
            for device, number in heat_zone_devices(coordinator.data)
        )

    async_add_entities(entities)


class OpusMissingDataBinarySensor(OpusBaseEntity, BinarySensorEntity):
    """On while OPUS has no current temperature for a heating zone.

    The controller loses the zone's room unit at the same time and, after its
    emergency delay, heats the zone on a fixed duty cycle.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "Sensor data missing"

    def __init__(self, coordinator: OpusCoordinator, device: Device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{DOMAIN}_{device.device_id}_missing_data"

    @property
    def is_on(self) -> bool | None:
        device = self.device
        if device is None:
            return None
        return device.get_state("missingData") == "error"


class EzrEmergencyModeBinarySensor(EzrZoneEntity, BinarySensorEntity):
    """On while the controller has lost the zone's room unit.

    After the controller's emergency delay the zone's valves run at the
    emergency duty cycle, ignoring the setpoint.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "Emergency mode"

    def __init__(
        self, coordinator: EzrCoordinator, device: Device, zone_number: int
    ) -> None:
        super().__init__(coordinator, device, zone_number, "emergency_mode")

    @property
    def is_on(self) -> bool | None:
        zone = self.zone
        return zone.room_unit_lost if zone is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        zone = self.zone
        status = self.coordinator.data
        if zone is None or status is None:
            return None
        return {
            "zone": zone.number,
            "signal_strength": [u.signal_strength for u in zone.room_units],
            "emergency_heat_percent": status.emergency_heat_percent,
            "emergency_delay_minutes": status.emergency_delay_minutes,
        }


class EzrPumpBinarySensor(EzrBaseEntity, BinarySensorEntity):
    """Circulation pump output of the controller."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_name = "Pump"

    def __init__(self, coordinator: EzrCoordinator, device: Device) -> None:
        super().__init__(coordinator, device, "pump")

    @property
    def is_on(self) -> bool | None:
        status = self.coordinator.data
        return status.pump_active if status is not None else None


class EzrRelayBinarySensor(EzrBaseEntity, BinarySensorEntity):
    """Boiler relay output of the controller."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_name = "Boiler relay"

    def __init__(self, coordinator: EzrCoordinator, device: Device) -> None:
        super().__init__(coordinator, device, "boiler_relay")

    @property
    def is_on(self) -> bool | None:
        status = self.coordinator.data
        return status.relay_active if status is not None else None
