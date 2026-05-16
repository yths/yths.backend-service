import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time

import gi.repository.Gio
import redis
import requests
import schedule
import obsws_python


logging.getLogger("obsws_python").setLevel(logging.CRITICAL)

OBS_HOST = os.environ.get("NBS_OBS_HOST", "localhost")
OBS_PORT = int(os.environ.get("NBS_OBS_PORT", 4455))


def job_stream(r, host=OBS_HOST, port=OBS_PORT, password=None):
    obs_running = True
    streaming = True
    try:
        if password is None:
            client = obsws_python.ReqClient(host=host, port=port, timeout=1)
        else:
            client = obsws_python.ReqClient(host=host, port=port, password=password, timeout=1)
        status = client.get_stream_status()
        client.disconnect()
        streaming = status.output_active
    except (ConnectionRefusedError, OSError, TimeoutError):
        streaming = False
        obs_running = False
    r.xadd(
        "stream",
        {"measurement": json.dumps({"streaming": streaming, "obs": obs_running})},
    )
    

def job_location(r, token=None):
    if token is not None:
        try:
            response = requests.get(f"https://ipinfo.io?token={token}", timeout=5)
            data = response.json()
            longitude = float(data["loc"].split(",")[1])
            latitude = float(data["loc"].split(",")[0])

            ip_address = data["ip"]
            timezone = data["timezone"]

            response = requests.get(
                f"https://api.sunrisesunset.io/json?lat={latitude}&lng={longitude}&timezone={data['timezone']}&time_format=24",
                timeout=5,
            )
            data = response.json()
            sunrise = data["results"]["sunrise"]
            sunset = data["results"]["sunset"]

            r.xadd(
                "location",
                {
                    "measurement": json.dumps(
                        {
                            "latitude": latitude,
                            "longitude": longitude,
                            "ip_address": ip_address,
                            "timezone": timezone,
                            "sunrise": sunrise,
                            "sunset": sunset,
                        }
                    )
                },
            )
        except (requests.exceptions.RequestException, ValueError, KeyError):
            logging.exception("job_location failed")


def job_audio(r):
    try:
        result = subprocess.run(
            ["pactl", "get-sink-mute", "@DEFAULT_SINK@"],
            capture_output=True, text=True, timeout=5,
        )
        muted = result.stdout.strip().split(" ")[-1] == "yes"
        result = subprocess.run(
            ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
            capture_output=True, text=True, timeout=5,
        )
        volume = int(result.stdout.strip().split("/")[1].strip().replace("%", ""))
        r.xadd("audio", {"measurement": json.dumps({"muted": muted, "volume": volume})})
    except (subprocess.SubprocessError, ValueError, IndexError):
        logging.exception("job_audio failed")
    

def job_updates(r):
    try:
        if platform.freedesktop_os_release()["NAME"] != "Ubuntu":
            result = subprocess.run(
                "yay -Qua --color never | wc -l",
                shell=True, capture_output=True, text=True, timeout=60,
            )
            try:
                outstanding_updates = int(result.stdout.strip())
            except ValueError:
                outstanding_updates = 0

            result = subprocess.run(
                "checkupdates | wc -l",
                shell=True, capture_output=True, text=True, timeout=60,
            )
            try:
                outstanding_updates += int(result.stdout.strip())
            except ValueError:
                outstanding_updates += 0
        else:
            result = subprocess.run(
                ["/usr/lib/update-notifier/apt-check"],
                capture_output=True, text=True, timeout=60,
            )
            try:
                outstanding_updates = int(result.stdout.split(";")[0])
            except ValueError:
                outstanding_updates = 0

        r.xadd(
            "updates",
            {"measurement": json.dumps({"outstanding_updates": outstanding_updates})},
        )
    except (subprocess.SubprocessError, OSError):
        logging.exception("job_updates failed")


def job_bluetooth(r, manager):
    connected_devices = set()
    try:
        objects = manager.GetManagedObjects()
    except gi.repository.GLib.Error:
        objects = dict()
    for path, data in objects.items():
        status = data.get("org.bluez.Device1", {}).get("Connected", False)
        if status:
            address = data.get("org.bluez.Device1", {}).get("Address", "Unknown")
            capacity = data.get("org.bluez.Battery1", {}).get(
                "Percentage", "Unknown"
            )
            connected_devices.add((address, capacity))
    r.xadd(
        "bluetooth",
        {
            "measurement": json.dumps(
                {
                    device: {"capacity": capacity}
                    for device, capacity in connected_devices
                }
            )
        },
    )


def job_powersupply(r):
    grid = True
    batteries = dict()
    try:
        for filename in os.listdir("/sys/class/power_supply/"):
            if filename.startswith("BAT"):
                with open(
                    os.path.join("/sys/class/power_supply/", filename, "capacity")
                ) as f:
                    capacity = f.read().strip()
                with open(
                    os.path.join("/sys/class/power_supply/", filename, "status")
                ) as f:
                    status = f.read().strip()
                    if status == "Discharging":
                        grid = False
                batteries[filename] = {"capacity": capacity, "status": status}
        r.xadd(
            "power_supply",
            {"measurement": json.dumps({"grid": grid, "batteries": batteries})},
        )
    except OSError:
        logging.exception("job_powersupply failed")


def job_vpn(r):
    connected = False
    country = ""
    city = ""

    if shutil.which("nordvpn") is not None:
        try:
            result = subprocess.run(
                ["nordvpn", "status"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().split("\n"):
                if line.startswith("Status:"):
                    status = line.split(":", 1)[1].strip()
                    if status == "Connected":
                        connected = True
                elif line.startswith("Country:"):
                    country = line.split(":", 1)[1].strip()
                elif line.startswith("City:"):
                    city = line.split(":", 1)[1].strip()
        except subprocess.SubprocessError:
            logging.exception("job_vpn failed")

    r.xadd(
        "vpn",
        {"measurement": json.dumps({"connected": connected, "country": country, "city": city})},
    )


if __name__ == "__main__":
    try:
        r = redis.Redis(host=os.environ.get("NBS_REDIS_HOST", "localhost"), port=int(os.environ.get("NBS_REDIS_PORT", 6379)), db=int(os.environ.get("NBS_REDIS_DB", 1)))
        r.ping()
    except redis.exceptions.ConnectionError:
        sys.exit(1)

    manager = gi.repository.Gio.DBusProxy().new_for_bus_sync(
        **{
            "bus_type": gi.repository.Gio.BusType.SYSTEM,
            "name": "org.bluez",
            "object_path": "/",
            "interface_name": "org.freedesktop.DBus.ObjectManager",
            "flags": gi.repository.Gio.DBusProxyFlags.NONE,
            "info": None,
            "cancellable": None,
        }
    )

    if os.path.exists(os.path.expanduser("~/.config/credentials.json")):
        with open(os.path.expanduser("~/.config/credentials.json")) as input_handle:
            credentials = json.load(input_handle)
    else:
        credentials = dict()

    schedule.every().second.do(job_bluetooth, r=r, manager=manager)
    schedule.every().second.do(job_powersupply, r=r)
    schedule.every().hour.do(job_updates, r=r)
    schedule.every().hour.at(":30").do(
        job_location, r=r, token=credentials.get("IPINFO_TOKEN")
    )
    schedule.every().second.do(job_audio, r=r)
    schedule.every().second.do(job_stream, r=r)
    schedule.every(10).seconds.do(job_vpn, r=r)

    schedule.run_all()
    while True:
        schedule.run_pending()
        time.sleep(1)
