# Derived from hass-gocoax (Apache-2.0, https://github.com/homeassistant-projects/hass-gocoax);
# modified for Kiwee Broadband MoCA adapters. See NOTICE.
"""Diagnostics support for Kiwee Broadband MoCA integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import KiweeConfigEntry

# keys to redact from diagnostics output
TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "mac_address",
    "source_mac",
    "target_mac",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: KiweeConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # build diagnostics data
    diagnostics_data: dict[str, Any] = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "host": entry.data.get(CONF_HOST),
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
        },
    }

    # add adapter data if available
    if coordinator.data:
        adapter_data = coordinator.data.to_dict()
        diagnostics_data["adapter"] = async_redact_data(adapter_data, TO_REDACT)

    return diagnostics_data
