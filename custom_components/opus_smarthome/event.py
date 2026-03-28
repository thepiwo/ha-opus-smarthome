"""Event platform for OPUS SmartHome doorbell."""
from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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
    """Set up OPUS event entities."""
    coordinator: OpusCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        OpusDoorbellEvent(coordinator, device)
        for device in coordinator.data.values()
        if device.is_doorbell
    ]
    async_add_entities(entities)


class OpusDoorbellEvent(OpusBaseEntity, EventEntity):
    """Representation of an OPUS doorbell event."""

    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = ["pressed"]
    _attr_name = None  # Use device name directly

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Check if the doorbell was pressed by looking for buttonBI=pressed
        in the device's current state. The coordinator updates device states
        from telegrams, so we check for the press event here.
        """
        device = self.device
        if device is None:
            super()._handle_coordinator_update()
            return

        button_state = device.get_state("buttonBI")
        if button_state == "pressed":
            device.update_state("buttonBI", None)  # consume the event
            self._trigger_event("pressed")
            self.async_write_ha_state()
        else:
            super()._handle_coordinator_update()
