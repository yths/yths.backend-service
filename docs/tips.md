# Tips

## Inspect Live Streams with `redis_debug.py`

A live TUI lists every key in the configured Redis DB, refreshing once per second. Streams show length, age of the newest entry, and a preview of the latest payload — useful for verifying that the service is publishing what you expect.

```bash
python3 redis_debug.py
```

Keybindings:

* `q` (or `Ctrl+C`) — quit
* `?` / `h` — toggle the help panel

The tool honours the same `BACKEND_REDIS_*` environment variables as the service.

## Refresh the Updates Count On Demand

Outside of the hourly tick and the pacman hook, you can force-refresh the updates count by running the hook script directly as your user:

```bash
python3 pacman_post_transaction.py
```

This is the fastest way to verify that `checkupdates` and `yay -Qua` are wired up correctly without waiting for the next pacman transaction.

## Test the OBS Connection

If the `stream` widget on the client side stays at `obs: false`, the service is unable to reach OBS WebSocket. Common causes:

* OBS isn't running, or the WebSocket plugin isn't enabled.
* `BACKEND_OBS_HOST` / `BACKEND_OBS_PORT` point at the wrong endpoint.
* `OBS_PASSWORD` in `~/.config/credentials.json` doesn't match OBS WebSocket's configured password (an empty string disables auth on both sides).

Tail the journal for the service to see the OBS error message:

```bash
journalctl --user -u backend -f
```

## Reset a Stream Without Restarting

Streams are capped at ~86 400 entries, but you can clear one explicitly if you want a clean slate (e.g. after fixing a misbehaving job):

```bash
redis-cli -n 1 DEL bluetooth
```

The next tick of the relevant job will recreate the stream with a fresh first entry.
