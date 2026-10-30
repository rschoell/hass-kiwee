#!/usr/bin/env python3
"""Run the real pykiwee client against your adapter and print the decoded status.

Usage (from the repo root):
    pip install aiohttp
    python3 tools/selftest.py 192.168.1.50 [user] [password]
Redact MAC addresses before sharing the output.
"""
import asyncio
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "kiwee"))
from pykiwee.client import KiweeClient  # noqa: E402

logging.basicConfig(level=logging.DEBUG if "-v" in sys.argv else logging.WARNING)
args = [a for a in sys.argv[1:] if a != "-v"]


async def main() -> None:
    client = KiweeClient(args[0], *(args[1:3]))
    try:
        st = await client.get_status()
        raw = (await client.get_local_info()).get("raw_data", [])
    finally:
        await client.close()
    print("MAC (local)      :", st.mac_address)
    print("Local node slot  :", st.node_id)
    print("Controller slot  :", st.nc_node_id, "| this adapter is controller:", st.network_controller)
    print("0x15 words 0-4  :", raw[:5])
    print("Link up          :", st.link_status, "| MoCA", st.moca_version)
    print("Firmware         :", st.firmware_version)
    print("LOF MHz / band   :", st.lof, "/", st.frequency_band)
    print("Preferred NC     :", st.preferred_nc)
    print("Channels (MHz)   :", f"beacon {st.beacon_channel}, primary {st.primary_channel}, secondary {st.secondary_channel}, first {st.first_channel}, count {st.channel_count}")
    print("Tx / Beacon power:", st.tx_power, "/", st.beacon_power)
    print(f"Ethernet TX      : good {st.packets.tx.ok} / bad {st.packets.tx.bad} / dropped {st.packets.tx.dropped}")
    print(f"Ethernet RX      : good {st.packets.rx.ok} / bad {st.packets.rx.bad} / dropped {st.packets.rx.dropped}")
    print("Peers            :")
    for p in st.network_peers:
        print(f"  slot {p.node_id}  {p.mac_address}  MoCA {p.moca_version}  TX good {p.tx_good}  controller: {p.is_nc}  PHY tx/rx {p.tx_phy_rate}/{p.rx_phy_rate} Mbps")


asyncio.run(main())
