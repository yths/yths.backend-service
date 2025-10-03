import os
import sys

import redis

if  __name__ == "__main__":
    try:
        r = redis.Redis(host=os.environ.get("NBS_REDIS_HOST", "localhost"), port=int(os.environ.get("NBS_REDIS_PORT", 6379)), db=int(os.environ.get("NBS_REDIS_DB", 1)))
        r.ping()
    except redis.exceptions.ConnectionError:
        sys.exit(1)

    bluetooth_measurements = r.xrange("bluetooth")
    sorted_bluetooth = sorted(bluetooth_measurements, key=lambda x: x[0])
    for entry in sorted_bluetooth:
        entry_id, data = entry
        print(data)
        quit()