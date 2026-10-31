# Derived from hass-gocoax (Apache-2.0, https://github.com/homeassistant-projects/hass-gocoax);
# modified for Kiwee Broadband MoCA adapters. See NOTICE.
"""Constants for the Kiwee Broadband MoCA integration."""

from typing import Final

DOMAIN: Final = "kiwee"

# configuration keys
CONF_HOST: Final = "host"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# defaults
DEFAULT_USERNAME: Final = "admin"
DEFAULT_PASSWORD: Final = "maxlinear"  # per KB-M3-02 manual
DEFAULT_SCAN_INTERVAL: Final = 30  # seconds
DEFAULT_TIMEOUT: Final = 15  # seconds
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 300

# manufacturers
MANUFACTURER_KIWEE: Final = "Kiwee Broadband"

# known models (KB-M3-02: MoCA 2.5, 2x 2.5 GbE, D-band; KB-M3-02E: Extended E-band)
MODELS: Final = {
    "KB-M3-02": {
        "manufacturer": MANUFACTURER_KIWEE,
        "moca": "2.5",
        "ethernet": "2 x 2.5 GbE",
    },
    "KB-M3-02E": {
        "manufacturer": MANUFACTURER_KIWEE,
        "moca": "2.5",
        "ethernet": "2 x 2.5 GbE",
    },
}

# platforms
PLATFORMS: Final = ["sensor", "binary_sensor", "button"]

# entity categories
ATTR_MAC_ADDRESS: Final = "mac_address"
ATTR_IP_ADDRESS: Final = "ip_address"
ATTR_MOCA_VERSION: Final = "moca_version"
ATTR_LINK_STATUS: Final = "link_status"
ATTR_FIRMWARE_VERSION: Final = "firmware_version"
ATTR_NODE_ID: Final = "node_id"
ATTR_NETWORK_CONTROLLER: Final = "network_controller"
ATTR_TX_OK: Final = "tx_ok"
ATTR_TX_BAD: Final = "tx_bad"
ATTR_TX_DROPPED: Final = "tx_dropped"
ATTR_RX_OK: Final = "rx_ok"
ATTR_RX_BAD: Final = "rx_bad"
ATTR_RX_DROPPED: Final = "rx_dropped"
ATTR_PEER_COUNT: Final = "peer_count"
ATTR_PHY_TX_RATE: Final = "phy_tx_rate"
ATTR_PHY_RX_RATE: Final = "phy_rx_rate"

# while an adapter restarts: poll this often (seconds) to notice when it is back
REBOOT_POLL_INTERVAL: Final = 10
