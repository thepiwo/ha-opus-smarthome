"""Climate platform for OPUS SmartHome heating zones."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from pyopus_smarthome import Device
from pyopus_smarthome.models import EEP_HEATCONTROLLER

from .const import DOMAIN
from .coordinator import OpusCoordinator
from .entity import OpusBaseEntity

MIN_TEMP = 6.0
MAX_TEMP = 30.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OPUS climate entities."""
    coordinator: OpusCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        OpusClimate(coordinator, device)
        for device in coordinator.data.values()
        if device.is_climate and not device.is_heat_controller
    ]
    async_add_entities(entities)


class OpusClimate(OpusBaseEntity, ClimateEntity):
    """Representation of an OPUS heating zone."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_name = None  # Use device name directly

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        device = self.device
        if device is None:
            return None
        temp = device.get_state("temperature")
        return float(temp) if temp is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature setpoint."""
        device = self.device
        if device is None:
            return None
        setpoint = device.get_state("temperatureSetpoint")
        return float(setpoint) if setpoint is not None else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode based on setpoint."""
        device = self.device
        if device is None:
            return HVACMode.OFF
        setpoint = device.get_state("temperatureSetpoint")
        if setpoint is not None and float(setpoint) <= MIN_TEMP:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def available(self) -> bool:
        """Return False if missingData=error (stale sensor)."""
        if not super().available:
            return False
        device = self.device
        if device is None:
            return False
        missing = device.get_state("missingData")
        return missing != "error"

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.coordinator.client.set_state(
                self._device_id, "temperatureSetpoint", temp
            )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode by adjusting the setpoint.

        The OPUS gateway does not support setting heaterMode on individual
        zones. OFF is simulated by setting the setpoint to the minimum.
        """
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.client.set_state(
                self._device_id, "temperatureSetpoint", MIN_TEMP
            )
