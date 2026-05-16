import subprocess
import time

import subprocess_safe


def test_happy_path_captures_stdout():
    r = subprocess_safe.run(["echo", "hello"], timeout=2)
    assert r.stdout.strip() == "hello"
    assert r.returncode == 0


def test_returncode_propagates():
    r = subprocess_safe.run(["sh", "-c", "exit 7"], timeout=2)
    assert r.returncode == 7


def test_stderr_captured():
    r = subprocess_safe.run(["sh", "-c", "echo oops >&2"], timeout=2)
    assert r.stderr.strip() == "oops"


def test_text_replace_decodes_invalid_utf8():
    # \xff is not valid UTF-8; errors="replace" should not raise.
    r = subprocess_safe.run(
        ["sh", "-c", r"printf '\xff'"], timeout=2,
    )
    assert isinstance(r.stdout, str)


def test_timeout_raises_within_bounded_wall_time():
    # Child traps SIGTERM, so SIGKILL via the process group is the only
    # way to bound wall time. The helper must raise TimeoutExpired and
    # return within timeout + REAP_TIMEOUT seconds.
    t0 = time.monotonic()
    raised = False
    try:
        subprocess_safe.run(
            ["sh", "-c", 'trap "" TERM; sleep 30'], timeout=1,
        )
    except subprocess.TimeoutExpired:
        raised = True
    elapsed = time.monotonic() - t0
    assert raised, "expected TimeoutExpired"
    assert elapsed < 3.5, f"call took {elapsed:.2f}s, exceeded bound"
