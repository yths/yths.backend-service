# nuunamnir Backend Service

A small Python script that collects the following system metrics and stores them in a redis/valkey database.

* connected bluetooth devices and their current battery level (if available)
* power supply statistics (grid or batteries with their current level)
* available system updates
* IP based location and sunrise and sunset time (e.g., for controlling dark or light mode)

It is used in conjunction with the system configuration that can be found [here](https://github.com/nuunamnir/nuunamnir.dot-files).

## Dependencies

Install the following dependencies:

```bash
yay -S python-redis python-schedule python-requests python-rich python-gobject valkey
```

For the optional pacman hook (see below) also install:

```bash
yay -S pacman-contrib yay
```

You also need an access token from [https://ipinfo.io](https://ipinfo.io).

## Installation

Configuration is read from the following environment variables (defaults shown):

```bash
NBS_REDIS_HOST=localhost
NBS_REDIS_PORT=6379
NBS_REDIS_DB=1
NBS_OBS_HOST=localhost
NBS_OBS_PORT=4455
```

To override them persistently, drop the overrides into `~/.config/nuunamnir.backend.env` (one `KEY=VALUE` per line) — the systemd unit picks the file up automatically and ignores it if absent.
Get the latest version of the backend service:
```
cd ~/repositories
git clone git@github.com:nuunamnir/nuunamnir.backend-service.git
```
Then activate the service.
```bash
cd nuunamnir.backend-service
mkdir -p ~/.local/share/systemd/user
cp nuunamnir.backend.service ~/.local/share/systemd/user/
systemctl --user enable --now nuunamnir.backend
```

### Credentials

Copy the credentials file template to `~/.config/credentials.json` and replace the placeholder with your access token for the IP service.

```bash
cp credentials.template.json ~/.config/credentials.json
```

### Pacman Hook (Arch only)

Optionally install a pacman `PostTransaction` hook that refreshes the outstanding-updates count in redis immediately after every transaction, instead of waiting up to an hour for the next tick of `job_updates`. Requires `pacman-contrib` (provides `checkupdates`) and `yay`.

```bash
sudo install -m 755 pacman_post_transaction.py /usr/local/bin/pacman-redis-updates
sudo install -m 644 update_count.py /usr/local/bin/update_count.py
sudo install -m 644 redis-updates.hook /etc/pacman.d/hooks/
```

The hook runs as root; the script re-execs itself via `runuser` as the lowest-UID regular user (UID 1000–59999 with a real login shell) to run `checkupdates` and `yay -Qua`, since both refuse to run as root. Redis is contacted on `localhost` and honours the same `NBS_REDIS_HOST` / `NBS_REDIS_PORT` / `NBS_REDIS_DB` environment variables as the main service.

The installed copies in `/usr/local/bin/` are snapshots — re-run the `install` commands after editing the source files in the repo.

## Tools

### `redis_debug.py`

A live TUI listing every key in the configured redis DB, refreshing once per second. Streams show length, age of the newest entry, and a preview of the latest payload — useful for verifying that the service is publishing what you expect.

```bash
python redis_debug.py
```

Keybindings:

* `q` (or `Ctrl+C`) — quit
* `?` / `h` — toggle the help panel

## Streams

Each stream stores entries with a single `measurement` field containing a JSON object. Schemas:

| Stream         | Frequency               | Payload keys                                                                                                       |
| -------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `bluetooth`    | 1 s                     | map of `<MAC>` → `{ "capacity": <int>\|"Unknown" }`                                                                |
| `power_supply` | 1 s                     | `grid: bool`, `batteries: { <name>: { "capacity": str, "status": str } }`                                          |
| `audio`        | 1 s                     | `muted: bool`, `volume: int`                                                                                       |
| `stream`       | 1 s                     | `streaming: bool`, `obs: bool`                                                                                     |
| `vpn`          | 10 s                    | `connected: bool`, `country: str`, `city: str`                                                                     |
| `updates`      | hourly (+ pacman hook)  | `outstanding_updates: int`                                                                                         |
| `location`     | hourly at xx:30         | `latitude: float`, `longitude: float`, `ip_address: str`, `timezone: str`, `sunrise: str`, `sunset: str`           |

All streams are capped at ~86 400 entries (≈ 24 h of 1 Hz data) via `XADD ... MAXLEN ~`.