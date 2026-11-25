"""Per-zone temperature offsets kept in the config entry options."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import CONF_TEMPERATURE_OFFSETS


def get_temperature_offset(options: Mapping[str, Any], device_id: str) -> float:
    """Return the offset configured for *device_id*, 0.0 if none."""
    offsets = options.get(CONF_TEMPERATURE_OFFSETS) or {}
    try:
        return float(offsets.get(device_id, 0.0))
    except (TypeError, ValueError):
        return 0.0


def options_with_temperature_offset(
    options: Mapping[str, Any], device_id: str, offset: float
) -> dict[str, Any]:
    """Return a copy of *options* with the offset for *device_id* set.

    An offset of 0 removes the entry, so the options only list zones that are
    actually corrected.
    """
    offsets = dict(options.get(CONF_TEMPERATURE_OFFSETS) or {})
    offset = round(float(offset), 1)
    if offset == 0:
        offsets.pop(device_id, None)
    else:
        offsets[device_id] = offset
    return {**options, CONF_TEMPERATURE_OFFSETS: offsets}
