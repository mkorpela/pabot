import os
import sys
import tempfile
import textwrap
import time

import pabot.pabot


def _write_minimal_suite(tmpdir: str) -> str:
    suite_path = os.path.join(tmpdir, "smoke.robot")
    with open(suite_path, "w", encoding="utf-8") as f:
        f.write(
            textwrap.dedent(
                """
                *** Settings ***
                Suite Setup    No Operation

                *** Test Cases ***
                Test 1
                    No Operation
                Test 2
                    No Operation
                """
            ).strip()
            + "\n"
        )
    return suite_path


def test_main_program_repeated_runs_does_not_slow_down():
    with tempfile.TemporaryDirectory() as tmpdir:
        suite_path = _write_minimal_suite(tmpdir)

        durations: list[float] = []
        for i in range(4):
            outdir = os.path.join(tmpdir, f"out_{i}")
            args = ["--pabotlib", "--pabotlibport", "0", "--outputdir", outdir, suite_path]

            t0 = time.perf_counter()
            exit_code = int(pabot.pabot.main_program(args))
            durations.append(time.perf_counter() - t0)

            assert exit_code == 0

        # Regression guard: previously iter 3+ could jump to ~25s.
        assert max(durations) < 10.0
        assert durations[2] < max(durations[0], durations[1]) * 5 + 1.0
