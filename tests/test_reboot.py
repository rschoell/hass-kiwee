"""Tests for the reboot request and the restart bookkeeping."""

import pytest
from pykiwee.client import KiweeClient
from pykiwee.exceptions import KiweeConnectionError
from pykiwee.reboot import RebootWatch


@pytest.mark.parametrize("mode", ["hang", "drop", "ok"])
async def test_reboot_sends_the_request(adapter, mode):
    """The request is sent once; no answer (the real adapter) or a closed connection is success."""
    client = await adapter("client", reboot=mode)
    await client.reboot(response_timeout=0.5)
    assert client.reboot_calls == ['{"data":[]}']


async def test_reboot_rejected_by_adapter(adapter):
    """An HTTP error answer to the reboot request is reported."""
    client = await adapter("client", reboot="reject")
    with pytest.raises(KiweeConnectionError):
        await client.reboot(response_timeout=0.5)


async def test_reboot_adapter_unreachable():
    """Nothing is sent, and an error is raised, if the adapter cannot be reached."""
    client = KiweeClient("127.0.0.1:9", timeout=3)
    try:
        with pytest.raises(KiweeConnectionError):
            await client.reboot(response_timeout=0.5)
    finally:
        await client.close()


def test_watch_needs_to_see_the_adapter_go_down():
    """Measured: the adapter still answers ~20 s after the request, then goes away."""
    watch = RebootWatch(min_wait=10, max_wait=240, no_down_timeout=90)
    assert not watch.active
    watch.start(100.0)
    assert watch.active
    assert watch.settling(105.0)  # right after the request: do not probe yet
    assert not watch.settling(111.0)
    # still reachable: that is NOT "back" yet
    assert watch.on_probe(112.0, reachable=True) == "waiting"
    assert watch.on_probe(122.0, reachable=True) == "waiting"
    # went down ...
    assert watch.on_probe(132.0, reachable=False) == "waiting"
    assert watch.on_probe(142.0, reachable=False) == "waiting"
    # ... and is back
    assert watch.on_probe(152.0, reachable=True) == "back"
    assert not watch.active


def test_watch_assumes_nothing_happened_if_it_never_goes_down():
    watch = RebootWatch(no_down_timeout=90)
    watch.start(0.0)
    assert watch.on_probe(80.0, reachable=True) == "waiting"
    assert watch.on_probe(91.0, reachable=True) == "back"
    assert not watch.active


def test_watch_gives_up_after_the_maximum():
    watch = RebootWatch(max_wait=240)
    watch.start(0.0)
    assert watch.on_probe(30.0, reachable=False) == "waiting"
    assert watch.on_probe(239.0, reachable=False) == "waiting"
    assert watch.on_probe(241.0, reachable=False) == "timeout"
    assert not watch.active


def test_watch_can_be_started_again():
    watch = RebootWatch()
    watch.start(0.0)
    watch.on_probe(20.0, reachable=False)
    assert watch.on_probe(50.0, reachable=True) == "back"
    watch.start(1000.0)
    assert watch.went_down is False  # state was reset
    assert watch.on_probe(1015.0, reachable=True) == "waiting"
