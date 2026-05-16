# Installation

## Disclaimer

This service polls system state and external APIs, then publishes the results to a Redis database. Assume any of these can fail or behave unexpectedly. Treat the credentials file as sensitive — it contains an API token and an optional OBS WebSocket password.

## Dependencies

Install the required Python packages and the Redis (or Valkey) server:

```bash
yay -S python-redis python-schedule python-requests python-rich python-gobject valkey
```

For the optional pacman hook (see below), also install:

```bash
yay -S pacman-contrib yay
```

An access token from [https://ipinfo.io](https://ipinfo.io) is required for the location job.

## Configuration

The service reads its Redis and OBS endpoints from environment variables (defaults shown):

```bash
BACKEND_REDIS_HOST=localhost
BACKEND_REDIS_PORT=6379
BACKEND_REDIS_DB=1
BACKEND_OBS_HOST=localhost
BACKEND_OBS_PORT=4455
```

To override these persistently, drop the overrides into `~/.config/backend.env` (one `KEY=VALUE` per line) — the systemd unit picks the file up automatically and ignores it if absent.

### Credentials

Copy the credentials template and fill in the values:

```bash
cp credentials.template.json ~/.config/credentials.json
```

| Field | Required | Description |
|---|---|---|
| `IPINFO_TOKEN` | yes | Token from [ipinfo.io](https://ipinfo.io); used by the location job |
| `OBS_PASSWORD` | no | OBS WebSocket password; leave empty to connect without authentication |

## Service Installation

Clone the repository and install the user-level systemd unit:

```bash
cd ~/repositories
git clone https://github.com/yths/yths.backend-service.git
cd yths.backend-service
mkdir -p ~/.local/share/systemd/user
cp backend.service ~/.local/share/systemd/user/
systemctl --user enable --now backend
```

## Pacman Hook (Arch only)

The optional `PostTransaction` hook refreshes the outstanding-updates count in Redis immediately after every pacman transaction, instead of waiting up to an hour for the next tick of `job_updates`. It requires `pacman-contrib` (for `checkupdates`) and `yay`.

```bash
sudo install -m 755 pacman_post_transaction.py /usr/local/bin/pacman-redis-updates
sudo install -m 644 update_count.py /usr/local/bin/update_count.py
sudo install -m 644 redis-updates.hook /etc/pacman.d/hooks/
```

The hook runs as root; the script re-execs itself via `runuser` as the lowest-UID regular user (UID 1000–59999 with a real login shell) to run `checkupdates` and `yay -Qua`, since both refuse to run as root. Redis is contacted on `localhost` and honours the same `BACKEND_REDIS_HOST` / `BACKEND_REDIS_PORT` / `BACKEND_REDIS_DB` variables as the main service.

The installed copies in `/usr/local/bin/` are snapshots — re-run the `install` commands after editing the source files in the repo.
