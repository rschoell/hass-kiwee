# Kiwee Broadband MoCA for Home Assistant

[![Validate](https://github.com/rschoell/hass-kiwee/actions/workflows/validate.yaml/badge.svg)](https://github.com/rschoell/hass-kiwee/actions/workflows/validate.yaml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Monitor Kiwee Broadband MoCA 2.5 adapters (KB-M3-02 family) in Home Assistant:
link state, who is the network controller, the other adapters on the coax network, PHY rates
between them, channels and Ethernet counters. Every adapter becomes its own device.

> This is an unofficial community project and is not affiliated with Kiwee Broadband or MaxLinear.
> Apart from the optional reboot button, the integration is **read-only**. It sends the same queries
> the adapter's own web pages use to display their status, and never changes a setting.

It started as a fork of [hass-gocoax](https://github.com/homeassistant-projects/hass-gocoax) (see [Credits](#credits)).

## Status

Developed and verified against four KB-M3-02 adapters on firmware `1.18.13` (MaxLinear MXL371x).
Other Kiwee models or firmware versions with the same MaxLinear web interface may work, but are
untested. If you try one, please open an issue with the output of `tools/selftest.py`.

## Installation

### HACS (custom repository)

1. HACS -> three-dot menu -> **Custom repositories**.
2. Add `https://github.com/rschoell/hass-kiwee` with category **Integration**.
3. Install **Kiwee Broadband MoCA Adapters** and restart Home Assistant.

### Manual

Copy `custom_components/kiwee` into the `custom_components` folder of your Home Assistant
configuration and restart.

## Setup

**Settings -> Devices & services -> Add integration -> Kiwee Broadband.**

Enter the adapter's IP address and the web interface login (the adapter manual lists
`admin` / `maxlinear` as the default). Add each adapter separately, with its own IP address.
Give the adapters a DHCP reservation so the address does not change.

Option: *Update interval* (10 to 300 seconds, default 30). Every update sends about 20
small requests to the adapter, so very short intervals are not recommended.

The credentials are sent with HTTP Basic authentication over plain HTTP, which is all the adapter
offers. Use the integration only on a network you trust.

## Entities

Per adapter:

| Entity | Notes |
|---|---|
| Link Status (binary) | MoCA link up/down |
| Network Controller (binary) | this adapter is the MoCA network controller |
| Preferred Network Controller (binary, diagnostic) | the "Preferred NC" setting |
| MoCA Version, Node ID, MAC Address, IP Address | |
| TX Packets / RX Packets | Ethernet good-packet counters; bad and dropped counts are attributes |
| Network Peers | number of other adapters; their MACs and rates are attributes |
| PHY TX Rate / PHY RX Rate | one pair per other adapter, in Mbit/s (unicast NPER) |
| Primary channel, Secondary channel (diagnostic) | MHz |
| Beacon channel, First channel (diagnostic, disabled by default) | MHz |
| Lowest Operating Frequency, Frequency Band, Channel Count | |
| Tx power level, Beacon power level (diagnostic) | the two dropdown settings, plain numbers |
| Reboot (button, configuration, **disabled by default**) | restarts the adapter, see below |

## Reboot button

Each adapter has a **Reboot** button that does what the Reboot page of the adapter's web interface does.
It is disabled by default: enable it under *Settings -> Devices & services -> Kiwee Broadband ->
the device -> disabled entities*.

- **Rebooting the network controller interrupts every MoCA link**, and anything that uses the
  controller as its uplink, for up to a minute. Home Assistant buttons have no confirmation step, so
  be careful with automations. The *Network Controller* sensor shows which adapter that is.
- After the press, the adapter's entities show as unavailable. The adapter does not answer the
  request, so pressing the button takes about 10 seconds to return. It then keeps answering for
  roughly 20 seconds, is unreachable for another 25 or so, and is back about 45 seconds after the
  press (measured on a client adapter; the network controller is reported to take 30 to 60 seconds).
  In Home Assistant the entities are usually back after about a minute.
  The integration waits quietly (no error spam in the log) until it has seen the adapter go down and
  come back, checking every 10 seconds, and gives up after four minutes.
- A reboot is refused with an error if the adapter cannot be reached.

To try it outside Home Assistant first (it refuses the controller unless you add `--allow-controller`):

```bash
python tools/reboot.py 192.168.1.50
```

## Diagnostics from the command line

Run these on a machine in the same network as the adapter (needs Python 3.12+ and `aiohttp`):

```bash
pip install aiohttp
python tools/selftest.py 192.168.1.50      # the real client, decoded values
python tools/probe.py 192.168.1.50         # raw responses of every request the web UI sends
```

The output contains MAC addresses. Replace them before sharing it in an issue.

How the adapter's web API works, and how each value is decoded, is written down in
[docs/PROTOCOL.md](docs/PROTOCOL.md).

## Troubleshooting

- *Cannot connect*: open `http://<adapter-ip>` in a browser from the Home Assistant host's network.
  The adapter must be reachable and the login must work there.
- *Wrong or duplicate devices*: each adapter is identified by its own MAC address. If two entries show
  the same MAC, tell me which firmware they run (open an issue with the selftest output).
- Enable debug logs:

  ```yaml
  logger:
    logs:
      custom_components.kiwee: debug
  ```

## Not supported yet

Adapter name and GPIO are not read. Settings cannot be changed from Home Assistant (the reboot is the only action).

## Development

```bash
pip install pytest pytest-asyncio aiohttp
pytest
```

The tests replay recorded adapter responses (with the MAC addresses replaced) against a small local
server that behaves like the adapter, including the CSRF check.

## Credits

Based on [hass-gocoax](https://github.com/homeassistant-projects/hass-gocoax) by Ryan Snodgrass
(Apache-2.0). The API client was rewritten for the Kiwee adapters. See [NOTICE](NOTICE).

## License

Apache License 2.0. See [LICENSE](LICENSE).
