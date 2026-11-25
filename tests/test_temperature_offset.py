"""Tests for per-zone temperature offsets."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyopus_smarthome import Device

from custom_components.opus_smarthome.climate import MAX_TEMP, MIN_TEMP, OpusClimate
from custom_components.opus_smarthome.const import CONF_TEMPERATURE_OFFSETS
from custom_components.opus_smarthome.coordinator import OpusCoordinator
from custom_components.opus_smarthome.number import OpusTemperatureOffsetNumber
from custom_components.opus_smarthome.offsets import (
    get_temperature_offset,
    options_with_temperature_offset,
)

ZONE = "FFAA0101"


def _zone(temperature: float | None = 20.0, setpoint: float = 21.0) -> Device:
    states = [{"key": "temperatureSetpoint", "value": setpoint}]
    if temperature is not None:
        states.append({"key": "temperature", "value": temperature})
    return Device.from_dict(
        {
            "deviceId": ZONE,
            "friendlyId": "Room",
            "eeps": [{"eep": "D1-4B-04"}],
            "deviceType": "Heatarea",
            "states": states,
        }
    )


def _coordinator(device: Device, offset: float = 0.0) -> MagicMock:
    offsets = {ZONE: offset}
    coordinator = MagicMock()
    coordinator.data = {device.device_id: device}
    coordinator.last_update_success = True
    coordinator.temperature_offset = lambda device_id: offsets.get(device_id, 0.0)
    coordinator.set_temperature_offset = lambda device_id, value: offsets.__setitem__(
        device_id, value
    )
    coordinator.client.set_state = AsyncMock()
    return coordinator


# --- options helpers -------------------------------------------------------


def test_offset_defaults_to_zero() -> None:
    assert get_temperature_offset({}, ZONE) == 0.0
    assert get_temperature_offset({CONF_TEMPERATURE_OFFSETS: {"OTHER": 1.0}}, ZONE) == 0.0


def test_offset_set_rounds_and_keeps_other_options() -> None:
    options = {"unrelated": True, CONF_TEMPERATURE_OFFSETS: {"OTHER": 0.5}}
    new = options_with_temperature_offset(options, ZONE, -0.8000001)
    assert new == {"unrelated": True, CONF_TEMPERATURE_OFFSETS: {"OTHER": 0.5, ZONE: -0.8}}
    assert options[CONF_TEMPERATURE_OFFSETS] == {"OTHER": 0.5}  # not mutated
    assert get_temperature_offset(new, ZONE) == -0.8


def test_offset_zero_removes_entry() -> None:
    options = {CONF_TEMPERATURE_OFFSETS: {ZONE: -0.8}}
    assert options_with_temperature_offset(options, ZONE, 0.0) == {
        CONF_TEMPERATURE_OFFSETS: {}
    }


def test_offset_ignores_garbage() -> None:
    assert get_temperature_offset({CONF_TEMPERATURE_OFFSETS: {ZONE: "x"}}, ZONE) == 0.0


# --- climate ---------------------------------------------------------------


def test_climate_without_offset_is_unchanged() -> None:
    device = _zone(20.4, 21.0)
    climate = OpusClimate(_coordinator(device), device)
    assert climate.current_temperature == 20.4
    assert climate.target_temperature == 21.0


def test_climate_applies_offset_to_current_and_target() -> None:
    device = _zone(20.0, 21.8)
    climate = OpusClimate(_coordinator(device, -0.8), device)
    assert climate.current_temperature == pytest.approx(19.2)
    assert climate.target_temperature == pytest.approx(21.0)


def test_climate_off_setpoint_is_not_shifted() -> None:
    device = _zone(20.0, MIN_TEMP)
    climate = OpusClimate(_coordinator(device, -0.8), device)
    assert climate.target_temperature == MIN_TEMP


def test_climate_missing_temperature() -> None:
    device = _zone(None)
    climate = OpusClimate(_coordinator(device, -0.8), device)
    assert climate.current_temperature is None


@pytest.mark.parametrize(
    ("offset", "requested", "sent"),
    [
        (0.0, 21.0, 21.0),
        (-0.8, 21.0, 21.8),
        (0.5, 21.0, 20.5),
        (-0.8, MIN_TEMP, MIN_TEMP),  # off stays off
        (1.0, 6.5, MIN_TEMP + 0.5),  # an offset never switches a zone off
        (-1.0, MAX_TEMP, MAX_TEMP),  # clamped to the gateway range
    ],
)
async def test_climate_set_temperature_sends_gateway_setpoint(
    offset: float, requested: float, sent: float
) -> None:
    device = _zone()
    coordinator = _coordinator(device, offset)
    climate = OpusClimate(coordinator, device)
    await climate.async_set_temperature(temperature=requested)
    coordinator.client.set_state.assert_awaited_once_with(
        ZONE, "temperatureSetpoint", pytest.approx(sent)
    )


# --- number ----------------------------------------------------------------


async def test_offset_number_reads_and_writes_coordinator() -> None:
    device = _zone()
    coordinator = _coordinator(device, -0.8)
    number = OpusTemperatureOffsetNumber(coordinator, device)
    assert number.unique_id == f"opus_smarthome_{ZONE}_temperature_offset"
    assert number.native_value == -0.8
    await number.async_set_native_value(0.4)
    assert number.native_value == 0.4


def test_offset_number_available_without_device() -> None:
    device = _zone()
    coordinator = _coordinator(device)
    coordinator.data = {}
    assert OpusTemperatureOffsetNumber(coordinator, device).available is True


# --- coordinator storage -----------------------------------------------------


def test_coordinator_stores_offset_in_entry_options() -> None:
    entry = SimpleNamespace(options={CONF_TEMPERATURE_OFFSETS: {ZONE: 0.3}})
    fake = MagicMock()
    fake.config_entry = entry
    fake.hass.config_entries.async_update_entry = MagicMock(
        side_effect=lambda e, options: setattr(e, "options", options)
    )

    assert OpusCoordinator.temperature_offset(fake, ZONE) == 0.3
    OpusCoordinator.set_temperature_offset(fake, ZONE, -1.0)
    assert entry.options == {CONF_TEMPERATURE_OFFSETS: {ZONE: -1.0}}
    fake.async_update_listeners.assert_called_once()


def test_coordinator_without_entry_has_no_offset() -> None:
    fake = MagicMock()
    fake.config_entry = None
    assert OpusCoordinator.temperature_offset(fake, ZONE) == 0.0
    OpusCoordinator.set_temperature_offset(fake, ZONE, 1.0)
    fake.hass.config_entries.async_update_entry.assert_not_called()
