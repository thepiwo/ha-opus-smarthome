"""Device triggers for OPUS SmartHome."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.components.homeassistant import SERVICE_TRIGGER
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_EVENT_TYPE,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

# List of triggers for doorbell
DOORBELL_TRIGGERS = ["pressed"]

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(DOORBELL_TRIGGERS),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for OPUS SmartHome devices."""
    registry = er.async_get(hass)
    triggers = []

    # Get all entities for this device
    entries = er.async_entries_for_device(registry, device_id)

    for entry in entries:
        if entry.domain != EVENT_DOMAIN:
            continue
        
        # We only have one type of event entity so far (doorbell)
        # which supports 'pressed'
        for trigger_type in DOORBELL_TRIGGERS:
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: trigger_type,
                    "metadata": {},
                }
            )

    return triggers


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, Any]:
    """List trigger capabilities."""
    return {
        "extra_fields": vol.Schema(
            {
                vol.Optional(CONF_ENTITY_ID): cv.entity_id,
            }
        )
    }


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    return TRIGGER_SCHEMA(config)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    event_config = {
        CONF_PLATFORM: "event",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        CONF_EVENT_TYPE: config[CONF_TYPE],
    }
    
    # We use the standard event trigger platform
    from homeassistant.components.event import async_attach_trigger as async_attach_event_trigger
    
    return await async_attach_event_trigger(
        hass, event_config, action, trigger_info
    )
