"""Number platform for OPUS SmartHome device configuration."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from pyopus_smarthome import Device

from .const import DOMAIN, TEMPERATURE_OFFSET_MAX, TEMPERATURE_OFFSET_MIN
from .coordinator import OpusCoordinator
from .entity import OpusBaseEntity
from .ezr import EzrBaseEntity, EzrCoordinator


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
        if device.is_climate and not device.is_heat_controller:
            entities.append(OpusTemperatureOffsetNumber(coordinator, device))
    ezr = coordinator.ezr
    controller = (
        coordinator.data.get(ezr.controller_device_id) if ezr is not None else None
    )
    if ezr is not None and controller is not None:
        entities.append(EzrEmergencyHeatNumber(ezr, controller))
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


class OpusTemperatureOffsetNumber(OpusBaseEntity, NumberEntity):
    """Correction for a heating zone's room temperature sensor.

    Added to the temperature the zone reports and subtracted from the setpoint
    sent to the gateway, so the zone regulates on the corrected value. Stored
    in Home Assistant only; the gateway and its sensor are unchanged.
    """

    _attr_name = "Temperature offset"
    _attr_icon = "mdi:thermometer-check"
    # No temperature device class: this is a difference, which HA's unit
    # conversion would treat as an absolute temperature.
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = TEMPERATURE_OFFSET_MIN
    _attr_native_max_value = TEMPERATURE_OFFSET_MAX
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: OpusCoordinator, device: Device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{DOMAIN}_{device.device_id}_temperature_offset"

    @property
    def available(self) -> bool:
        """The offset lives in HA, so it stays editable while the zone is offline."""
        return True

    @property
    def native_value(self) -> float:
        return self.coordinator.temperature_offset(self._device_id)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.set_temperature_offset(self._device_id, value)


class EzrEmergencyHeatNumber(EzrBaseEntity, NumberEntity):
    """Duty cycle the controller uses for zones that lost their room unit.

    0 keeps such zones unheated (no frost protection); the controller default
    heats them regardless of the setpoint.
    """

    _attr_name = "Emergency heat"
    _attr_icon = "mdi:radiator"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: EzrCoordinator, device: Device) -> None:
        super().__init__(coordinator, device, "emergency_heat")

    @property
    def native_value(self) -> float | None:
        status = self.coordinator.data
        if status is None or status.emergency_heat_percent is None:
            return None
        return float(status.emergency_heat_percent)

    async def async_set_native_value(self, value: float) -> None:
        status = self.coordinator.data
        await self.coordinator.client.set_emergency_heat_percent(
            int(value),
            device_id=status.device_id if status is not None else None,
        )
        await self.coordinator.async_request_refresh()
