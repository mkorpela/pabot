"""Acceptance tests for the pabot:exclusive tag feature.

Tests in atest/ that carry the [Tags]    pabot:exclusive tag must run completely
alone — no other test (normal or exclusive) may execute in parallel with them.

Suites used
-----------
- suite_01 … suite_03  : normal tests (run in parallel across up to 4 workers)
- suite_04              : mixed suite (1 normal + 1 exclusive test)
- suite_05              : pure exclusive suite (2 exclusive tests)

Verification strategy
---------------------
Robot Framework 7 records ``start`` (ISO-8601) and ``elapsed`` (seconds) on
every ``<status>`` element.  After pabot finishes we parse output.xml and check
that no exclusive test's time window overlaps with any other test's window.
"""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATEST_DIR = os.path.join(REPO_ROOT, "atest")
SRC_DIR = os.path.join(REPO_ROOT, "src")
PABOT_TAG = "pabot:exclusive"

EXPECTED_EXCLUSIVE_TESTS = 3  # 1 (suite_04) + 2 (suite_05)
EXPECTED_TOTAL_TESTS = 10  # suite_01..03: 3*2=6, suite_04: 2, suite_05: 2

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_pabot(output_dir, extra_args=None):
    """Run pabot against atest/ and return CompletedProcess."""
    cmd = [
        sys.executable,
        "-m",
        "pabot.pabot",
        "--processes",
        "4",
        "--outputdir",
        str(output_dir),
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(ATEST_DIR)

    env = {**os.environ, "PYTHONPATH": SRC_DIR}
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def _parse_tests(output_xml_path):
    """Return a list of dicts for every test found in output.xml.

    Each dict has:
        name        (str)
        start       (datetime)
        end         (datetime)
        is_exclusive (bool)
    """
    tree = ET.parse(output_xml_path)
    root = tree.getroot()
    tests = []

    def _walk(element):
        for child in element:
            if child.tag == "test":
                status = child.find("status")
                if status is None:
                    continue
                start_str = status.get("start")
                elapsed_str = status.get("elapsed")
                if start_str is None or elapsed_str is None:
                    continue
                start = datetime.fromisoformat(start_str)
                end = start + timedelta(seconds=float(elapsed_str))
                tags = [t.text.lower() for t in child.findall("tag") if t.text]
                tests.append(
                    {
                        "name": child.get("name"),
                        "start": start,
                        "end": end,
                        "is_exclusive": PABOT_TAG.lower() in tags,
                    }
                )
            else:
                _walk(child)

    _walk(root)
    return tests


def _overlap(a, b):
    """True when two time windows (open intervals) overlap."""
    return a["start"] < b["end"] and b["start"] < a["end"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl not supported on Windows")
def test_all_atest_tests_pass(tmp_path):
    """pabot must exit 0 and all tests in atest/ must report PASS."""
    result = _run_pabot(tmp_path)
    assert result.returncode == 0, (
        "pabot exited with code %d\n\nSTDOUT:\n%s\n\nSTDERR:\n%s"
        % (result.returncode, result.stdout, result.stderr)
    )

    tests = _parse_tests(str(tmp_path / "output.xml"))
    assert len(tests) == EXPECTED_TOTAL_TESTS, "Expected %d tests, found %d" % (
        EXPECTED_TOTAL_TESTS,
        len(tests),
    )
    failed = [t["name"] for t in tests if t.get("status") == "FAIL"]
    assert not failed, "Some tests failed: %s" % failed


def test_exclusive_tests_detected_in_output(tmp_path):
    """pabot log must mention exclusive tests when it finds them."""
    result = _run_pabot(tmp_path)
    combined = result.stdout + result.stderr
    assert "exclusive" in combined.lower(), (
        "Expected pabot to report exclusive tests in its output.\n"
        "STDOUT:\n%s\nSTDERR:\n%s" % (result.stdout, result.stderr)
    )


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl not supported on Windows")
def test_exclusive_tests_run_alone(tmp_path):
    """Each exclusive test must not overlap in wall-clock time with any other test.

    This is the core correctness check: with 4 workers and all exclusive tests
    scheduled AFTER all parallel stages, their 0.3 s windows must be isolated.
    """
    result = _run_pabot(tmp_path)
    assert result.returncode == 0, (
        "pabot exited with code %d\n\nSTDOUT:\n%s\n\nSTDERR:\n%s"
        % (result.returncode, result.stdout, result.stderr)
    )

    tests = _parse_tests(str(tmp_path / "output.xml"))
    exclusive = [t for t in tests if t["is_exclusive"]]

    assert len(exclusive) >= EXPECTED_EXCLUSIVE_TESTS, (
        "Expected at least %d exclusive tests, found %d.\n"
        "Check that suite_04-suite_05 exist and carry [Tags]    pabot:exclusive."
        % (EXPECTED_EXCLUSIVE_TESTS, len(exclusive))
    )

    violations = []
    for exc in exclusive:
        for other in tests:
            if other is exc:
                continue
            if _overlap(exc, other):
                violations.append(
                    "  '%s'  [%s → %s]\n"
                    "    overlapped with '%s'  [%s → %s]"
                    % (
                        exc["name"],
                        exc["start"].isoformat(timespec="milliseconds"),
                        exc["end"].isoformat(timespec="milliseconds"),
                        other["name"],
                        other["start"].isoformat(timespec="milliseconds"),
                        other["end"].isoformat(timespec="milliseconds"),
                    )
                )

    assert not violations, (
        "pabot:exclusive tests ran in parallel with other tests!\n\n"
        + "\n".join(violations)
    )
