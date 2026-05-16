"""subprocess.run replacement that strictly bounds wall time.

The standard library's subprocess.run(timeout=N) sends SIGKILL to the
child after N seconds, but then waits indefinitely for it to be reaped.
If the child is in uninterruptible sleep (D state on a wedged socket
or filesystem call) or has spawned descendants that outlive it, that
wait can hang and pin the calling thread forever.

This module puts the child in its own session (start_new_session=True),
sends SIGKILL to the whole process group on TimeoutExpired, then waits
at most _REAP_TIMEOUT additional seconds. If the secondary wait also
times out, TimeoutExpired is raised regardless — the orphaned child
remains adopted by init.
"""
import os
import signal
import subprocess


_REAP_TIMEOUT = 2


def run(argv, timeout, **kwargs):
    """Run argv with a strict wall-time bound. Same return shape as subprocess.run."""
    kwargs.setdefault("stdout", subprocess.PIPE)
    kwargs.setdefault("stderr", subprocess.PIPE)
    kwargs.setdefault("text", True)
    kwargs.setdefault("errors", "replace")
    proc = subprocess.Popen(argv, start_new_session=True, **kwargs)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.communicate(timeout=_REAP_TIMEOUT)
        except subprocess.TimeoutExpired:
            pass
        raise
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)
