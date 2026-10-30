# Derived from hass-gocoax (Apache-2.0, https://github.com/homeassistant-projects/hass-gocoax);
# modified for Kiwee Broadband MoCA adapters. See NOTICE.
"""pykiwee - Async Python client library for Kiwee Broadband MoCA adapters."""

from .client import KiweeClient
from .exceptions import (
    KiweeAuthError,
    KiweeConnectionError,
    KiweeError,
    KiweeParseError,
    KiweeTimeoutError,
)
from .models import (
    AdapterStatus,
    EthernetPackets,
    NetworkPeer,
    PacketStats,
    PhyRate,
)

__all__ = [
    "KiweeClient",
    "AdapterStatus",
    "EthernetPackets",
    "NetworkPeer",
    "PacketStats",
    "PhyRate",
    "KiweeError",
    "KiweeAuthError",
    "KiweeConnectionError",
    "KiweeParseError",
    "KiweeTimeoutError",
]
