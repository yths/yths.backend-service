#!/usr/bin/env python3
"""Push the current outstanding-updates count to redis.

Invoked by the pacman PostTransaction hook so the dashboard reflects the
new state immediately instead of waiting up to an hour for the next tick
of job_updates in monitor.py.

When invoked as root (the pacman-hook case), re-execs itself via runuser
as the lowest-UID regular user (UID 1000..59999, with a real login shell)
before counting updates, since checkupdates and yay refuse to run as root.
"""
import json
import logging
import os
import pwd
import sys

import redis
import redis.exceptions

# Allow the import below to find update_count whether the script is run
# from the repo or installed alongside it to /usr/local/bin/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update_count


logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
)

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


def main():
    if os.geteuid() == 0:
        user = _primary_user()
        if user is None:
            logging.error("no regular user available; cannot drop privileges")
            return
        os.execvp(
            "runuser",
            ["runuser", "-u", user.pw_name, "--",
             sys.executable, os.path.abspath(__file__)],
        )

    try:
        outstanding = update_count.count_outstanding_updates()
    except OSError:
        logging.exception("update count failed")
        outstanding = 0

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
    except redis.exceptions.RedisError:
        logging.exception("redis write failed")


if __name__ == "__main__":
    main()
