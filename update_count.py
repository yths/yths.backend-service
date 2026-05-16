"""Count outstanding system package updates for the host distribution."""
import platform
import subprocess

import subprocess_safe


def count_outstanding_updates():
    """Return the number of pending package updates for this host.

    Handles Arch (yay -Qua + checkupdates) and Ubuntu (apt-check).
    Individual sub-commands that fail contribute 0 to the total. Raises
    OSError if /etc/os-release cannot be read.
    """
    if platform.freedesktop_os_release()["NAME"] == "Ubuntu":
        return _ubuntu()
    return _arch()


def _count_lines(argv):
    """Run argv and return the number of stdout lines; 0 on subprocess error."""
    try:
        result = subprocess_safe.run(argv, timeout=60)
        return len(result.stdout.splitlines())
    except subprocess.SubprocessError:
        return 0


def _arch():
    return (
        _count_lines(["yay", "-Qua", "--color", "never"])
        + _count_lines(["checkupdates"])
    )


def _ubuntu():
    try:
        result = subprocess_safe.run(
            ["/usr/lib/update-notifier/apt-check"], timeout=60,
        )
        return int(result.stdout.split(";")[0])
    except (subprocess.SubprocessError, ValueError):
        return 0
