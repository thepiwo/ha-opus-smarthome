DOMAIN = "opus_smarthome"
PLATFORMS = ["cover", "climate", "sensor", "binary_sensor", "event", "number"]
DEFAULT_PORT = 8080

# Per-zone room temperature correction, stored in the config entry options as
# {device_id: offset}. Added to the reported temperature, subtracted from the
# setpoint sent to the gateway.
CONF_TEMPERATURE_OFFSETS = "temperature_offsets"
TEMPERATURE_OFFSET_MIN = -5.0
TEMPERATURE_OFFSET_MAX = 5.0
