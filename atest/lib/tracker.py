"""
Execution tracker for pabot exclusive-lock acceptance tests.

Each test records its start/end to a shared JSON-Lines log file.
After all tests finish, `verify_exclusivity()` asserts that no exclusive test
overlapped with any parallel test, and that exclusive tests did not overlap
each other.
"""
import json
import os
import time

try:
    import fcntl
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False

# Log file lives next to the atest/ directory, e.g. atest/_exec_log.txt
_LOG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "_exec_log.txt"
)


def _write(record):
    line = json.dumps(record)
    with open(_LOG_FILE, "a") as f:
        if _HAS_FLOCK:
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line + "\n")
            f.flush()
        finally:
            if _HAS_FLOCK:
                fcntl.flock(f, fcntl.LOCK_UN)


def log_parallel_start(test_name):
    """Record that a parallel (non-exclusive) test started."""
    _write({"event": "start", "kind": "parallel", "time": time.time(), "name": test_name})


def log_exclusive_start(test_name):
    """Record that an exclusive test started."""
    _write({"event": "start", "kind": "exclusive", "time": time.time(), "name": test_name})


def log_test_end(test_name):
    """Record that a test ended."""
    _write({"event": "end", "time": time.time(), "name": test_name})


def verify_exclusivity():
    """
    Parse the execution log and assert:
    1. No exclusive test overlapped with any parallel test.
    2. No two exclusive tests overlapped each other (sequential execution).

    Returns a summary string on success.
    Raises AssertionError describing every violation found.
    """
    if not os.path.exists(_LOG_FILE):
        raise AssertionError("Execution log not found: " + _LOG_FILE)

    parallel = {}   # name -> {"start": float, "end": float|None}
    exclusive = {}  # name -> {"start": float, "end": float|None}

    with open(_LOG_FILE) as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                r = json.loads(raw)
            except json.JSONDecodeError:
                continue
            name = r.get("name", "?")
            if r["event"] == "start":
                entry = {"start": r["time"], "end": None}
                if r["kind"] == "parallel":
                    parallel[name] = entry
                else:
                    exclusive[name] = entry
            elif r["event"] == "end":
                ts = r["time"]
                for bucket in (parallel, exclusive):
                    if name in bucket:
                        bucket[name]["end"] = ts

    violations = []

    # 1. No parallel/exclusive overlap
    for exc_name, exc in exclusive.items():
        for par_name, par in parallel.items():
            if par["start"] < exc["start"] and (
                par["end"] is None or par["end"] > exc["start"]
            ):
                violations.append(
                    "  OVERLAP: exclusive '{}' (t={:.3f}) with parallel '{}' "
                    "(start={:.3f}, end={})".format(
                        exc_name, exc["start"],
                        par_name, par["start"], par["end"]
                    )
                )

    # 2. No exclusive/exclusive overlap
    sorted_exc = sorted(exclusive.items(), key=lambda x: x[1]["start"])
    for i in range(len(sorted_exc) - 1):
        n1, d1 = sorted_exc[i]
        n2, d2 = sorted_exc[i + 1]
        if d1["end"] is not None and d2["start"] < d1["end"]:
            violations.append(
                "  OVERLAP: exclusive '{}' and exclusive '{}'".format(n1, n2)
            )

    if violations:
        raise AssertionError(
            "{} exclusivity violation(s) detected:\n{}".format(
                len(violations), "\n".join(violations)
            )
        )

    return (
        "VERIFIED: {} exclusive test(s) ran alone, "
        "{} parallel test(s) ran concurrently.".format(
            len(exclusive), len(parallel)
        )
    )
