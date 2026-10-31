# Derived from hass-gocoax (Apache-2.0, https://github.com/homeassistant-projects/hass-gocoax);
# modified for Kiwee Broadband MoCA adapters. See NOTICE.
"""Reboot button for Kiwee Broadband MoCA adapters."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KiweeConfigEntry
from .const import DOMAIN, MANUFACTURER_KIWEE
from .coordinator import KiweeCoordinator
from .pykiwee.exceptions import KiweeError


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KiweeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the reboot button."""
    async_add_entities([KiweeRebootButton(entry.runtime_data)])


class KiweeRebootButton(CoordinatorEntity[KiweeCoordinator], ButtonEntity):
    """Reboots the adapter.

    Disabled by default: rebooting the network controller interrupts every MoCA link
    (and anything that uses the controller as uplink) for up to a minute.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "reboot"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: KiweeCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        data = coordinator.data
        self._attr_unique_id = f"{coordinator.mac_address}_reboot"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.mac_address or coordinator.host)},
            connections={(CONNECTION_NETWORK_MAC, data.mac_address)} if data else set(),
            name=f"Kiwee Broadband {coordinator.host}",
            manufacturer=MANUFACTURER_KIWEE,
            model=data.model if data else None,
            sw_version=data.firmware_version if data else None,
            configuration_url=f"http://{coordinator.host}",
        )

    @property
    def available(self) -> bool:
        """Not pressable while the adapter is already restarting."""
        return super().available and not self.coordinator.rebooting

    async def async_press(self) -> None:
        """Reboot the adapter."""
        try:
            await self.coordinator.async_reboot()
        except KiweeError as err:
            raise HomeAssistantError(
                f"Could not reboot Kiwee Broadband at {self.coordinator.host}: {err}"
            ) from err
