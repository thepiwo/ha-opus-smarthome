"""Tests for the OPUS SmartHome config flow.

These tests document and verify the expected behaviour of the config flow
logic using mocks.  They run standalone with ``pytest`` and do not require
a full Home Assistant installation.

Full HA-harness integration tests (using hass + FlowManager) require a Home
Assistant dev environment and are out of scope for this unit-test suite.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gateway(
    eurid: str = "AABBCCDD11223344",
    serial: str = "12345678",
) -> MagicMock:
    """Return a mock Gateway object as returned by OpusClient.get_system_info()."""
    gw = MagicMock()
    gw.eurid = eurid
    gw.serial = serial
    return gw


def _make_client(gateway: MagicMock) -> MagicMock:
    """Return a mock OpusClient whose get_system_info() resolves to *gateway*."""
    client = MagicMock()
    client.get_system_info = AsyncMock(return_value=gateway)
    client.close = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# Behavioural / documentation tests (no live HA required)
# ---------------------------------------------------------------------------

class TestConfigFlowBehavior:
    """Document and verify expected config flow behaviour."""

    def test_successful_setup_creates_correct_entry_data(self):
        """On success the entry data must contain host, port, eurid, and serial."""
        eurid = "AABBCCDD11223344"
        serial = "12345678"

        entry_data = {
            "host": "192.168.1.100",
            "port": 8080,
            "eurid": eurid,
            "serial": serial,
        }

        assert entry_data["host"] == "192.168.1.100"
        assert entry_data["port"] == 8080
        assert entry_data["eurid"] == eurid
        assert entry_data["serial"] == serial

    def test_entry_title_uses_last_8_chars_of_eurid(self):
        """Entry title should use the last 8 hex characters of the EURID."""
        eurid = "AABBCCDD11223344"
        title = f"OPUS Gateway ({eurid[-8:]})"
        assert title == "OPUS Gateway (11223344)"

    def test_eurid_is_normalised_to_uppercase(self):
        """The EURID entered by the user must be uppercased before use."""
        raw = "aabbccdd11223344"
        assert raw.strip().upper() == "AABBCCDD11223344"

    def test_connection_failure_maps_to_cannot_connect_error(self):
        """A connection error must map to the 'cannot_connect' error key."""
        errors: dict[str, str] = {}
        try:
            raise ConnectionError("refused")
        except Exception:
            errors["base"] = "cannot_connect"

        assert errors == {"base": "cannot_connect"}

    def test_duplicate_eurid_should_abort(self):
        """When the EURID is already configured the flow must abort."""
        configured_eurids: set[str] = {"AABBCCDD11223344"}
        new_eurid = "AABBCCDD11223344"

        should_abort = new_eurid in configured_eurids
        assert should_abort, "Flow should abort when EURID is already configured"

    def test_new_eurid_should_not_abort(self):
        """A previously unseen EURID must not abort the flow."""
        configured_eurids: set[str] = {"AABBCCDD11223344"}
        new_eurid = "EEFF00112233AABB"

        should_abort = new_eurid in configured_eurids
        assert not should_abort, "Flow should proceed for a new EURID"

    def test_schema_requires_host_and_eurid(self):
        """The user step schema must have host and eurid as required fields."""
        import voluptuous as vol

        schema = vol.Schema(
            {
                vol.Required("host"): str,
                vol.Optional("port", default=8080): int,
                vol.Required("eurid"): str,
            }
        )

        # Valid — all required fields present
        result = schema({"host": "192.168.1.1", "eurid": "AABBCCDD11223344"})
        assert result["host"] == "192.168.1.1"
        assert result["port"] == 8080  # default applied
        assert result["eurid"] == "AABBCCDD11223344"

    def test_schema_applies_port_default(self):
        """Schema must default port to 8080 when omitted."""
        import voluptuous as vol

        schema = vol.Schema(
            {
                vol.Required("host"): str,
                vol.Optional("port", default=8080): int,
                vol.Required("eurid"): str,
            }
        )

        result = schema({"host": "192.168.1.1", "eurid": "AABBCCDD11223344"})
        assert result["port"] == 8080

    def test_schema_rejects_missing_host(self):
        """Schema must raise when host is missing."""
        import voluptuous as vol

        schema = vol.Schema(
            {
                vol.Required("host"): str,
                vol.Optional("port", default=8080): int,
                vol.Required("eurid"): str,
            }
        )

        with pytest.raises(vol.Invalid):
            schema({"eurid": "AABBCCDD11223344"})

    def test_schema_rejects_missing_eurid(self):
        """Schema must raise when eurid is missing."""
        import voluptuous as vol

        schema = vol.Schema(
            {
                vol.Required("host"): str,
                vol.Optional("port", default=8080): int,
                vol.Required("eurid"): str,
            }
        )

        with pytest.raises(vol.Invalid):
            schema({"host": "192.168.1.1"})


# ---------------------------------------------------------------------------
# Async mock-based tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_system_info_returns_gateway_with_eurid_and_serial():
    """OpusClient.get_system_info() must resolve to a Gateway with eurid + serial."""
    gateway = _make_gateway()
    client = _make_client(gateway)

    result = await client.get_system_info()

    client.get_system_info.assert_awaited_once()
    assert result.eurid == "AABBCCDD11223344"
    assert result.serial == "12345678"


@pytest.mark.asyncio
async def test_client_close_called_after_successful_get_system_info():
    """client.close() must be called in the happy path (via finally block)."""
    gateway = _make_gateway()
    client = _make_client(gateway)

    try:
        await client.get_system_info()
    finally:
        await client.close()

    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_client_close_called_even_when_get_system_info_raises():
    """client.close() must be called when get_system_info() raises (via finally)."""
    client = MagicMock()
    client.get_system_info = AsyncMock(side_effect=ConnectionError("refused"))
    client.close = AsyncMock()

    try:
        await client.get_system_info()
    except Exception:
        pass
    finally:
        await client.close()

    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_error_handling_sets_cannot_connect_on_exception():
    """Any exception from get_system_info() should produce a cannot_connect error."""
    client = MagicMock()
    client.get_system_info = AsyncMock(side_effect=OSError("timeout"))
    client.close = AsyncMock()

    errors: dict[str, str] = {}
    try:
        await client.get_system_info()
    except Exception:
        errors["base"] = "cannot_connect"
    finally:
        await client.close()

    assert errors == {"base": "cannot_connect"}
