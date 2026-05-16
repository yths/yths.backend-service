from collections import namedtuple
from unittest.mock import patch

import pacman_post_transaction


_PwEntry = namedtuple("PwEntry", ["pw_name", "pw_uid", "pw_gid", "pw_shell"])


def _entry(name, uid, shell="/bin/bash"):
    return _PwEntry(pw_name=name, pw_uid=uid, pw_gid=uid, pw_shell=shell)


def test_primary_user_returns_lowest_regular_uid():
    fake = [
        _entry("root", 0),
        _entry("bin", 1, "/usr/bin/nologin"),
        _entry("yths", 1000),
        _entry("other", 1001),
        _entry("nobody", 65534, "/usr/bin/nologin"),
    ]
    with patch("pacman_post_transaction.pwd.getpwall", return_value=fake):
        u = pacman_post_transaction._primary_user()
    assert u.pw_name == "yths"


def test_primary_user_returns_none_when_no_regular_users():
    fake = [
        _entry("root", 0),
        _entry("bin", 1, "/usr/bin/nologin"),
        _entry("nobody", 65534, "/usr/bin/nologin"),
    ]
    with patch("pacman_post_transaction.pwd.getpwall", return_value=fake):
        assert pacman_post_transaction._primary_user() is None


def test_primary_user_skips_nologin_shells():
    fake = [
        _entry("svc", 1000, "/usr/bin/nologin"),
        _entry("real", 1001, "/bin/bash"),
    ]
    with patch("pacman_post_transaction.pwd.getpwall", return_value=fake):
        u = pacman_post_transaction._primary_user()
    assert u.pw_name == "real"


def test_primary_user_skips_false_shells():
    fake = [
        _entry("svc", 1000, "/bin/false"),
        _entry("real", 1001, "/bin/bash"),
    ]
    with patch("pacman_post_transaction.pwd.getpwall", return_value=fake):
        u = pacman_post_transaction._primary_user()
    assert u.pw_name == "real"


def test_primary_user_skips_uids_above_range():
    fake = [
        _entry("nobody", 65534, "/bin/bash"),
        _entry("svc", 60000, "/bin/bash"),
        _entry("real", 1000, "/bin/bash"),
    ]
    with patch("pacman_post_transaction.pwd.getpwall", return_value=fake):
        u = pacman_post_transaction._primary_user()
    assert u.pw_name == "real"


def test_primary_user_skips_system_uids_below_1000():
    fake = [
        _entry("daemon", 999, "/bin/bash"),
        _entry("real", 1000, "/bin/bash"),
    ]
    with patch("pacman_post_transaction.pwd.getpwall", return_value=fake):
        u = pacman_post_transaction._primary_user()
    assert u.pw_name == "real"
