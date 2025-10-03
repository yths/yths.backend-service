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
yay -S python-redis python-schedule valkey
```

You also need an access token from [https://ipinfo.io](https://ipinfo.io).

## Installation

In case you do not want to use the default redis backend, you can set the following environment variables (make sure they are available before the backend service starts):
```bash
NBS_REDIS_HOST=localhost
NBS_REDIS_PORT=6379
NBS_REDIS_DB=1
```
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
````