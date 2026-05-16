#!/usr/bin/env python3
"""Push the current outstanding-updates count to redis.

Invoked by the pacman PostTransaction hook so the dashboard reflects the
new state immediately instead of waiting up to an hour for the next tick
of job_updates in monitor.py.

When invoked as root (the pacman-hook case), drops to the lowest-UID
regular user (UID 1000..59999, real shell) before running checkupdates
and yay -Qua, since both refuse to run as root. Redis is contacted on
localhost regardless of the running user.
"""
import json
import os
import pwd
import subprocess
import sys

import redis
import redis.exceptions


HOST = os.environ.get("NBS_REDIS_HOST", "localhost")
PORT = int(os.environ.get("NBS_REDIS_PORT", 6379))
DB = int(os.environ.get("NBS_REDIS_DB", 1))

STREAM_MAXLEN = 86400


def _primary_user():
    """Lowest-UID regular user with a real login shell, or None."""
    candidates = [
        e for e in pwd.getpwall()
        if 1000 <= e.pw_uid < 60000
        and not e.pw_shell.endswith(("nologin", "false"))
    ]
    return min(candidates, key=lambda e: e.pw_uid) if candidates else None


def _count(cmd):
    user = _primary_user() if os.geteuid() == 0 else None
    full = (
        ["runuser", "-u", user.pw_name, "--", "sh", "-c", cmd]
        if user is not None
        else ["sh", "-c", cmd]
    )
    try:
        result = subprocess.run(
            full, capture_output=True, text=True, timeout=60,
        )
        return int(result.stdout.strip() or 0)
    except (subprocess.SubprocessError, ValueError):
        return 0


def main():
    outstanding = _count("checkupdates | wc -l")
    outstanding += _count("yay -Qua --color never | wc -l")

    try:
        r = redis.Redis(
            host=HOST, port=PORT, db=DB,
            socket_timeout=5, socket_connect_timeout=2,
        )
        r.xadd(
            "updates",
            {"measurement": json.dumps({"outstanding_updates": outstanding})},
            maxlen=STREAM_MAXLEN, approximate=True,
        )
    except redis.exceptions.RedisError as e:
        print(f"redis write failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
