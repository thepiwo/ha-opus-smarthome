"""Tests for the Möhlenhoff EZR controller entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyopus_smarthome import Device, EzrStatus

from custom_components.opus_smarthome.binary_sensor import (
    EzrEmergencyModeBinarySensor,
    EzrPumpBinarySensor,
    EzrRelayBinarySensor,
    OpusMissingDataBinarySensor,
)
from custom_components.opus_smarthome.ezr import (
    find_ezr_host,
    find_heat_controller,
    heat_zone_devices,
)
from custom_components.opus_smarthome.number import EzrEmergencyHeatNumber
from custom_components.opus_smarthome.sensor import EzrValveSensor

STATIC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Devices><Device>
  <ID>EZR0TEST1</ID>
  <PUMP_OUTPUT><PUMP_ISACTIVE>1</PUMP_ISACTIVE></PUMP_OUTPUT>
  <RELAIS><RELAIS_ISACTIVE>0</RELAIS_ISACTIVE></RELAIS>
  <EMERGENCYMODE><EMERGENCYMODE_TIME>180</EMERGENCYMODE_TIME><PWMHEAT>25</PWMHEAT></EMERGENCYMODE>
  <HEATAREA nr="1"><HEATAREA_NAME>RBG1</HEATAREA_NAME><HEATAREA_STATE>0</HEATAREA_STATE></HEATAREA>
  <HEATAREA nr="2"><HEATAREA_NAME>RBG2</HEATAREA_NAME><HEATAREA_STATE>0</HEATAREA_STATE></HEATAREA>
  <HEATCTRL nr="1"><INUSE>1</INUSE><HEATAREA_NR>1</HEATAREA_NR><ACTOR_PERCENT>0</ACTOR_PERCENT></HEATCTRL>
  <HEATCTRL nr="2"><INUSE>1</INUSE><HEATAREA_NR>2</HEATAREA_NR><ACTOR_PERCENT>25</ACTOR_PERCENT></HEATCTRL>
  <IODEVICE nr="1"><HEATAREA_NR>1</HEATAREA_NR><SIGNALSTRENGTH>2</SIGNALSTRENGTH><IODEVICE_COMERROR>0</IODEVICE_COMERROR></IODEVICE>
  <IODEVICE nr="2"><HEATAREA_NR>2</HEATAREA_NR><SIGNALSTRENGTH>0</SIGNALSTRENGTH><IODEVICE_COMERROR>1</IODEVICE_COMERROR></IODEVICE>
</Device></Devices>
"""


def _heat_area(device_id: str, zone: int | None, missing: str | None = None) -> Device:
    states = [{"key": "temperatureSetpoint", "value": 6.0}]
    if missing is not None:
        states.append({"key": "missingData", "value": missing})
    data = {
        "deviceId": device_id,
        "friendlyId": f"Room {device_id}",
        "eeps": [{"eep": "D1-4B-04"}],
        "deviceType": "Heatarea",
        "states": states,
    }
    if zone is not None:
        data["physicalDevice"] = f"001122334455_{zone}"
    return Device.from_dict(data)


def _controller(ip: str | None = "192.168.1.50/24") -> Device:
    states = [{"key": "ipAddress", "value": ip}] if ip is not None else []
    return Device.from_dict(
        {
            "deviceId": "FFAA0001",
            "friendlyId": "Heating controller",
            "eeps": [{"eep": "D1-4B-02"}],
            "deviceType": "IP",
            "states": states,
        }
    )


def _devices(*devices: Device) -> dict[str, Device]:
    return {d.device_id: d for d in devices}


def _ezr_coordinator(status: EzrStatus | None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = status
    coordinator.last_update_success = status is not None
    coordinator.client.set_emergency_heat_percent = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def test_find_ezr_host_strips_prefix_length():
    assert find_ezr_host(_devices(_controller(), _heat_area("FFAA0002", 1))) == "192.168.1.50"


def test_find_ezr_host_without_controller():
    assert find_ezr_host(_devices(_heat_area("FFAA0002", 1))) is None


def test_find_ezr_host_without_address():
    assert find_ezr_host(_devices(_controller(ip=None))) is None


def test_find_heat_controller():
    controller = _controller()
    assert find_heat_controller(_devices(controller, _heat_area("FFAA0002", 1))) is controller


def test_heat_zone_devices_maps_zones_and_skips_unlinked():
    linked = _heat_area("FFAA0002", 3)
    unlinked = _heat_area("FFAA0003", None)
    result = heat_zone_devices(_devices(_controller(), linked, unlinked))
    assert result == [(linked, 3)]


# ---------------------------------------------------------------------------
# OPUS missing-data sensor
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("missing", "expected"),
    [("error", True), ("reset", False), (None, False)],
)
def test_missing_data_sensor(missing, expected):
    device = _heat_area("FFAA0002", 1, missing=missing)
    coordinator = MagicMock()
    coordinator.data = _devices(device)

    sensor = OpusMissingDataBinarySensor(coordinator, device)

    assert sensor.unique_id == "opus_smarthome_FFAA0002_missing_data"
    assert sensor.is_on is expected


# ---------------------------------------------------------------------------
# Controller entities
# ---------------------------------------------------------------------------


def test_emergency_mode_on_for_zone_with_lost_room_unit():
    coordinator = _ezr_coordinator(EzrStatus.from_xml(STATIC_XML))
    lost = EzrEmergencyModeBinarySensor(coordinator, _heat_area("FFAA0003", 2), 2)
    fine = EzrEmergencyModeBinarySensor(coordinator, _heat_area("FFAA0002", 1), 1)

    assert lost.unique_id == "opus_smarthome_FFAA0003_emergency_mode"
    assert lost.is_on is True
    assert fine.is_on is False
    assert lost.extra_state_attributes == {
        "zone": 2,
        "signal_strength": [0],
        "emergency_heat_percent": 25,
        "emergency_delay_minutes": 180,
    }


def test_zone_entity_unavailable_for_unknown_zone():
    coordinator = _ezr_coordinator(EzrStatus.from_xml(STATIC_XML))
    sensor = EzrEmergencyModeBinarySensor(coordinator, _heat_area("FFAA0009", 9), 9)
    assert sensor.available is False
    assert sensor.is_on is None


def test_zone_entity_unavailable_without_data():
    coordinator = _ezr_coordinator(None)
    sensor = EzrValveSensor(coordinator, _heat_area("FFAA0002", 1), 1)
    assert sensor.available is False
    assert sensor.native_value is None


def test_valve_sensor_reports_actuator_percent():
    coordinator = _ezr_coordinator(EzrStatus.from_xml(STATIC_XML))
    sensor = EzrValveSensor(coordinator, _heat_area("FFAA0003", 2), 2)
    assert sensor.unique_id == "opus_smarthome_FFAA0003_valve"
    assert sensor.native_value == 25


def test_pump_and_relay_sensors_attach_to_controller():
    coordinator = _ezr_coordinator(EzrStatus.from_xml(STATIC_XML))
    controller = _controller()

    pump = EzrPumpBinarySensor(coordinator, controller)
    relay = EzrRelayBinarySensor(coordinator, controller)

    assert pump.is_on is True
    assert relay.is_on is False
    assert pump.unique_id == "opus_smarthome_FFAA0001_pump"
    assert pump.device_info["identifiers"] == {("opus_smarthome", "FFAA0001")}


def test_emergency_heat_number_value():
    coordinator = _ezr_coordinator(EzrStatus.from_xml(STATIC_XML))
    number = EzrEmergencyHeatNumber(coordinator, _controller())
    assert number.native_value == 25.0


async def test_emergency_heat_number_sets_controller_value():
    coordinator = _ezr_coordinator(EzrStatus.from_xml(STATIC_XML))
    number = EzrEmergencyHeatNumber(coordinator, _controller())

    await number.async_set_native_value(0)

    coordinator.client.set_emergency_heat_percent.assert_awaited_once_with(
        0, device_id="EZR0TEST1"
    )
    coordinator.async_request_refresh.assert_awaited_once()
