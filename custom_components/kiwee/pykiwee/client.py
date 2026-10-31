# Derived from hass-gocoax (Apache-2.0, https://github.com/homeassistant-projects/hass-gocoax);
# modified for Kiwee Broadband MoCA adapters. See NOTICE.
"""Async client for Kiwee Broadband MoCA adapters."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import secrets
from typing import TYPE_CHECKING

import aiohttp

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

if TYPE_CHECKING:
    from aiohttp import ClientSession

LOG = logging.getLogger(__name__)

# API endpoints - JSON data
ENDPOINT_MAC = "/ms/1/0x103/GET"
ENDPOINT_REBOOT = "/ms/1/0xb00"  # POST {"data":[]}, sent by reboot.html
ENDPOINT_LOCAL_INFO = "/ms/0/0x15"
ENDPOINT_FRAME_INFO = "/ms/0/0x14"
ENDPOINT_FMR_INFO = "/ms/0/0x1D"
MAX_NODES = 16  # node bitmask width used by the web UI (0x15 word 12)
ENDPOINT_CHANNELS = "/ms/0/0x7f"  # [?, ?, first channel MHz, number of channels]
ENDPOINT_BEACON = "/ms/0/0x24"  # [high, low] 64-bit: beacon channel MHz
ENDPOINT_NODE_STATUS = "/ms/0/0x16"  # per-node record, body {"data":[slot]}
ENDPOINT_LOF = "/ms/0/0x1003/GET"  # LOF in MHz (= LOF field on index.html), POST {"data":[]}
ENDPOINT_TX_POWER = "/ms/0/0x10a8/GET"  # "Tx Power" dropdown on index.html, POST {"data":[]}
ENDPOINT_BEACON_POWER = "/ms/0/0x100e/GET"  # "Beacon Power Level" dropdown on index.html
ENDPOINT_PREFERRED_NC = "/ms/0/0x1002/GET"  # 1 = "Preferred NC" checked (index.html), POST {"data":[]}

# HTML page endpoints

# data indices from decoded format
LOCAL_INFO_LINK_STATUS_IDX = 5
LOCAL_INFO_MOCA_VER_IDX = 11
LOCAL_INFO_NODE_ID_IDX = 0  # local node slot (observed 3; Kiwee, differs from goCoax)
LOCAL_INFO_NC_NODE_IDX = 1  # Kiwee: words 0 and 1 are both 3 on the controller; word 4 is something else (unconfirmed)

FRAME_TX_GOOD_IDX = 12
FRAME_TX_BAD_IDX = 30
FRAME_TX_DROP_IDX = 48
FRAME_RX_GOOD_IDX = 66
FRAME_RX_BAD_IDX = 84
FRAME_RX_DROP_IDX = 102

DEFAULT_TIMEOUT = 15

_LOGGER = logging.getLogger(__name__)


class KiweeClient:
    """Async client for communicating with Kiwee Broadband MoCA adapters."""

    def __init__(
        self,
        host: str,
        username: str = "admin",
        password: str = "maxlinear",
        session: ClientSession | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the Kiwee Broadband client."""
        self._host = host
        self._username = username
        self._password = password
        self._session = session
        self._owns_session = session is None
        self._timeout = timeout
        self._base_url = f"http://{host}"
        self._csrf_token: str | None = None

    async def _get_session(self) -> ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the client session if we own it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @staticmethod
    def _is_ms_post(endpoint: str) -> bool:
        """MaxLinear /ms/ queries are POSTs; only the ".../GET" form is a plain GET."""
        return endpoint.startswith("/ms/") and not endpoint.endswith("/GET")

    def _auth_header(self) -> dict[str, str]:
        """HTTP Basic authentication header (set by hand, aiohttp deprecates auth=)."""
        token = base64.b64encode(f"{self._username}:{self._password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    async def _refresh_csrf(self, session: ClientSession, auth: dict[str, str]) -> None:
        """Obtain a CSRF token the way the web UI does (cookie + X-CSRF-TOKEN header).

        The adapter's pages send the same value as the ``csrf_token`` cookie and the
        ``X-CSRF-TOKEN`` header. Try to pick it up from a page load; if the server does
        not set one, generate one (double-submit scheme accepts any matching pair).
        """
        token = None
        try:
            async with session.get(
                f"{self._base_url}/devStatus.html", headers=auth
            ) as resp:
                morsel = resp.cookies.get("csrf_token")
                if morsel is not None:
                    token = morsel.value
        except aiohttp.ClientError:
            pass
        self._csrf_token = token or secrets.token_hex(16).upper()

    def _ms_headers(self, auth: dict[str, str], page: str = "devStatus.html") -> dict[str, str]:
        """Headers of a web UI POST: Basic auth, CSRF cookie + header, origin and referer."""
        return {
            **auth,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html, */*",
            "X-CSRF-TOKEN": self._csrf_token or "",
            "Cookie": f"csrf_token={self._csrf_token}",
            "Origin": self._base_url,
            "Referer": f"{self._base_url}/{page}",
        }

    async def _post_ms(
        self,
        session: ClientSession,
        url: str,
        auth: dict[str, str],
        body: str = '{"data":[]}',
        retry: bool = True,
    ) -> dict | str:
        """POST an /ms/ query with CSRF cookie + header."""
        if self._csrf_token is None:
            await self._refresh_csrf(session, auth)
        headers = self._ms_headers(auth)
        async with session.post(
            url, data=body, headers=headers
        ) as resp:
            if resp.status in (400, 403) and retry:
                self._csrf_token = None
                return await self._post_ms(session, url, auth, body=body, retry=False)
            return await self._handle_response(resp, url)

    async def _request(
        self, endpoint: str, method: str = "GET", body: str | None = None
    ) -> dict | str:
        """Make an authenticated request to the adapter.

        ``body`` is the JSON body for /ms/ POST queries, e.g. '{"data":[0]}'.
        """
        session = await self._get_session()
        url = f"{self._base_url}{endpoint}"
        auth = self._auth_header()

        try:
            async with asyncio.timeout(self._timeout):
                if method == "POST" or body is not None or self._is_ms_post(endpoint):
                    return await self._post_ms(
                        session, url, auth, body=body or '{"data":[]}'
                    )
                async with session.get(url, headers=auth) as resp:
                    return await self._handle_response(resp, url)

        except TimeoutError as err:
            raise KiweeTimeoutError(
                f"Timeout connecting to Kiwee Broadband adapter at {self._host}"
            ) from err
        except aiohttp.ClientError as err:
            raise KiweeConnectionError(
                f"Error connecting to Kiwee Broadband adapter at {self._host}: {err}"
            ) from err

    async def _handle_response(
        self, resp: aiohttp.ClientResponse, url: str
    ) -> dict | str:
        """Handle HTTP response."""
        if resp.status == 401:
            raise KiweeAuthError(
                f"Authentication failed for Kiwee Broadband adapter at {self._host}"
            )
        if resp.status != 200:
            raise KiweeConnectionError(
                f"HTTP {resp.status} from Kiwee Broadband adapter: {url}"
            )

        text = await resp.text()
        # /ms/ endpoints return JSON even when the content type says text/html
        if "/ms/" in url or "json" in (resp.content_type or ""):
            try:
                return json.loads(text)
            except ValueError as err:
                raise KiweeConnectionError(
                    f"Invalid JSON from Kiwee Broadband adapter: {url}"
                ) from err
        return text

    def _parse_hex_value(self, hex_str: str) -> int:
        """Parse hex string to integer."""
        try:
            return int(hex_str, 16)
        except (ValueError, TypeError):
            return 0

    def _parse_64bit_value(self, data: list[str], high_idx: int) -> int:
        """Parse 64-bit value from two consecutive hex strings."""
        if high_idx + 1 >= len(data):
            return 0
        high = self._parse_hex_value(data[high_idx]) & 0xFFFFFFFF
        low = self._parse_hex_value(data[high_idx + 1])
        return (high * 4294967296) + low

    def _hex_to_mac(self, hi: int, lo: int) -> str:
        """Convert two integers to MAC address string."""
        # extract bytes: hi contains first 4 bytes, lo contains last 2
        b1 = (hi >> 24) & 0xFF
        b2 = (hi >> 16) & 0xFF
        b3 = (hi >> 8) & 0xFF
        b4 = hi & 0xFF
        b5 = (lo >> 24) & 0xFF
        b6 = (lo >> 16) & 0xFF
        return f"{b1:02x}:{b2:02x}:{b3:02x}:{b4:02x}:{b5:02x}:{b6:02x}"

    def _parse_moca_version(self, ver_int: int) -> str:
        """Parse MoCA version from integer value."""
        # version is encoded as major * 16 + minor
        if ver_int == 0x20:
            return "2.0"
        if ver_int == 0x25:
            return "2.5"
        if ver_int >= 0x20:
            major = ver_int >> 4
            minor = ver_int & 0x0F
            return f"{major}.{minor}"
        return "unknown"

    async def get_mac_address(self, node_id: int | None = None) -> str:
        """Get the adapter's own MAC address.

        devStatus.html sends POST /ms/1/0x103/GET with {"data":[<local node id>]}. On the
        adapters tested the same call with 3 also returned the adapter's own MAC, so 3 is
        used as a fallback. A plain GET without a body returns another adapter's MAC.
        """
        if node_id is None:
            try:
                node_id = (await self.get_local_info()).get("node_id")
            except KiweeParseError:
                node_id = None
        selectors = [n for n in dict.fromkeys([node_id, 3]) if n is not None]
        last_err: KiweeConnectionError | None = None
        for selector in selectors:
            try:
                resp = await self._request(ENDPOINT_MAC, body=f'{{"data":[{selector}]}}')
            except KiweeConnectionError as err:
                last_err = err
                continue
            if isinstance(resp, dict) and len(resp.get("data", [])) >= 2:
                mac = self._hex_to_mac(
                    self._parse_hex_value(resp["data"][0]),
                    self._parse_hex_value(resp["data"][1]),
                )
                if mac != "00:00:00:00:00:00":
                    return mac
        if last_err is not None:
            raise last_err
        return ""

    async def _optional(self, coro, default):
        """Await an optional query; on adapter errors log and return a default.

        Not every Kiwee endpoint is mapped yet, so a failing optional query must
        not take the whole integration down.
        """
        try:
            return await coro
        except KiweeError as err:
            _LOGGER.debug("Optional Kiwee query failed: %s", err)
            return default

    @staticmethod
    def _ascii_words(words: list[str]) -> str:
        """Decode big-endian hex words to ASCII, e.g. 0x312e3138 0x2e313300 -> '1.18.13'."""
        raw = b"".join(int(w, 16).to_bytes(4, "big") for w in words)
        return raw.replace(b"\x00", b"").decode("ascii", errors="ignore")

    async def get_local_info(self) -> dict:
        """Get local adapter info (link status, MoCA version, etc.)."""
        resp = await self._request(ENDPOINT_LOCAL_INFO)
        if isinstance(resp, dict) and "data" in resp:
            data = resp["data"]
            return {
                "link_status": self._parse_hex_value(data[LOCAL_INFO_LINK_STATUS_IDX])
                if len(data) > LOCAL_INFO_LINK_STATUS_IDX
                else 0,
                "moca_version": self._parse_hex_value(data[LOCAL_INFO_MOCA_VER_IDX])
                if len(data) > LOCAL_INFO_MOCA_VER_IDX
                else 0,
                "node_id": self._parse_hex_value(data[LOCAL_INFO_NODE_ID_IDX])
                if len(data) > LOCAL_INFO_NODE_ID_IDX
                else 0,
                "nc_node_id": self._parse_hex_value(data[LOCAL_INFO_NC_NODE_IDX])
                if len(data) > LOCAL_INFO_NC_NODE_IDX
                else 0,
                "version_string": self._ascii_words(data[21:23]) if len(data) > 22 else "",
                # words used by devStatus.html / phyRates.html
                "node_mask": self._parse_hex_value(data[12]) if len(data) > 12 else 0,
                "primary_offset": self._parse_hex_value(data[18]) if len(data) > 18 else 0,
                "secondary_offset": self._parse_hex_value(data[19]) if len(data) > 19 else 0,
                "gap_mode": self._parse_hex_value(data[28]) if len(data) > 28 else 0,
                "raw_data": data,
            }
        raise KiweeParseError("Invalid local info response")

    async def get_frame_info(self) -> EthernetPackets:
        """Get ethernet tx/rx packet statistics."""
        resp = await self._request(ENDPOINT_FRAME_INFO, body='{"data":[0]}')
        if isinstance(resp, dict) and "data" in resp:
            data = resp["data"]
            tx_good = self._parse_64bit_value(data, FRAME_TX_GOOD_IDX)
            tx_bad = self._parse_64bit_value(data, FRAME_TX_BAD_IDX)
            tx_drop = self._parse_64bit_value(data, FRAME_TX_DROP_IDX)
            rx_good = self._parse_64bit_value(data, FRAME_RX_GOOD_IDX)
            rx_bad = self._parse_64bit_value(data, FRAME_RX_BAD_IDX)
            rx_drop = self._parse_64bit_value(data, FRAME_RX_DROP_IDX)

            return EthernetPackets(
                tx=PacketStats(ok=tx_good, bad=tx_bad, dropped=tx_drop),
                rx=PacketStats(ok=rx_good, bad=rx_bad, dropped=rx_drop),
            )
        raise KiweeParseError("Invalid frame info response")

    async def get_channel_info(self) -> tuple[int | None, int | None]:
        """First channel (MHz) and number of channels from /ms/0/0x7f (devStatus.html)."""
        resp = await self._request(ENDPOINT_CHANNELS, body='{"data":[]}')
        if isinstance(resp, dict) and len(resp.get("data", [])) >= 4:
            first = self._parse_hex_value(resp["data"][2])
            count = self._parse_hex_value(resp["data"][3])
            return (first or None), (count if 0 < count <= 16 else None)
        raise KiweeParseError("Invalid channel info response")

    async def get_beacon_channel(self) -> int | None:
        """Beacon channel (MHz): word 1 of /ms/0/0x24 (devStatus.html "Beacon Channel")."""
        resp = await self._request(ENDPOINT_BEACON, body='{"data":[]}')
        if isinstance(resp, dict) and len(resp.get("data", [])) >= 2:
            return self._parse_hex_value(resp["data"][1]) or None
        raise KiweeParseError("Invalid beacon channel response")

    @staticmethod
    def _channel_plan(
        beacon: int | None, primary_offset: int, secondary_offset: int, gap_mode: int
    ) -> tuple[int | None, int | None]:
        """Primary / secondary channel as computed by devStatus.html."""
        if beacon is None:
            return None, None
        primary = {0: beacon, 1: beacon + 25, 2: beacon - 25}.get(primary_offset)
        if primary is None:
            return None, None
        step = 125 if gap_mode else 100
        secondary = {1: primary - step, 2: primary + step}.get(secondary_offset)
        return primary, secondary

    async def get_node_table(self, node_mask: int) -> dict[int, list[int]]:
        """Per-node records: POST /ms/0/0x16 with {"data":[node]} for each node in the mask.

        Words: [0..1] MAC, [3] flags (0x40 = network controller), [4] MoCA version
        (0x25 = 2.5), [7] TX good packets (matches the web UI).
        """
        table: dict[int, list[int]] = {}
        for node in range(MAX_NODES):
            if not node_mask & (1 << node):
                continue
            try:
                resp = await self._request(
                    ENDPOINT_NODE_STATUS, body=f'{{"data":[{node}]}}'
                )
            except (KiweeConnectionError, KiweeParseError) as err:
                LOG.debug("Node %d query failed: %s", node, err)
                continue
            if isinstance(resp, dict) and len(resp.get("data", [])) >= 8:
                table[node] = [self._parse_hex_value(w) for w in resp["data"]]
        return table

    def _peers_from_table(
        self, table: dict[int, list[int]], local_node_id: int
    ) -> list[NetworkPeer]:
        """Build the peer list (every node except this adapter)."""
        peers: list[NetworkPeer] = []
        for node, words in sorted(table.items()):
            mac_addr = self._hex_to_mac(words[0], words[1])
            if node == local_node_id or mac_addr == "00:00:00:00:00:00":
                continue
            peers.append(
                NetworkPeer(
                    node_id=node,
                    mac_address=mac_addr,
                    moca_version=self._parse_moca_version(words[4]),
                    tx_good=words[7],
                    is_nc=bool(words[3] & 0x40),
                )
            )
        return peers

    async def get_phy_matrix(
        self, local_info: dict, table: dict[int, list[int]]
    ) -> dict[tuple[int, int], int]:
        """PHY rates (Mbps, unicast NPER) between nodes: {(from_node, to_node): rate}.

        Port of the calculation in phyRates.html. For every node, POST /ms/0/0x1D with
        {"data":[1 << node, version]} returns the FMR payload; from word 10 on there is one
        6-byte entry (gapNper, gapVLper, ofdmbNper, ofdmbVLper) per node in the mask.
        """
        mask = local_info.get("node_mask", 0)
        nc_node = local_info.get("nc_node_id", 0)

        def ver(node: int) -> int:
            words = table.get(node)
            return (words[4] & 0xFF) if words and len(words) > 4 else 0

        nc_ver = ver(nc_node) or ver(local_info.get("node_id", 0))
        matrix: dict[tuple[int, int], int] = {}

        for src in range(MAX_NODES):
            if not mask & (1 << src) or src not in table:
                continue
            node_ver = ver(src)
            final_ver = 1 if min(nc_ver, node_ver) < 0x20 else 2
            try:
                resp = await self._request(
                    ENDPOINT_FMR_INFO, body=f'{{"data":[{1 << src},{final_ver}]}}'
                )
            except (KiweeConnectionError, KiweeParseError) as err:
                LOG.debug("FMR query for node %d failed: %s", src, err)
                continue
            if not (isinstance(resp, dict) and len(resp.get("data", [])) > 12):
                continue
            words = [self._parse_hex_value(w) for w in resp["data"]]
            entry_ver = min(node_ver, nc_ver)
            idx, aligned = 10, True

            for dst in range(MAX_NODES):
                if not mask & (1 << dst):
                    if node_ver >= 0x20:
                        idx += 1 if aligned else 2
                    elif not aligned:
                        idx += 1
                    aligned = not aligned
                    continue
                fmr_ver = min(entry_ver, ver(dst)) if nc_ver < 0x20 else node_ver
                if idx + 1 >= len(words):
                    break
                word = words[idx]
                if fmr_ver in (0x20, 0x25):  # MoCA 2.x payload
                    if aligned:
                        gap_n = (word >> 24) & 0xFF
                        gap_vl = (word >> 16) & 0xFF
                        ofdm_n = word & 0xFFFF
                        idx += 1
                    else:
                        gap_n = (word >> 8) & 0xFF
                        gap_vl = word & 0xFF
                        ofdm_n = (words[idx + 1] >> 16) & 0xFFFF
                        idx += 2
                else:  # MoCA 1.x payload
                    gap_vl = 0
                    if aligned:
                        gap_n = (word & 0xF8000000) >> 27
                        ofdm_n = (word & 0x07FF0000) >> 16
                    else:
                        gap_n = (word & 0x0000F800) >> 11
                        ofdm_n = word & 0x000007FF
                        idx += 1
                aligned = not aligned

                if gap_n == 0:
                    rate = 0
                elif gap_vl == 0 and fmr_ver == 0x20:
                    rate = (1200 * ofdm_n) // ((256 + gap_n * 2 + 10) * 26)
                else:
                    rate = (3900 * ofdm_n) // ((512 + (gap_n + 10) * 2) * 46)
                if rate:
                    matrix[(src, dst)] = rate
        return matrix

    def _lof_to_band(self, lof: int) -> str:
        """Convert LOF (lowest operating frequency) to band name."""
        # MoCA 2.5 band definitions (approximate)
        if lof >= 1400:
            return "D-High"
        if lof >= 1225:
            return "D-Mid"
        if lof >= 1125:
            return "Extended-D"
        if lof >= 1000:
            return "D-Low"
        return f"Unknown ({lof} MHz)"

    async def get_lof(self) -> int | None:
        """Get the LOF (lowest operating frequency, MHz): "LOF" on index.html (1400 = D-High)."""
        resp = await self._request(ENDPOINT_LOF, body='{"data":[]}')
        if isinstance(resp, dict) and resp.get("data"):
            lof = self._parse_hex_value(resp["data"][0])
            return lof if 1000 <= lof <= 1700 else None
        raise KiweeParseError("Invalid LOF response")

    async def _read_setting(self, endpoint: str) -> int | None:
        """Read a single-value setting (index.html dropdowns) via POST {"data":[]}."""
        resp = await self._request(endpoint, body='{"data":[]}')
        if isinstance(resp, dict) and resp.get("data"):
            return self._parse_hex_value(resp["data"][0])
        raise KiweeParseError(f"Invalid response for {endpoint}")

    async def get_tx_power(self) -> int | None:
        """Tx Power setting (confirmed: 10 on the UI = 0x10a8 value 10)."""
        return await self._read_setting(ENDPOINT_TX_POWER)

    async def get_beacon_power(self) -> int | None:
        """Beacon Power Level setting (confirmed: changed to 8 on the UI = 0x100e value 8)."""
        return await self._read_setting(ENDPOINT_BEACON_POWER)

    async def get_preferred_nc(self) -> bool | None:
        """Get the "Preferred NC" setting (index.html): 1 on the controller, 0 on clients."""
        resp = await self._request(ENDPOINT_PREFERRED_NC, body='{"data":[]}')
        if isinstance(resp, dict) and resp.get("data"):
            return self._parse_hex_value(resp["data"][0]) == 1
        raise KiweeParseError("Invalid preferred NC response")

    async def get_status(self) -> AdapterStatus:
        """Get complete adapter status."""
        local_info = await self.get_local_info()
        mac_address = await self.get_mac_address(local_info.get("node_id"))

        link_status = local_info.get("link_status", 0) == 1
        moca_ver_int = local_info.get("moca_version", 0)
        moca_version = self._parse_moca_version(moca_ver_int)
        node_id = local_info.get("node_id", 0)
        nc_node_id = local_info.get("nc_node_id", 0)
        is_nc = node_id == nc_node_id

        lof_mhz = await self._optional(self.get_lof(), None)
        preferred_nc = await self._optional(self.get_preferred_nc(), None)
        tx_power = await self._optional(self.get_tx_power(), None)
        beacon_power = await self._optional(self.get_beacon_power(), None)
        packets = await self._optional(self.get_frame_info(), EthernetPackets())
        node_table = await self.get_node_table(local_info.get("node_mask", 0))
        peers = self._peers_from_table(node_table, node_id)
        phy_matrix = await self._optional(self.get_phy_matrix(local_info, node_table), {})
        phy_rates: list[PhyRate] = []
        for peer in peers:
            peer.tx_phy_rate = phy_matrix.get((node_id, peer.node_id), 0)
            peer.rx_phy_rate = phy_matrix.get((peer.node_id, node_id), 0)
            phy_rates.append(
                PhyRate(
                    source_mac=mac_address,
                    target_mac=peer.mac_address,
                    tx_rate=peer.tx_phy_rate,
                    rx_rate=peer.rx_phy_rate,
                )
            )
        first_channel, channels_ui = await self._optional(
            self.get_channel_info(), (None, None)
        )
        beacon_channel = await self._optional(self.get_beacon_channel(), None)
        primary_channel, secondary_channel = self._channel_plan(
            beacon_channel,
            local_info.get("primary_offset", 0),
            local_info.get("secondary_offset", 0),
            local_info.get("gap_mode", 0),
        )

        return AdapterStatus(
            mac_address=mac_address,
            ip_address=self._host,
            moca_version=moca_version,
            link_status=link_status,
            packets=packets,
            network_peers=peers,
            phy_rates=phy_rates,
            node_id=node_id,
            nc_node_id=nc_node_id,
            network_controller=is_nc,
            firmware_version=local_info.get("version_string") or None,
            frequency_band=self._lof_to_band(lof_mhz) if lof_mhz else None,
            lof=lof_mhz,
            channel_count=channels_ui,
            preferred_nc=preferred_nc,
            tx_power=tx_power,
            beacon_power=beacon_power,
            beacon_channel=beacon_channel,
            primary_channel=primary_channel,
            secondary_channel=secondary_channel,
            first_channel=first_channel,
        )

    async def reboot(self, response_timeout: float = 10.0) -> None:
        """Reboot the adapter, like the button on reboot.html.

        Sends POST /ms/1/0xb00 with {"data":[]}. The adapter does not answer (measured: the
        request just times out) and restarts about 20 s later, so a timeout, a closed connection
        or a reset *after* the request went out counts as success. To still report real
        problems, the adapter is queried first: unreachable or wrong credentials raise, and so
        does an HTTP error answer to the reboot request itself.
        """
        await self.get_local_info()  # raises KiweeConnectionError / KiweeAuthError
        session = await self._get_session()
        auth = self._auth_header()
        if self._csrf_token is None:
            await self._refresh_csrf(session, auth)

        url = f"{self._base_url}{ENDPOINT_REBOOT}"
        try:
            async with asyncio.timeout(response_timeout):
                async with session.post(
                    url,
                    data='{"data":[]}',
                    headers=self._ms_headers(auth, page="reboot.html"),
                ) as resp:
                    if resp.status == 401:
                        raise KiweeAuthError(
                            f"Authentication failed for Kiwee Broadband adapter at {self._host}"
                        )
                    if resp.status >= 400:
                        raise KiweeConnectionError(
                            f"HTTP {resp.status} from Kiwee Broadband adapter: {url}"
                        )
                    await resp.read()
        except aiohttp.ClientConnectorError as err:
            raise KiweeConnectionError(
                f"Cannot connect to Kiwee Broadband adapter at {self._host}: {err}"
            ) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            # expected while the adapter restarts
            LOG.debug("Connection closed during reboot of %s: %s", self._host, err)

    async def test_connection(self) -> bool:
        """Test connection to the adapter."""
        try:
            mac = await self.get_mac_address()
            return bool(mac)
        except KiweeAuthError:
            raise
        except KiweeConnectionError:
            raise
        except Exception as err:
            LOG.debug(f"Connection test failed: {err}")
            return False
