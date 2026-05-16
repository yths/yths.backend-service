# Backend Service

A system metrics collector that publishes bluetooth, power supply, audio, OBS streaming, VPN, geolocation, and system-update data to Redis streams. Designed as a theme-agnostic data source for live dashboards and status widgets.

## Getting Started

Clone this repository and follow [docs/install.md](docs/install.md).

```bash
git clone https://github.com/yths/yths.backend-service.git
```

## Dependencies

* [IPinfo](https://ipinfo.io/) — an API access token is required by the location job, which also provides sunrise/sunset times (used by theme-aware dark/light mode switching in clients).

## Documentation

* [docs/install.md](docs/install.md) — installation, configuration, credentials, optional pacman hook
* [docs/notes.md](docs/notes.md) — Redis stream schemas and design notes
* [docs/tips.md](docs/tips.md) — debugging recipes and operational tips
* [docs/issues.md](docs/issues.md) — known gaps and roadmap

## Tests

```bash
yay -S python-pytest
pytest
```
