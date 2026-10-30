# Derived from hass-gocoax (Apache-2.0, https://github.com/homeassistant-projects/hass-gocoax);
# modified for Kiwee Broadband MoCA adapters. See NOTICE.
"""Data models for Kiwee Broadband MoCA adapter responses."""

from dataclasses import dataclass, field


@dataclass
class PacketStats:
    """Packet statistics for tx/rx."""

    ok: int = 0
    bad: int = 0
    dropped: int = 0


@dataclass
class EthernetPackets:
    """Ethernet packet statistics."""

    tx: PacketStats = field(default_factory=PacketStats)
    rx: PacketStats = field(default_factory=PacketStats)


@dataclass
class NetworkPeer:
    """Information about a peer on the MoCA network."""

    node_id: int
    mac_address: str
    moca_version: str
    tx_phy_rate: int = 0  # Mbps
    rx_phy_rate: int = 0  # Mbps
    tx_good: int = 0  # TX good packets towards this node
    is_nc: bool = False  # this node is the network controller


@dataclass
class PhyRate:
    """PHY rate between two adapters."""

    source_mac: str
    target_mac: str
    tx_rate: int  # Mbps
    rx_rate: int  # Mbps


@dataclass
class AdapterStatus:
    """Complete status of a Kiwee Broadband MoCA adapter."""

    mac_address: str
    ip_address: str
    moca_version: str
    link_status: bool  # True = up, False = down
    adapter_name: str | None = None
    firmware_version: str | None = None
    model: str | None = None
    packets: EthernetPackets = field(default_factory=EthernetPackets)
    network_peers: list[NetworkPeer] = field(default_factory=list)
    phy_rates: list[PhyRate] = field(default_factory=list)
    node_id: int = 0
    network_controller: bool = False  # True if this node is the NC
    # new fields for enhanced monitoring
    frequency_band: str | None = None  # e.g., "D-Low", "D-High", "Extended-D"
    lof: int | None = None  # Lowest Operating Frequency in MHz
    channel_count: int | None = None  # number of bonded channels
    nc_node_id: int | None = None  # network controller node ID
    preferred_nc: bool | None = None  # "Preferred NC" setting
    tx_power: int | None = None  # "Tx Power" setting
    beacon_power: int | None = None  # "Beacon Power Level" setting
    beacon_channel: int | None = None  # MHz
    primary_channel: int | None = None  # MHz
    secondary_channel: int | None = None  # MHz
    first_channel: int | None = None  # MHz

    @property
    def peer_count(self) -> int:
        """Return count of network peers."""
        return len(self.network_peers)

    def to_dict(self) -> dict:
        """Convert to dictionary for diagnostics."""
        return {
            "mac_address": self.mac_address,
            "ip_address": self.ip_address,
            "moca_version": self.moca_version,
            "link_status": "up" if self.link_status else "down",
            "adapter_name": self.adapter_name,
            "firmware_version": self.firmware_version,
            "model": self.model,
            "node_id": self.node_id,
            "nc_node_id": self.nc_node_id,
            "network_controller": self.network_controller,
            "frequency_band": self.frequency_band,
            "lof": self.lof,
            "preferred_nc": self.preferred_nc,
            "tx_power": self.tx_power,
            "beacon_power": self.beacon_power,
            "beacon_channel": self.beacon_channel,
            "primary_channel": self.primary_channel,
            "secondary_channel": self.secondary_channel,
            "first_channel": self.first_channel,
            "channel_count": self.channel_count,
            "packets": {
                "tx": {
                    "ok": self.packets.tx.ok,
                    "bad": self.packets.tx.bad,
                    "dropped": self.packets.tx.dropped,
                },
                "rx": {
                    "ok": self.packets.rx.ok,
                    "bad": self.packets.rx.bad,
                    "dropped": self.packets.rx.dropped,
                },
            },
            "network_peers": [
                {
                    "node_id": peer.node_id,
                    "mac_address": peer.mac_address,
                    "moca_version": peer.moca_version,
                    "tx_phy_rate": peer.tx_phy_rate,
                    "rx_phy_rate": peer.rx_phy_rate,
                    "tx_good": peer.tx_good,
                    "is_nc": peer.is_nc,
                }
                for peer in self.network_peers
            ],
            "phy_rates": [
                {
                    "source_mac": rate.source_mac,
                    "target_mac": rate.target_mac,
                    "tx_rate": rate.tx_rate,
                    "rx_rate": rate.rx_rate,
                }
                for rate in self.phy_rates
            ],
        }
