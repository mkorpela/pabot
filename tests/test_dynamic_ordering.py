import os
import shutil
import tempfile
import subprocess
import textwrap
import unittest
import xml.etree.ElementTree as ET
import re
from datetime import datetime

EXEC_RE = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+).*EXECUTING (?P<name>.+)"
)
PASS_RE = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+).*PASSED (?P<name>.+?) in"
)
FAIL_RE = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+).*FAILED (?P<name>.+)"
)

def get_tmpdir_name(name):
    # mimic pabot test helpers
    return name.replace("-", "_")


class TestDynamicOrdering(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.tmpdir_name = get_tmpdir_name(os.path.basename(cls.tmpdir))

        cls.suites_dir = os.path.join(cls.tmpdir, "suites")
        cls.order_dir = os.path.join(cls.tmpdir, "ordering")
        os.makedirs(cls.suites_dir)
        os.makedirs(cls.order_dir)

        # ---------------- ROBOT SUITES ----------------

        cls.complex_suite = os.path.join(cls.suites_dir, "complex.robot")
        with open(cls.complex_suite, "w") as f:
            f.write(textwrap.dedent("""
                *** Test Cases ***
                Test A
                    Sleep    2.0    # This sleep ensures other tests can start while A is running

                Test B
                    Sleep    0.1

                Test C
                    Sleep    0.1

                Test D
                    Sleep    0.1
            """))

        cls.chain_suite = os.path.join(cls.suites_dir, "chain.robot")
        with open(cls.chain_suite, "w") as f:
            f.write(textwrap.dedent("""
                *** Test Cases ***
                A
                    Sleep    0.1

                B
                    Sleep    0.1

                C
                    Sleep    0.1
            """))

        cls.fail_suite = os.path.join(cls.suites_dir, "fail.robot")
        with open(cls.fail_suite, "w") as f:
            f.write(textwrap.dedent("""
                *** Test Cases ***
                Fail Test
                    Fail    boom
            """))

        # ---------------- ORDERING FILES ----------------

        cls.order_simple = os.path.join(cls.order_dir, "order_simple.txt")
        with open(cls.order_simple, "w") as f:
            f.write(textwrap.dedent("""
                --test Simple.Test A
                --test Simple.Test B
                --test Simple.Test C
            """))

        cls.order_chain = os.path.join(cls.order_dir, "order_chain.txt")
        with open(cls.order_chain, "w") as f:
            f.write(textwrap.dedent("""
                --test Chain.A
                --test Chain.B #DEPENDS Chain.A
                --test Chain.C #DEPENDS Chain.B
            """))

        cls.order_chain_with_fail = os.path.join(cls.order_dir, "order_chain_with_fail.txt")
        with open(cls.order_chain_with_fail, "w") as f:
            f.write(textwrap.dedent("""
                --test Combined.Chain.A
                --test Combined.Fail.Fail Test #DEPENDS Combined.Chain.A
                --test Combined.Chain.B #DEPENDS Combined.Fail.Fail Test
                --test Combined.Chain.C #DEPENDS Combined.Chain.B
            """))

        cls.order_complex = os.path.join(cls.order_dir, "order_complex.txt")
        with open(cls.order_complex, "w") as f:
            f.write(textwrap.dedent("""
                --test Complex.Test A
                --test Complex.Test B
                --test Complex.Test C #DEPENDS Complex.Test B
                --test Complex.Test D #DEPENDS Complex.Test C
            """))

        cls.order_complex_diamond = os.path.join(cls.order_dir, "order_complex_diamond.txt")
        with open(cls.order_complex_diamond, "w") as f:
            f.write(textwrap.dedent("""
                --test Complex.Test B
                --test Complex.Test A #DEPENDS Complex.Test B
                --test Complex.Test C #DEPENDS Complex.Test B
                --test Complex.Test D #DEPENDS Complex.Test C #DEPENDS Complex.Test A
            """))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    # ---------------- HELPERS ----------------

    def _run_pabot(self, args):
        cmd = ["pabot"] + args
        return subprocess.run(
            cmd,
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _read_results(self):
        output_xml = os.path.join(self.tmpdir, "output.xml")
        tree = ET.parse(output_xml)
        root = tree.getroot()

        results = {}
        for test in root.iter("test"):
            name = test.attrib["name"]

            # Test case final status is the last <status> element
            status_elem = test.find("status")
            if status_elem is None:
                raise AssertionError(f"No <status> found for test {name}")

            results[name] = status_elem.attrib["status"]

        return results

    def parse_execution_times(self, stdout: str):
        times = {}

        for line in stdout.splitlines():
            if m := EXEC_RE.search(line):
                name = m.group("name")
                ts = datetime.fromisoformat(m.group("ts"))
                times.setdefault(name, {})["start"] = ts

            elif m := PASS_RE.search(line):
                name = m.group("name")
                ts = datetime.fromisoformat(m.group("ts"))
                times.setdefault(name, {})["end"] = ts

            elif m := FAIL_RE.search(line):
                name = m.group("name")
                ts = datetime.fromisoformat(m.group("ts"))
                times.setdefault(name, {})["end"] = ts

        return times

    def assert_executed_before(self, times, first, second):
        assert first in times, f"{first} not executed"
        assert second in times, f"{second} not executed"

        assert times[first]["end"] < times[second]["start"], (
            f"{first} did not complete before {second} started"
        )

    # ---------------- TESTS ----------------

    def test_dynamic_parallel_execution(self):
        """
        Static ordering must remain unchanged
        """
        process = self._run_pabot([
            "--processes", "3", "--testlevelsplit",
            "--ordering", self.order_chain, "dynamic",
            self.chain_suite,
        ])
        assert process.returncode == 0, f"Pabot failed: {process.stdout}\n{process.stderr}"

        times = self.parse_execution_times(process.stdout)
        self.assert_executed_before(times, "Chain.A", "Chain.B")
        self.assert_executed_before(times, "Chain.B", "Chain.C")

        results = self._read_results()
        self.assertEqual(list(results.keys()), ["A", "B", "C"])


    def test_dynamic_run_all_chain(self):
        """
        failure_policy=run_all executes full dependency chain
        """
        process = self._run_pabot([
            "--processes", "2", "--testlevelsplit",
            "--ordering", self.order_chain, "dynamic", "run_all",
            self.chain_suite,
        ])
        assert process.returncode == 0, f"Pabot failed: {process.stdout}\n{process.stderr}"

        times = self.parse_execution_times(process.stdout)
        self.assert_executed_before(times, "Chain.A", "Chain.B")
        self.assert_executed_before(times, "Chain.B", "Chain.C")

        results = self._read_results()
        self.assertEqual(results["A"], "PASS")
        self.assertEqual(results["B"], "PASS")
        self.assertEqual(results["C"], "PASS")


    def test_dynamic_skip_transitive_dependencies(self):
        """
        failure_policy=skip skips the entire dependency chain
        """
        process = self._run_pabot([
            "--processes", "2", "--testlevelsplit", "--name", "Combined",
            "--ordering", self.order_chain_with_fail, "dynamic", "skip",
            self.fail_suite,
            self.chain_suite,
        ])
        assert process.returncode == 1, f"Pabot failed: {process.stdout}\n{process.stderr}"

        times = self.parse_execution_times(process.stdout)
        self.assert_executed_before(times, "Combined.Chain.A", "Combined.Fail.Fail Test")
        self.assert_executed_before(times, "Combined.Fail.Fail Test", "Combined.Chain.B")
        self.assert_executed_before(times, "Combined.Chain.B", "Combined.Chain.C")

        results = self._read_results()
        self.assertEqual(results["A"], "PASS")
        self.assertEqual(results["Fail Test"], "FAIL")
        self.assertEqual(results["B"], "SKIP")
        self.assertEqual(results["C"], "SKIP")


    def test_dynamic_run_all_transitive_dependencies(self):
        """
        failure_policy=run_all executes the entire dependency chain, even after a failure
        """
        process = self._run_pabot([
            "--processes", "2", "--testlevelsplit", "--name", "Combined",
            "--ordering", self.order_chain_with_fail, "dynamic", "run_all",
            self.fail_suite,
            self.chain_suite,
        ])
        assert process.returncode == 1, f"Pabot failed: {process.stdout}\n{process.stderr}"

        times = self.parse_execution_times(process.stdout)
        self.assert_executed_before(times, "Combined.Chain.A", "Combined.Fail.Fail Test")
        self.assert_executed_before(times, "Combined.Fail.Fail Test", "Combined.Chain.B")
        self.assert_executed_before(times, "Combined.Chain.B", "Combined.Chain.C")

        results = self._read_results()
        self.assertEqual(results["A"], "PASS")
        self.assertEqual(results["Fail Test"], "FAIL")
        self.assertEqual(results["B"], "PASS")
        self.assertEqual(results["C"], "PASS")


    def test_static_ordering_still_works(self):
        """
        Static ordering must remain unchanged
        """
        process = self._run_pabot([
            "--processes", "3", "--testlevelsplit",
            "--ordering", self.order_chain, "static",
            self.chain_suite,
        ])
        assert process.returncode == 0, f"Pabot failed: {process.stdout}\n{process.stderr}"

        times = self.parse_execution_times(process.stdout)
        self.assert_executed_before(times, "Chain.A", "Chain.B")
        self.assert_executed_before(times, "Chain.B", "Chain.C")

        results = self._read_results()
        self.assertEqual(list(results.keys()), ["A", "B", "C"])


    def test_dynamic_start_with_dependencies_when_possible(self):
        """
        If dependencies are ready, they should be started even if other independent tests are still running
        """
        process = self._run_pabot([
            "--processes", "2", "--testlevelsplit",
            "--ordering", self.order_complex, "dynamic", "run_all",
            self.complex_suite,
        ])
        assert process.returncode == 0, f"Pabot failed: {process.stdout}\n{process.stderr}"

        times = self.parse_execution_times(process.stdout)
        self.assert_executed_before(times, "Complex.Test B", "Complex.Test C")
        self.assert_executed_before(times, "Complex.Test C", "Complex.Test D")
        assert times["Complex.Test A"]["start"] < times["Complex.Test C"]["start"], (
            "Complex.Test A should start before Complex.Test C"
        )
        assert times["Complex.Test A"]["end"] > times["Complex.Test D"]["start"], (
            "Complex.Test D should start before Complex.Test A ends"
        ) 

        results = self._read_results()
        self.assertEqual(results["Test A"], "PASS")
        self.assertEqual(results["Test B"], "PASS")
        self.assertEqual(results["Test C"], "PASS")
        self.assertEqual(results["Test D"], "PASS")


    def test_dynamic_diamond_dependencies(self):
        """
        Tests that dependencies are correctly handled in a diamond-shaped dependency graph
        """
        process = self._run_pabot([
            "--processes", "2", "--testlevelsplit",
            "--ordering", self.order_complex_diamond, "dynamic", "run_all",
            self.complex_suite,
        ])
        assert process.returncode == 0, f"Pabot failed: {process.stdout}\n{process.stderr}"

        times = self.parse_execution_times(process.stdout)
        self.assert_executed_before(times, "Complex.Test B", "Complex.Test A")
        self.assert_executed_before(times, "Complex.Test B", "Complex.Test C")
        self.assert_executed_before(times, "Complex.Test A", "Complex.Test D")
        self.assert_executed_before(times, "Complex.Test C", "Complex.Test D")

        results = self._read_results()
        self.assertEqual(results["Test A"], "PASS")
        self.assertEqual(results["Test B"], "PASS")
        self.assertEqual(results["Test C"], "PASS")
        self.assertEqual(results["Test D"], "PASS")
