import subprocess
from unittest.mock import patch

import update_count


class _FakeProc:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def test_count_lines_returns_line_count():
    with patch("update_count.subprocess_safe.run", return_value=_FakeProc("a\nb\nc\n")):
        assert update_count._count_lines(["x"]) == 3


def test_count_lines_handles_no_trailing_newline():
    with patch("update_count.subprocess_safe.run", return_value=_FakeProc("a\nb")):
        assert update_count._count_lines(["x"]) == 2


def test_count_lines_handles_empty_output():
    with patch("update_count.subprocess_safe.run", return_value=_FakeProc("")):
        assert update_count._count_lines(["x"]) == 0


def test_count_lines_returns_zero_on_subprocess_error():
    with patch(
        "update_count.subprocess_safe.run",
        side_effect=subprocess.SubprocessError,
    ):
        assert update_count._count_lines(["x"]) == 0


def test_count_lines_returns_zero_on_timeout():
    with patch(
        "update_count.subprocess_safe.run",
        side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1),
    ):
        assert update_count._count_lines(["x"]) == 0


def test_arch_sums_yay_and_checkupdates():
    with patch("update_count._count_lines", side_effect=[3, 5]):
        assert update_count._arch() == 8


def test_ubuntu_parses_first_field():
    with patch("update_count.subprocess_safe.run", return_value=_FakeProc("7;3")):
        assert update_count._ubuntu() == 7


def test_ubuntu_returns_zero_on_malformed_output():
    with patch("update_count.subprocess_safe.run", return_value=_FakeProc("garbage")):
        assert update_count._ubuntu() == 0


def test_ubuntu_returns_zero_on_subprocess_error():
    with patch(
        "update_count.subprocess_safe.run",
        side_effect=subprocess.SubprocessError,
    ):
        assert update_count._ubuntu() == 0


def test_dispatches_to_ubuntu_on_ubuntu():
    with patch(
        "update_count.platform.freedesktop_os_release",
        return_value={"NAME": "Ubuntu"},
    ), patch("update_count._ubuntu", return_value=17):
        assert update_count.count_outstanding_updates() == 17


def test_dispatches_to_arch_otherwise():
    with patch(
        "update_count.platform.freedesktop_os_release",
        return_value={"NAME": "Arch Linux"},
    ), patch("update_count._arch", return_value=42):
        assert update_count.count_outstanding_updates() == 42
