# Derived from hass-gocoax (Apache-2.0, https://github.com/homeassistant-projects/hass-gocoax);
# modified for Kiwee Broadband MoCA adapters. See NOTICE.
"""Binary sensor platform for Kiwee Broadband MoCA integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KiweeConfigEntry
from .const import DOMAIN, MANUFACTURER_KIWEE
from .coordinator import KiweeCoordinator
from .pykiwee import AdapterStatus

LOG = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class KiweeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Kiwee Broadband binary sensor entity."""

    value_fn: Callable[[AdapterStatus], bool | None]
    extra_attrs_fn: Callable[[AdapterStatus], dict[str, Any]] | None = None


BINARY_SENSOR_DESCRIPTIONS: tuple[KiweeBinarySensorEntityDescription, ...] = (
    KiweeBinarySensorEntityDescription(
        key="link_status",
        translation_key="link_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.link_status,
    ),
    KiweeBinarySensorEntityDescription(
        key="network_controller",
        translation_key="network_controller",
        icon="mdi:crown",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.network_controller,
    ),
    KiweeBinarySensorEntityDescription(
        key="preferred_nc",
        translation_key="preferred_nc",
        icon="mdi:crown-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.preferred_nc,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: KiweeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kiwee Broadband binary sensor entities."""
    coordinator = entry.runtime_data

    entities: list[KiweeBinarySensor] = [
        KiweeBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class KiweeBinarySensor(CoordinatorEntity[KiweeCoordinator], BinarySensorEntity):
    """Binary sensor entity for Kiwee Broadband MoCA adapter."""

    entity_description: KiweeBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KiweeCoordinator,
        description: KiweeBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.mac_address}_{description.key}"
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> DeviceInfo:
        """Build device info for this sensor."""
        data = self.coordinator.data
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.coordinator.mac_address or self.coordinator.host)
            },
            connections={(CONNECTION_NETWORK_MAC, data.mac_address)} if data else set(),
            name=f"Kiwee Broadband {self.coordinator.host}",
            manufacturer=MANUFACTURER_KIWEE,
            model=data.model if data else None,
            sw_version=data.firmware_version if data else None,
            configuration_url=f"http://{self.coordinator.host}",
        )

    @property
    def is_on(self) -> bool | None:
        """Return the sensor state."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if not self.coordinator.data or not self.entity_description.extra_attrs_fn:
            return None
        return self.entity_description.extra_attrs_fn(self.coordinator.data)
