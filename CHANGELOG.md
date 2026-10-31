# Changelog

## 0.2.0

- Reboot button (disabled by default). The adapter's entities show as unavailable while it
  restarts; the integration polls every 10 seconds and resumes once it has seen the adapter go
  down and come back (it still answers for about 20 seconds after the request).
- `tools/reboot.py`: reboot an adapter from the command line and time how long it takes to return
  (refuses the network controller unless `--allow-controller` is given).

## 0.1.0

First release.

- Config flow with per-adapter devices (unique ID = the adapter's own MAC address) and an
  update-interval option.
- Link status, MoCA version, firmware, IP, MAC, local node ID, network controller and
  preferred network controller.
- Ethernet TX/RX good/bad/dropped counters.
- Other nodes on the MoCA network (peers) with MAC address, TX good packets and PHY TX/RX rate.
- Beacon, primary, secondary and first channel, number of channels, LOF and band.
- Tx power and beacon power level settings (read only).
- `tools/selftest.py` and `tools/probe.py` for checking an adapter from the command line.
