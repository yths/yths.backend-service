import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time

import gi.repository.Gio
import redis
import requests
import schedule
import obsws_python

import update_count


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("obsws_python").setLevel(logging.CRITICAL)

OBS_HOST = os.environ.get("NBS_OBS_HOST", "localhost")
OBS_PORT = int(os.environ.get("NBS_OBS_PORT", 4455))

# Cap each stream at roughly 24h of 1Hz data so redis memory stays bounded.
STREAM_MAXLEN = 86400

_job_locks = {}


def run_threaded(job_func, *args, **kwargs):
    """Dispatch `job_func` in a daemon thread. If a previous invocation of
    the same function is still running, drop this tick — that way a slow job
    cannot pile up overlapping threads or block faster jobs."""
    lock = _job_locks.setdefault(job_func, threading.Lock())
    if not lock.acquire(blocking=False):
        return

    def target():
        try:
            job_func(*args, **kwargs)
        except Exception:
            logging.exception("%s raised", job_func.__name__)
        finally:
            lock.release()

    threading.Thread(target=target, daemon=True).start()


def job_stream(r, host=OBS_HOST, port=OBS_PORT, password=None):
    obs_running = False
    streaming = False
    try:
        if password is None:
            client = obsws_python.ReqClient(host=host, port=port, timeout=1)
        else:
            client = obsws_python.ReqClient(
                host=host, port=port, password=password, timeout=1,
            )
        status = client.get_stream_status()
        client.disconnect()
        obs_running = True
        streaming = status.output_active
    except (ConnectionRefusedError, OSError, TimeoutError):
        pass
    r.xadd(
        "stream",
        {"measurement": json.dumps({"streaming": streaming, "obs": obs_running})},
        maxlen=STREAM_MAXLEN, approximate=True,
    )


def job_location(r, token=None):
    # Composite payload — a partial result would mislead consumers, so this
    # job is the one exception to the "always xadd" rule: skip on error.
    if token is None:
        return
    try:
        response = requests.get(f"https://ipinfo.io?token={token}", timeout=5)
        data = response.json()
        longitude = float(data["loc"].split(",")[1])
        latitude = float(data["loc"].split(",")[0])

        ip_address = data["ip"]
        timezone = data["timezone"]

        response = requests.get(
            f"https://api.sunrisesunset.io/json?lat={latitude}&lng={longitude}&timezone={timezone}&time_format=24",
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
            maxlen=STREAM_MAXLEN, approximate=True,
        )
    except (requests.exceptions.RequestException, ValueError, KeyError):
        logging.exception("job_location failed")


def job_audio(r):
    muted = False
    volume = 0
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
    except (subprocess.SubprocessError, ValueError, IndexError):
        logging.exception("job_audio failed")
    r.xadd(
        "audio",
        {"measurement": json.dumps({"muted": muted, "volume": volume})},
        maxlen=STREAM_MAXLEN, approximate=True,
    )


def job_updates(r):
    outstanding_updates = 0
    try:
        outstanding_updates = update_count.count_outstanding_updates()
    except OSError:
        logging.exception("job_updates failed")
    r.xadd(
        "updates",
        {"measurement": json.dumps({"outstanding_updates": outstanding_updates})},
        maxlen=STREAM_MAXLEN, approximate=True,
    )


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
        maxlen=STREAM_MAXLEN, approximate=True,
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
    except OSError:
        logging.exception("job_powersupply failed")
    r.xadd(
        "power_supply",
        {"measurement": json.dumps({"grid": grid, "batteries": batteries})},
        maxlen=STREAM_MAXLEN, approximate=True,
    )


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
        maxlen=STREAM_MAXLEN, approximate=True,
    )


if __name__ == "__main__":
    try:
        r = redis.Redis(
            host=os.environ.get("NBS_REDIS_HOST", "localhost"),
            port=int(os.environ.get("NBS_REDIS_PORT", 6379)),
            db=int(os.environ.get("NBS_REDIS_DB", 1)),
            socket_timeout=5,
            socket_connect_timeout=2,
            retry_on_timeout=True,
        )
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

    schedule.every().second.do(run_threaded, job_bluetooth, r=r, manager=manager)
    schedule.every().second.do(run_threaded, job_powersupply, r=r)
    schedule.every().hour.do(run_threaded, job_updates, r=r)
    schedule.every().hour.at(":30").do(
        run_threaded, job_location, r=r, token=credentials.get("IPINFO_TOKEN")
    )
    schedule.every().second.do(run_threaded, job_audio, r=r)
    schedule.every().second.do(run_threaded, job_stream, r=r)
    schedule.every(10).seconds.do(run_threaded, job_vpn, r=r)

    schedule.run_all()
    try:
        while True:
            try:
                schedule.run_pending()
            except Exception:
                logging.exception("scheduler tick failed")
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("shutting down")
