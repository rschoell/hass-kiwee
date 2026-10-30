# Derived from hass-gocoax (Apache-2.0, https://github.com/homeassistant-projects/hass-gocoax);
# modified for Kiwee Broadband MoCA adapters. See NOTICE.
"""Kiwee Broadband MoCA Integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN as DOMAIN
from .const import PLATFORMS
from .coordinator import KiweeCoordinator

LOG = logging.getLogger(__name__)

type KiweeConfigEntry = ConfigEntry[KiweeCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: KiweeConfigEntry) -> bool:
    """Set up Kiwee Broadband MoCA from a config entry."""
    host = entry.data[CONF_HOST]
    LOG.debug(f"Setting up Kiwee Broadband integration for {host}")

    # create coordinator
    coordinator = KiweeCoordinator(hass, entry)

    # fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # store coordinator in runtime data
    entry.runtime_data = coordinator

    # register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    # forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    LOG.info(f"Kiwee Broadband integration setup complete for {host}")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KiweeConfigEntry) -> bool:
    """Unload a Kiwee Broadband config entry."""
    host = entry.data[CONF_HOST]
    LOG.debug(f"Unloading Kiwee Broadband integration for {host}")

    # unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        LOG.info(f"Kiwee Broadband integration unloaded for {host}")

    return unload_ok


async def async_options_update_listener(
    hass: HomeAssistant, entry: KiweeConfigEntry
) -> None:
    """Handle options update."""
    LOG.debug(f"Options updated for Kiwee Broadband {entry.data[CONF_HOST]}, reloading")
    await hass.config_entries.async_reload(entry.entry_id)
