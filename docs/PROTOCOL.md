# Kiwee / MaxLinear adapter web API

Notes on the HTTP interface of the KB-M3-02 (MaxLinear MXL371x, firmware 1.18.13), found by
reading the JavaScript of the adapter's own pages (`devStatus.html`, `phyRates.html`, `index.html`)
and comparing the responses with what the pages display.

## Requests

- HTTP Basic authentication.
- Queries are `POST http://<ip>/ms/<n>/<id>` (some end in `/GET`) with
  `Content-Type: application/x-www-form-urlencoded` and a body like `{"data":[]}`, `{"data":[3]}`
  or `{"data":[8,2]}`.
- A CSRF token is required: the same value as cookie `csrf_token` and as header `X-CSRF-TOKEN`.
  The server sets the cookie when `devStatus.html` is loaded; any matching pair is accepted.
- Responses are JSON: `{"data":["0x00000003", ...]}`, each value a 32-bit hex word.
  64-bit counters are two words (high, low).
- A request with a body the adapter does not expect returns `400 Bad request`.

## Endpoints

| Request | Body | Contents |
|---|---|---|
| `/ms/0/0x15` | `[]` | local info (below) |
| `/ms/0/0x16` | `[node]` | record of one node (below) |
| `/ms/1/0x103/GET` | `[node id]` | MAC address of this adapter (2 words) |
| `/ms/0/0x14` | `[0]` | Ethernet counters (below) |
| `/ms/0/0x1D` | `[1 << node, version]` | PHY rate data for one node (below) |
| `/ms/0/0x24` | `[]` | word 1 = beacon channel (MHz) |
| `/ms/0/0x7f` | `[]` | word 2 = first channel (MHz), word 3 = number of channels |
| `/ms/0/0x1003/GET` | empty | LOF (MHz) |
| `/ms/1/0x20b/GET` | empty | IP address |
| `/ms/1/0x303/GET` | `[0]` | chip ID (0x16 = MXL371x) |
| `/ms/1/0xb17` | `[0]` | GPIO |
| `/ms/0/0x1002/GET` | `[]` | Preferred NC (1 = enabled) |
| `/ms/0/0x10a8/GET` | `[]` | Tx Power setting |
| `/ms/0/0x100e/GET` | `[]` | Beacon Power Level setting |

## `0x15` local info

| Word | Meaning |
|---|---|
| 0 | node ID of this adapter |
| 1 | node ID of the network controller |
| 5 | link status (0 = down) |
| 11 | MoCA version (0x25 = 2.5) |
| 12 | bitmask of nodes on the network (0xf = nodes 0 to 3) |
| 18 | primary channel offset (0: beacon, 1: +25 MHz, 2: -25 MHz) |
| 19 | secondary channel offset (1: below, 2: above primary) |
| 21, 22 | firmware version as ASCII (`1.18.13`) |
| 28 | channel gap mode (1: secondary is 125 MHz away, otherwise 100 MHz) |

Words 4 and 9 change over time and are not used.

## `0x16` node record

| Word | Meaning |
|---|---|
| 0, 1 | MAC address (the first 6 of the 8 bytes) |
| 3 | flags; bit `0x40` is set for the network controller |
| 4 | MoCA version (0x25 = 2.5) |
| 7 | TX good packets towards this node (0 for the node itself) |

## `0x14` Ethernet counters

64-bit values (high word, low word), 27 per block, TX block first, then RX block:

| Counter | Words |
|---|---|
| TX good / bad / dropped | 12-13, 30-31, 48-49 |
| RX good / bad / dropped | 66-67, 84-85, 102-103 |

## `0x1D` PHY rates

Send `[1 << node, 2]` (version 1 if a node or the controller is MoCA 1.x). From word 10 on, the
response has one packed entry per node in the node bitmask, alternating between starting at the
top of a word and at its middle (6 bytes per entry):

- aligned: `gapNper = w >> 24`, `gapVLper = (w >> 16) & 0xff`, `ofdmbNper = w & 0xffff`
  (word *n*), `ofdmbVLper = word[n+1] >> 16`; advance one word.
- not aligned: `gapNper = (w >> 8) & 0xff`, `gapVLper = w & 0xff`,
  `ofdmbNper = word[n+1] >> 16`, `ofdmbVLper = word[n+1] & 0xffff`; advance two words.

PHY rate in Mbit/s (MoCA 2.x): `floor(3900 * ofdmbNper / ((512 + (gapNper + 10) * 2) * 46))`.
The rate from node *a* to node *b* is the entry for *b* in the response for node *a*.
The values match the table on `phyRates.html`.
