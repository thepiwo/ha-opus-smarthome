"""Sensor platform for OPUS SmartHome temperature and humidity sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE
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
    """Set up OPUS sensor entities."""
    coordinator: OpusCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for device in coordinator.data.values():
        if device.is_sensor:
            entities.append(OpusTemperatureSensor(coordinator, device))
            entities.append(OpusHumiditySensor(coordinator, device))
    async_add_entities(entities)


class OpusTemperatureSensor(OpusBaseEntity, SensorEntity):
    """OPUS temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_name = "Temperature"

    def __init__(self, coordinator: OpusCoordinator, device: Device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{DOMAIN}_{device.device_id}_temperature"

    @property
    def native_value(self) -> float | None:
        device = self.device
        if device is None:
            return None
        temp = device.get_state("temperature")
        return float(temp) if temp is not None else None


class OpusHumiditySensor(OpusBaseEntity, SensorEntity):
    """OPUS humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_name = "Humidity"

    def __init__(self, coordinator: OpusCoordinator, device: Device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{DOMAIN}_{device.device_id}_humidity"

    @property
    def native_value(self) -> float | None:
        device = self.device
        if device is None:
            return None
        humidity = device.get_state("humidity")
        return float(humidity) if humidity is not None else None
