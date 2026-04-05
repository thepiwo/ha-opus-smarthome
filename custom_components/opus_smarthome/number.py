"""Number platform for OPUS SmartHome device configuration."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from pyopus_smarthome import Device

from .const import DOMAIN
from .coordinator import OpusCoordinator
from .entity import OpusBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OPUS number entities."""
    coordinator: OpusCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = []
    for device in coordinator.data.values():
        if device.is_cover and device.get_configuration_parameter("rotationTime") is not None:
            entities.append(OpusCoverRotationTimeNumber(coordinator, device))
    async_add_entities(entities)


class OpusCoverRotationTimeNumber(OpusBaseEntity, NumberEntity):
    """Expose OPUS cover slat rotation time as a number entity."""

    _attr_name = "Rotation Time"
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"
    _attr_native_min_value = 0
    _attr_native_max_value = 120
    _attr_native_step = 1
    _attr_mode = "box"

    def __init__(self, coordinator: OpusCoordinator, device: Device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{DOMAIN}_{device.device_id}_rotation_time"

    @property
    def native_value(self) -> float | None:
        """Return the current configured rotation time."""
        device = self.device
        if device is None:
            return None
        value = device.get_configuration_parameter_value("rotationTime")
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set the configured rotation time."""
        await self.coordinator.client.set_device_configuration_parameter(
            self._device_id,
            "rotationTime",
            int(value),
        )

        device = self.device
        if device is not None:
            parameter = device.get_configuration_parameter("rotationTime")
            if parameter is not None:
                parameter.value = float(value)

        self.async_write_ha_state()
