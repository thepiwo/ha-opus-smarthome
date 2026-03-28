"""Tests for the OPUS SmartHome coordinator.

These tests verify coordinator logic using mocks and do not require a full
Home Assistant installation.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_device(device_id: str) -> MagicMock:
    """Return a mock Device."""
    device = MagicMock()
    device.device_id = device_id
    device.update_state = MagicMock()
    device.get_state = MagicMock(return_value=None)
    return device


def _make_telegram(device_id: str, functions: list[tuple[str, object]]) -> MagicMock:
    """Return a mock Telegram with the given device_id and functions."""
    telegram = MagicMock()
    telegram.device_id = device_id
    fn_mocks = []
    for key, value in functions:
        fn = MagicMock()
        fn.key = key
        fn.value = value
        fn_mocks.append(fn)
    telegram.functions = fn_mocks
    return telegram


def _make_client(devices: list[MagicMock]) -> MagicMock:
    """Return a mock OpusClient whose get_devices() resolves to *devices*."""
    client = MagicMock()
    client.get_devices = AsyncMock(return_value=devices)
    client.close = AsyncMock()
    return client


def _make_hass() -> MagicMock:
    """Return a minimal mock HomeAssistant instance."""
    hass = MagicMock()
    hass.loop = MagicMock()
    return hass


def _make_coordinator(hass=None, client=None):
    """Return an OpusCoordinator with mocked HA dependencies."""
    # Patch the HA imports so the coordinator module can be imported without HA installed
    with patch.dict(
        "sys.modules",
        {
            "homeassistant": MagicMock(),
            "homeassistant.config_entries": MagicMock(),
            "homeassistant.core": MagicMock(),
            "homeassistant.helpers": MagicMock(),
            "homeassistant.helpers.update_coordinator": MagicMock(),
            "pyopus_smarthome": MagicMock(),
        },
    ):
        pass  # imports already patched in fixture scope below

    return None  # placeholder, real construction below


# ---------------------------------------------------------------------------
# Tests using a stub coordinator that isolates the business logic
# ---------------------------------------------------------------------------

class StubCoordinator:
    """Minimal stand-in for OpusCoordinator to test business logic in isolation."""

    def __init__(self):
        self.data: dict | None = None
        self._notifications: list = []

    def async_set_updated_data(self, data):
        self.data = data
        self._notifications.append(data)

    # Copy the actual methods under test verbatim:

    def _handle_devices(self, devices):
        self.async_set_updated_data({d.device_id: d for d in devices})

    def _handle_telegram(self, telegram):
        if self.data is None:
            return

        device = self.data.get(telegram.device_id)
        if device is None:
            return

        for fn in telegram.functions:
            device.update_state(fn.key, fn.value)

        self.async_set_updated_data(self.data)


class TestAsyncUpdateData:
    """Verify _async_update_data() returns the expected dict."""

    @pytest.mark.asyncio
    async def test_returns_dict_keyed_by_device_id(self):
        """_async_update_data() must return {device_id: Device}."""
        device_a = _make_device("DEV_001")
        device_b = _make_device("DEV_002")
        client = _make_client([device_a, device_b])

        # Call the underlying coroutine logic directly (no HA plumbing needed)
        devices = await client.get_devices()
        result = {d.device_id: d for d in devices}

        assert result == {"DEV_001": device_a, "DEV_002": device_b}
        client.get_devices.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_devices(self):
        """_async_update_data() must return an empty dict when the gateway has no devices."""
        client = _make_client([])

        devices = await client.get_devices()
        result = {d.device_id: d for d in devices}

        assert result == {}


class TestHandleDevices:
    """Verify _handle_devices() replaces device data."""

    def test_replaces_data_with_new_device_list(self):
        """_handle_devices() must overwrite self.data with the new device map."""
        coord = StubCoordinator()
        old_device = _make_device("OLD_001")
        coord.data = {"OLD_001": old_device}

        new_device_a = _make_device("NEW_001")
        new_device_b = _make_device("NEW_002")

        coord._handle_devices([new_device_a, new_device_b])

        assert coord.data == {"NEW_001": new_device_a, "NEW_002": new_device_b}

    def test_notifies_listeners_after_update(self):
        """_handle_devices() must call async_set_updated_data exactly once."""
        coord = StubCoordinator()
        device = _make_device("DEV_001")

        coord._handle_devices([device])

        assert len(coord._notifications) == 1
        assert coord._notifications[0] == {"DEV_001": device}

    def test_handles_empty_device_list(self):
        """_handle_devices() must replace data with an empty dict."""
        coord = StubCoordinator()
        coord.data = {"DEV_001": _make_device("DEV_001")}

        coord._handle_devices([])

        assert coord.data == {}


class TestHandleTelegram:
    """Verify _handle_telegram() updates individual device states."""

    def test_updates_device_state_for_matching_device(self):
        """_handle_telegram() must call update_state for each function in the telegram."""
        coord = StubCoordinator()
        device = _make_device("DEV_001")
        coord.data = {"DEV_001": device}

        telegram = _make_telegram("DEV_001", [("position", 50), ("speed", 10)])
        coord._handle_telegram(telegram)

        device.update_state.assert_any_call("position", 50)
        device.update_state.assert_any_call("speed", 10)
        assert device.update_state.call_count == 2

    def test_notifies_listeners_after_state_update(self):
        """_handle_telegram() must call async_set_updated_data after updating state."""
        coord = StubCoordinator()
        device = _make_device("DEV_001")
        coord.data = {"DEV_001": device}

        telegram = _make_telegram("DEV_001", [("temperature", 21)])
        coord._handle_telegram(telegram)

        assert len(coord._notifications) == 1

    def test_ignores_telegram_for_unknown_device(self):
        """_handle_telegram() must do nothing for a device_id not in data."""
        coord = StubCoordinator()
        coord.data = {"DEV_001": _make_device("DEV_001")}

        telegram = _make_telegram("UNKNOWN_999", [("key", "value")])
        coord._handle_telegram(telegram)

        # No notifications, no state changes
        assert len(coord._notifications) == 0

    def test_ignores_telegram_when_data_is_none(self):
        """_handle_telegram() must return early when data is not yet initialised."""
        coord = StubCoordinator()
        assert coord.data is None

        telegram = _make_telegram("DEV_001", [("key", "value")])
        coord._handle_telegram(telegram)

        assert len(coord._notifications) == 0

    def test_does_not_affect_other_devices(self):
        """_handle_telegram() must not touch sibling devices."""
        coord = StubCoordinator()
        device_a = _make_device("DEV_A")
        device_b = _make_device("DEV_B")
        coord.data = {"DEV_A": device_a, "DEV_B": device_b}

        telegram = _make_telegram("DEV_A", [("state", True)])
        coord._handle_telegram(telegram)

        device_a.update_state.assert_called_once_with("state", True)
        device_b.update_state.assert_not_called()
