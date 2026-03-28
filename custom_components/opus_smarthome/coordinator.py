"""Push-mode coordinator for OPUS SmartHome."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from pyopus_smarthome import OpusClient, OpusStream, Device, Telegram

from .const import DOMAIN

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
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.client = client
        self._stream: OpusStream | None = None
        self._host = host
        self._eurid = eurid
        self._port = port

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
