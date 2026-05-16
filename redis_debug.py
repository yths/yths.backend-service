#!/usr/bin/env python3
"""Live TUI showing every key in the configured Redis DB.

Connection env vars mirror configuration/qtile/config.py:
    NBS_REDIS_HOST (default: localhost)
    NBS_REDIS_PORT (default: 6379)
    NBS_REDIS_DB   (default: 1)
"""
import argparse
import json
import os
import select
import sys
import termios
import time
import tty

import redis
import redis.exceptions
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


KEYBINDINGS = [
    ("q", "quit (Ctrl+C also works)"),
    ("?  /  h", "toggle this help"),
]


HOST = os.environ.get("NBS_REDIS_HOST", "localhost")
PORT = int(os.environ.get("NBS_REDIS_PORT", 6379))
DB = int(os.environ.get("NBS_REDIS_DB", 1))


def connect():
    pool = redis.ConnectionPool(
        host=HOST,
        port=PORT,
        db=DB,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
        health_check_interval=30,
    )
    return redis.Redis(connection_pool=pool)


def _decode(value):
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return repr(value)
    return str(value)


def _truncate(text, limit=80):
    text = text.replace("\n", " ")
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _format_measurement(payload):
    """Render a stream entry the way the qtile widgets consume it."""
    raw = payload.get(b"measurement") if isinstance(payload, dict) else None
    if raw is not None:
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _truncate(_decode(raw))
        if isinstance(data, dict):
            if not data:
                return "{}"
            return "  ".join(f"{k}={_truncate(str(v), 40)}" for k, v in data.items())
        return _truncate(json.dumps(data))
    rendered = ", ".join(f"{_decode(k)}={_decode(v)}" for k, v in payload.items())
    return _truncate(rendered) if rendered else "[no fields]"


def _stream_age(eid_str):
    """Age of a stream entry id ('<ms>-<seq>') as a short human string."""
    try:
        ms = int(eid_str.split("-", 1)[0])
    except (ValueError, AttributeError):
        return "?"
    age_s = max(0.0, time.time() - ms / 1000.0)
    if age_s < 1:
        return f"{age_s * 1000:.0f}ms"
    if age_s < 60:
        return f"{age_s:.1f}s"
    if age_s < 3600:
        return f"{age_s / 60:.1f}m"
    if age_s < 86400:
        return f"{age_s / 3600:.1f}h"
    return f"{age_s / 86400:.1f}d"


def peek(r, key, ktype):
    """Return (size, age, latest_repr) for a key based on its type."""
    if ktype == "stream":
        try:
            length = r.xlen(key)
            entries = r.xrevrange(key, count=1)
        except redis.exceptions.RedisError as e:
            return ("?", "—", f"[stream error: {e}]")
        if not entries:
            return (str(length), "—", "[empty]")
        eid, payload = entries[0]
        eid_str = _decode(eid)
        return (str(length), _stream_age(eid_str), f"{eid_str}  {_format_measurement(payload)}")

    if ktype == "string":
        value = r.get(key)
        if value is None:
            return ("0", "—", "[nil]")
        return (str(len(value)), "—", _truncate(_decode(value)))

    if ktype == "list":
        length = r.llen(key)
        head = r.lrange(key, 0, 0)
        preview = _truncate(_decode(head[0])) if head else "[empty]"
        return (str(length), "—", preview)

    if ktype == "hash":
        length = r.hlen(key)
        cursor, fields = r.hscan(key, count=3)
        items = list(fields.items())[:3]
        preview = ", ".join(f"{_decode(k)}={_truncate(_decode(v), 30)}" for k, v in items)
        if length > len(items):
            preview = preview + f", … (+{length - len(items)})"
        return (str(length), "—", preview or "[empty]")

    if ktype == "set":
        length = r.scard(key)
        members = list(r.sscan_iter(key, count=3))[:3]
        preview = ", ".join(_decode(m) for m in members)
        return (str(length), "—", preview or "[empty]")

    if ktype == "zset":
        length = r.zcard(key)
        members = r.zrange(key, 0, 2, withscores=True)
        preview = ", ".join(f"{_decode(m)}={s}" for m, s in members)
        return (str(length), "—", preview or "[empty]")

    return ("?", "—", f"[unknown type: {ktype}]")


def scan_keys(r):
    keys = []
    for key in r.scan_iter(match="*", count=200):
        keys.append(key)
    keys.sort()
    return keys


def _help_panel():
    text = Text()
    for i, (key, desc) in enumerate(KEYBINDINGS):
        if i:
            text.append("\n")
        text.append(key, style="bold cyan")
        text.append(f"  {desc}", style="dim")
    return Panel(text, title="keys", border_style="dim", expand=False)


def render(r, last_update_ts, error, show_help=False):
    title = f"Redis @ {HOST}:{PORT} db={DB}"
    if error:
        caption = f"[red]error:[/red] {error}   ·   press ? for help"
    else:
        delta = time.monotonic() - last_update_ts
        caption = f"updated {delta:.1f}s ago   ·   press ? for help"

    table = Table(title=title, caption=caption, expand=True)
    table.add_column("key", style="cyan", no_wrap=True)
    table.add_column("type", style="magenta", no_wrap=True)
    table.add_column("size", justify="right", style="green", no_wrap=True)
    table.add_column("age", justify="right", style="yellow", no_wrap=True)
    table.add_column("latest", overflow="fold")

    def _wrap(t):
        return Group(t, _help_panel()) if show_help else t

    if error:
        return _wrap(table)

    try:
        keys = scan_keys(r)
    except redis.exceptions.RedisError as e:
        table.caption = f"[red]scan error:[/red] {e}   ·   press ? for help"
        return _wrap(table)

    if not keys:
        table.add_row("—", "—", "—", "—", Text("(db is empty)", style="dim"))
        return _wrap(table)

    for key in keys:
        try:
            ktype = _decode(r.type(key))
        except redis.exceptions.RedisError as e:
            table.add_row(_decode(key), "?", "?", "—", f"[type error: {e}]")
            continue
        try:
            size, age, latest = peek(r, key, ktype)
        except redis.exceptions.RedisError as e:
            size, age, latest = "?", "—", f"[peek error: {e}]"
        table.add_row(_decode(key), ktype, size, age, latest)

    return _wrap(table)


def _setup_stdin():
    if not sys.stdin.isatty():
        return None
    old = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin)
    return old


def _restore_stdin(old):
    if old is not None:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)


def _poll_key(timeout):
    """Wait up to `timeout` seconds for a key press; return the char or None."""
    if not sys.stdin.isatty():
        time.sleep(timeout)
        return None
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        return None
    try:
        return sys.stdin.read(1)
    except OSError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="refresh interval in seconds (default: 1.0)",
    )
    args = parser.parse_args()

    console = Console()
    r = connect()
    last_update = time.monotonic()
    error = None
    show_help = False

    old_tty = _setup_stdin()
    try:
        with Live(render(r, last_update, error, show_help), console=console, refresh_per_second=4, screen=False) as live:
            while True:
                try:
                    r.ping()
                    error = None
                except redis.exceptions.RedisError as e:
                    error = str(e) or e.__class__.__name__
                live.update(render(r, last_update, error, show_help))
                if error is None:
                    last_update = time.monotonic()
                try:
                    key = _poll_key(args.interval)
                except KeyboardInterrupt:
                    break
                if key is None:
                    continue
                if key in ("q", "Q", "\x03"):
                    break
                if key in ("?", "h", "H"):
                    show_help = not show_help
                    live.update(render(r, last_update, error, show_help))
    finally:
        _restore_stdin(old_tty)


if __name__ == "__main__":
    main()
