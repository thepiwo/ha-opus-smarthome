"""Push-mode coordinator for OPUS SmartHome."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from pyopus_smarthome import OpusClient, OpusStream, Device, Telegram

from .const import DOMAIN
from .offsets import get_temperature_offset, options_with_temperature_offset

if TYPE_CHECKING:
    from .ezr import EzrCoordinator

_LOGGER = logging.getLogger(__name__)


class OpusCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Coordinator that manages OPUS devices via push updates."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: OpusClient,
        host: str,
        eurid: str,
        port: int,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
        )
        self.client = client
        self._stream: OpusStream | None = None
        self._host = host
        self._eurid = eurid
        self._port = port
        self.ezr: EzrCoordinator | None = None

    def temperature_offset(self, device_id: str) -> float:
        """Return the temperature offset configured for a heating zone."""
        if self.config_entry is None:
            return 0.0
        return get_temperature_offset(self.config_entry.options, device_id)

    @callback
    def set_temperature_offset(self, device_id: str, offset: float) -> None:
        """Store a zone's temperature offset and refresh its entities."""
        if self.config_entry is None:
            return
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options=options_with_temperature_offset(
                self.config_entry.options, device_id, offset
            ),
        )
        self.async_update_listeners()

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch initial device list from the gateway."""
        devices = await self.client.get_devices()
        return {d.device_id: d for d in devices}

    async def start_stream(self) -> None:
        """Start the NDJSON event stream for real-time push updates."""
        self._stream = OpusStream(
            self._host,
            eurid=self._eurid,
            port=self._port,
            on_devices=self._handle_devices,
            on_telegram=self._handle_telegram,
        )
        await self._stream.start()

    async def stop_stream(self) -> None:
        """Stop the event stream."""
        if self._stream:
            await self._stream.stop()
            self._stream = None

    @callback
    def _handle_devices(self, devices: list[Device]) -> None:
        """Handle full device list from stream (initial + reconnect)."""
        self.async_set_updated_data({d.device_id: d for d in devices})

    @callback
    def _handle_telegram(self, telegram: Telegram) -> None:
        """Handle individual telegram — update device state and notify entities."""
        if self.data is None:
            return

        device = self.data.get(telegram.device_id)
        if device is None:
            return

        for fn in telegram.functions:
            device.update_state(fn.key, fn.value)

        # Notify all listeners that data has changed
        self.async_set_updated_data(self.data)
