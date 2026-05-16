# Notes

## Redis Stream Schemas

Each stream stores entries with a single `measurement` field containing a JSON object. All streams are capped at ~86 400 entries (≈ 24 h of 1 Hz data) via `XADD ... MAXLEN ~`.

| Stream         | Frequency               | Payload keys                                                                                                       |
| -------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `bluetooth`    | 1 s                     | map of `<MAC>` → `{ "capacity": <int>\|"Unknown" }`                                                                |
| `power_supply` | 1 s                     | `grid: bool`, `batteries: { <name>: { "capacity": str, "status": str } }`                                          |
| `audio`        | 1 s                     | `muted: bool`, `volume: int`                                                                                       |
| `stream`       | 1 s                     | `streaming: bool`, `obs: bool`                                                                                     |
| `vpn`          | 10 s                    | `connected: bool`, `country: str`, `city: str`                                                                     |
| `updates`      | hourly (+ pacman hook)  | `outstanding_updates: int`                                                                                         |
| `location`     | hourly at xx:30         | `latitude: float`, `longitude: float`, `ip_address: str`, `timezone: str`, `sunrise: str`, `sunset: str`           |

## Scheduling and Concurrency

`monitor.py` uses `schedule` to run each job on its own cadence. Jobs that perform I/O against external services (OBS WebSocket, ipinfo.io) run inside threads and protect against overlap via a per-job lock, so a slow tick never blocks the next one.

The VPN job derives its `connected` signal from the presence of a `/sys/class/net/<iface>` directory rather than from network activity — this is cheap, race-free, and avoids touching the VPN client process.

## Reliability

`subprocess_safe.py` wraps subprocess invocations with a uniform timeout, output-capture, and exception policy so that one misbehaving external command can't hang the scheduler. The pacman hook also uses this wrapper.

The OBS connection is re-established lazily on each tick if the previous attempt failed, so leaving OBS closed (or not authenticated) degrades cleanly to `streaming: false, obs: false` instead of crashing the job.

## Relation to Clients

Streams are theme-agnostic and contain no presentation logic. Clients (e.g. qtile widgets in [yths.dot-files](https://github.com/yths/yths.dot-files)) subscribe to whichever streams they want and apply their own theme to the rendered output. The `audio` and `stream` streams in particular are designed for live status indicators.
