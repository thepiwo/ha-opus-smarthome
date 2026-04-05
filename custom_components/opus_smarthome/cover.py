"""Cover platform for OPUS SmartHome roller shutters."""
from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
)
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
    """Set up OPUS cover entities."""
    coordinator: OpusCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        OpusCover(coordinator, device)
        for device in coordinator.data.values()
        if device.is_cover
    ]
    async_add_entities(entities)


class OpusCover(OpusBaseEntity, CoverEntity):
    """Representation of an OPUS roller shutter."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _base_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.STOP
    )
    _attr_name = None  # Use device name directly

    def __init__(self, coordinator: OpusCoordinator, device: Device) -> None:
        """Initialize the cover with features derived from device capabilities."""
        super().__init__(coordinator, device)
        self._attr_supported_features = self._base_supported_features
        if device.supports_cover_tilt:
            self._attr_supported_features |= CoverEntityFeature.SET_TILT_POSITION

    @property
    def current_cover_position(self) -> int | None:
        """Return current position (HA: 0=closed, 100=open)."""
        device = self.device
        if device is None:
            return None
        pos = device.get_state("position")
        if pos is None or pos == "unknown":
            return None
        # Invert: OPUS 0=open,100=closed → HA 0=closed,100=open
        return round(100 - float(pos))

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt/angle position."""
        device = self.device
        if device is None or not device.supports_cover_tilt:
            return None
        angle = device.get_state("angle")
        if angle is None or angle == "unknown":
            return None
        return round(100 - float(angle))

    @property
    def is_closed(self) -> bool | None:
        """Return True if the cover is fully closed."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    @property
    def is_opening(self) -> bool:
        """Return True if the cover is currently opening."""
        device = self.device
        if device is None:
            return False
        # During motor movement, position reports "unknown"
        # We can't distinguish opening vs closing from position alone
        # but HA needs these for UI states
        return False

    @property
    def is_closing(self) -> bool:
        """Return True if the cover is currently closing."""
        return False

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover (OPUS position=0)."""
        await self.coordinator.client.set_state(self._device_id, "position", 0)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover (OPUS position=100)."""
        await self.coordinator.client.set_state(self._device_id, "position", 100)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set cover position (invert HA→OPUS)."""
        ha_position = kwargs[ATTR_POSITION]
        opus_position = 100 - ha_position
        await self.coordinator.client.set_state(self._device_id, "position", opus_position)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set tilt position."""
        device = self.device
        if device is None or not device.supports_cover_tilt:
            return
        ha_tilt = kwargs[ATTR_TILT_POSITION]
        opus_angle = 100 - ha_tilt
        await self.coordinator.client.set_state(self._device_id, "angle", opus_angle)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop cover movement."""
        await self.coordinator.client.set_state(self._device_id, "stop", True)
