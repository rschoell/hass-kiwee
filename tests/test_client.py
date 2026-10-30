"""Tests for the adapter API client, using recorded (sanitised) responses."""

from pykiwee.client import KiweeClient


async def test_controller(adapter):
    """The adapter that is the MoCA network controller."""
    st = await (await adapter("controller")).get_status()

    assert st.mac_address == "02:00:5e:00:00:13"
    assert (st.node_id, st.nc_node_id, st.network_controller) == (3, 3, True)
    assert st.preferred_nc is True
    assert st.link_status is True
    assert st.moca_version == "2.5"
    assert st.firmware_version == "1.18.13"
    assert (st.lof, st.frequency_band, st.channel_count) == (1400, "D-High", 3)
    assert (st.tx_power, st.beacon_power) == (10, 8)
    assert (st.beacon_channel, st.primary_channel) == (1400, 1400)
    assert (st.secondary_channel, st.first_channel) == (1525, 1400)

    assert (st.packets.tx.ok, st.packets.tx.bad, st.packets.tx.dropped) == (3710915, 0, 0)
    assert (st.packets.rx.ok, st.packets.rx.bad, st.packets.rx.dropped) == (1708489, 94, 245)

    peers = {p.node_id: p for p in st.network_peers}
    assert sorted(peers) == [0, 1, 2]
    assert peers[0].mac_address == "02:00:5e:00:00:10"
    assert peers[0].tx_good == 296822
    assert not any(p.is_nc for p in peers.values())
    # PHY rates (Mbps): values checked by hand against the formula of phyRates.html
    assert (peers[0].tx_phy_rate, peers[0].rx_phy_rate) == (2076, 2108)
    assert (peers[1].tx_phy_rate, peers[1].rx_phy_rate) == (2095, 2111)
    assert (peers[2].tx_phy_rate, peers[2].rx_phy_rate) == (2038, 2080)


async def test_client_adapter(adapter):
    """An adapter that is not the controller; its own node is slot 0."""
    st = await (await adapter("client")).get_status()

    # the fixture has no answer for the MAC request with the local node id (0),
    # so this also covers the fallback to the fixed selector 3
    assert st.mac_address == "02:00:5e:00:00:10"
    assert (st.node_id, st.nc_node_id, st.network_controller) == (0, 3, False)
    assert st.preferred_nc is False

    peers = {p.node_id: p for p in st.network_peers}
    assert sorted(peers) == [1, 2, 3]  # every node except itself
    assert peers[3].is_nc is True
    assert peers[3].mac_address == "02:00:5e:00:00:13"
    assert peers[3].tx_good == 80396002
    assert (peers[3].tx_phy_rate, peers[3].rx_phy_rate) == (2102, 2086)


async def test_requests_need_csrf_token(adapter):
    """The fake adapter rejects requests without a matching token, like the real one."""
    client = await adapter("controller")
    client._csrf_token = "x"  # noqa: SLF001
    # the client recovers by fetching a fresh token and retrying
    assert (await client.get_status()).mac_address == "02:00:5e:00:00:13"


def test_channel_plan():
    """Primary / secondary channel as computed by devStatus.html."""
    plan = KiweeClient._channel_plan  # noqa: SLF001
    assert plan(1400, 0, 2, 1) == (1400, 1525)
    assert plan(1400, 0, 1, 0) == (1400, 1300)
    assert plan(1400, 1, 2, 0) == (1425, 1525)
    assert plan(1400, 2, 0, 0) == (1375, None)
    assert plan(None, 0, 0, 0) == (None, None)
