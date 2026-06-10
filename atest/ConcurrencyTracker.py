"""Process-safe concurrency tracker for pabot acceptance tests.

Each pabot worker is a separate OS process, so we use fcntl advisory locking
on a shared JSON file to safely read/modify concurrent test state.

Set PABOT_TRACKER_FILE env var to override the default tracker location.
"""
import fcntl
import json
import os
import time

_DEFAULT_TRACKER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".concurrent_tracker.json"
)


def _tracker_path():
    return os.environ.get("PABOT_TRACKER_FILE", _DEFAULT_TRACKER)


def _update(name, active):
    """Atomically set the active flag for *name* in the shared tracker file."""
    path = _tracker_path()
    # 'a+' creates the file if missing; flock gives us exclusive write access
    with open(path, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        content = f.read()
        data = json.loads(content) if content.strip() else {}
        entry = data.get(name, {})
        entry["active"] = active
        if active:
            entry["start"] = time.time()
        else:
            entry.setdefault("start", time.time())
            entry["end"] = time.time()
        data[name] = entry
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent=2)
        # flock released on file close


def mark_running(name):
    """Register that *name* has started running."""
    _update(name, active=True)


def mark_done(name):
    """Register that *name* has finished."""
    _update(name, active=False)


def assert_running_alone(name):
    """Raise AssertionError if any other test is currently marked as active.

    Called from within an exclusive test after a short grace-period sleep so
    that any truly concurrent test has had time to call mark_running().
    """
    path = _tracker_path()
    try:
        with open(path) as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f, fcntl.LOCK_UN)
    except (FileNotFoundError, json.JSONDecodeError):
        return  # No tracker yet — we are the very first test, fine

    concurrent = [n for n, v in data.items() if v.get("active") and n != name]
    if concurrent:
        raise AssertionError(
            "pabot:exclusive test '%s' is NOT running alone!\n"
            "Concurrent active tests: %s" % (name, concurrent)
        )
