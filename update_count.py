"""Count outstanding system package updates for the host distribution."""
import platform
import subprocess


def count_outstanding_updates():
    """Return the number of pending package updates for this host.

    Handles Arch (yay -Qua + checkupdates) and Ubuntu (apt-check).
    Individual sub-commands that fail contribute 0 to the total. Raises
    OSError if /etc/os-release cannot be read.
    """
    if platform.freedesktop_os_release()["NAME"] == "Ubuntu":
        return _ubuntu()
    return _arch()


def _line_count_via_wc(cmd):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=60,
        )
        return int(result.stdout.strip())
    except (subprocess.SubprocessError, ValueError):
        return 0


def _arch():
    return (
        _line_count_via_wc("yay -Qua --color never | wc -l")
        + _line_count_via_wc("checkupdates | wc -l")
    )


def _ubuntu():
    try:
        result = subprocess.run(
            ["/usr/lib/update-notifier/apt-check"],
            capture_output=True, text=True, timeout=60,
        )
        return int(result.stdout.split(";")[0])
    except (subprocess.SubprocessError, ValueError):
        return 0
