"""Tests for the OPUS SmartHome doorbell event."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.opus_smarthome.event import OpusDoorbellEvent


def test_doorbell_event_unique_id():
    """Test the unique ID of the doorbell event."""
    coordinator = MagicMock()
    device = MagicMock()
    device.device_id = "12345"

    event = OpusDoorbellEvent(coordinator, device)
    assert event.unique_id == "opus_smarthome_12345_doorbell"


def test_doorbell_event_trigger():
    """Test that the doorbell event triggers when state changes to pressed."""
    coordinator = MagicMock()
    device = MagicMock()
    device.device_id = "12345"
    device.get_state.return_value = "pressed"
    coordinator.data = {device.device_id: device}

    event = OpusDoorbellEvent(coordinator, device)

    event._trigger_event = MagicMock()
    event.async_write_ha_state = MagicMock()

    event._handle_coordinator_update()

    event._trigger_event.assert_called_once_with("pressed")
    device.update_state.assert_called_once_with("buttonBI", None)
    event.async_write_ha_state.assert_called_once()


def test_doorbell_event_no_trigger():
    """Test that the doorbell event does not trigger when state is not pressed."""
    coordinator = MagicMock()
    device = MagicMock()
    device.device_id = "12345"
    device.get_state.return_value = "released"
    coordinator.data = {device.device_id: device}

    event = OpusDoorbellEvent(coordinator, device)
    event._trigger_event = MagicMock()
    event.async_write_ha_state = MagicMock()

    event._handle_coordinator_update()

    event._trigger_event.assert_not_called()
