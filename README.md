# OPUS SmartHome for Home Assistant

A HACS custom component that integrates the OPUS SmartHome / OPUS greenNet gateway with Home Assistant. It provides real-time, push-based control and monitoring of OPUS-compatible devices using the local gateway API — no cloud, no polling.

Built on [`pyopus-smarthome`](https://github.com/thepiwo/pyopus-smarthome), an async Python client library for the OPUS gateway.

---

## Supported Devices

| Device Type | HA Platform | Notes |
|---|---|---|
| Roller shutters / blinds | `cover` | Position control, tilt for blinds |
| Floor heating (Möhlenhoff) | `climate` | Target temperature, current temp |
| Temperature / humidity sensors | `sensor` | °C and % RH |
| Doorbell | `event` | Push event on ring |

---

## Prerequisites

- OPUS SmartHome gateway (OPUS greenNet hub) reachable on your local network
- Home Assistant 2024.1 or newer
- [HACS](https://hacs.xyz/) installed

---

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations** and click the three-dot menu in the top right.
3. Select **Custom repositories**.
4. Enter `https://github.com/thepiwo/ha-opus-smarthome` and select category **Integration**, then click **Add**.
5. Search for **OPUS SmartHome** and install it.
6. Restart Home Assistant.

### Manual

1. Copy the `custom_components/opus_smarthome/` folder into your `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **OPUS SmartHome**.
3. Enter the **IP address** of your gateway (e.g. `192.168.1.100`).
4. Enter the **EURID** from the QR code label on the gateway (or use the [`opus-qr`](https://github.com/thepiwo/pyopus-smarthome) CLI tool to decode it).
5. Optionally adjust the port (default: `8080`).
6. Click **Submit**.

Credentials are derived automatically from the EURID — you do not need to enter a username or password.

---

## How It Works

The integration connects to the OPUS gateway over HTTP on your local network. Device state updates are delivered via a **Server-Sent Events (SSE) / NDJSON streaming** connection — the gateway pushes changes in real time as they happen. There is no polling interval; updates appear in Home Assistant within milliseconds of a physical change.

On startup the integration:
1. Connects to the gateway and derives credentials automatically.
2. Fetches the full device list and creates HA entities.
3. Opens a persistent streaming connection for live state updates.

If the connection drops (e.g. gateway reboot), the integration reconnects automatically with exponential back-off.

---

## Entities Created

### Cover (roller shutters / blinds)
- `cover.<name>` — open/close/stop, set position (0–100 %)
- Blinds also expose tilt position

### Climate (floor heating)
- `climate.<name>` — set target temperature, read current temperature
- Supports `heat` and `off` HVAC modes

### Sensor (temperature / humidity)
- `sensor.<name>_temperature` — current temperature in °C
- `sensor.<name>_humidity` — current relative humidity in %

### Event (doorbell)
- `event.<name>_doorbell` — fires a Home Assistant event on each ring

---

## Troubleshooting

### "Cannot connect to gateway"
- Verify the gateway IP address (`192.168.1.100`) is reachable from your Home Assistant host (`ping 192.168.1.100`).
- Check that port `8080` (or your configured port) is not blocked by a firewall.
- Confirm the gateway is powered on and the OPUS SmartHome app can reach it.

### Entities go unavailable after some time
- The gateway may have rebooted or dropped the connection. The integration will reconnect automatically; entities return to available once reconnection succeeds.
- If this happens frequently, check gateway stability and network reliability.

### Rate limiting
- Sending too many commands in rapid succession may cause the gateway to throttle requests temporarily. Space out automated actions by at least a few seconds.

### Credential derivation fails
- Credentials are derived from gateway-specific data fetched at setup time. If this step fails, ensure the gateway firmware is up to date and try re-adding the integration.

### Debug logging
Add the following to your `configuration.yaml` to enable verbose logs:

```yaml
logger:
  default: warning
  logs:
    custom_components.opus_smarthome: debug
```

---

## Contributing

Pull requests and issue reports are welcome. Please do not include real IP addresses, serial numbers, or EURIDs in any issues or pull requests.

---

## License

MIT
