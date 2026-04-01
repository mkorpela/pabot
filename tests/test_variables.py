import os
import shutil
import tempfile
import subprocess
import textwrap
import unittest
import xml.etree.ElementTree as ET


def get_tmpdir_name(name):
    # mimic pabot test helpers
    return name.replace("-", "_")


class TestVariables(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.tmpdir_name = get_tmpdir_name(os.path.basename(cls.tmpdir))

        cls.suites_dir = os.path.join(cls.tmpdir, "suites")
        cls.variables_dir = os.path.join(cls.tmpdir, "variables")
        os.makedirs(cls.suites_dir)

        # ---------------- ROBOT SUITES ----------------

        cls.variables_suite = os.path.join(cls.suites_dir, "check_variables.robot")
        with open(cls.variables_suite, "w") as f:
            f.write(textwrap.dedent("""
                *** Test Cases ***
                Test A
                    Log Variables

                Test B
                    Log Variables

                Test C
                    Log Variables

                Test D
                    Log Variables

                *** Keywords ***
                Log Variables
                    Log    PABOTLIBURI=${PABOTLIBURI}
                    Log    PABOTQUEUEINDEX=${PABOTQUEUEINDEX}
                    Log    PABOTEXECUTIONPOOLID=${PABOTEXECUTIONPOOLID}
                    Log    PABOTEXECUTIONBATCHSIZE=${PABOTEXECUTIONBATCHSIZE}
                    Log    PABOTNUMBEROFPROCESSES=${PABOTNUMBEROFPROCESSES}
                    Log    CALLER_ID=${CALLER_ID}
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

    def _read_logged_variables(self):
        output_xml = os.path.join(self.tmpdir, "output.xml")
        tree = ET.parse(output_xml)
        root = tree.getroot()

        variables = {}
        for test in root.iter("test"):
            name = test.attrib["name"]
            variables[name] = {}
            for log in test.iter("msg"):
                variable_name, variable_value = log.text.split("=", 1)
                variables[name][variable_name] = variable_value

        return variables

    def assert_all_variables_present(self, variables):
        for test_vars in variables.values():
            self.assertIn("PABOTLIBURI", test_vars)
            self.assertIn("PABOTQUEUEINDEX", test_vars)
            self.assertIn("PABOTEXECUTIONPOOLID", test_vars)
            self.assertIn("PABOTEXECUTIONBATCHSIZE", test_vars)
            self.assertIn("PABOTNUMBEROFPROCESSES", test_vars)
            self.assertIn("CALLER_ID", test_vars)

    # ---------------- TESTS ----------------

    def test_check_variables_more_tests_than_processes(self):
        """
        Checks that the expected pabot variables are set correctly in all test
        cases when there are more test cases than processes.
        """
        process = self._run_pabot([
            "--processes", "2", "--testlevelsplit",
            self.variables_suite,
        ])
        assert process.returncode == 0, f"Pabot failed: {process.stdout}\n{process.stderr}"

        results = self._read_results()
        self.assertEqual(results["Test A"], "PASS")
        self.assertEqual(results["Test B"], "PASS")
        self.assertEqual(results["Test C"], "PASS")
        self.assertEqual(results["Test D"], "PASS")

        variables = self._read_logged_variables()
        self.assert_all_variables_present(variables)
        # Check the values of all variables are correct.
        pabotlib_uris = [test_vars["PABOTLIBURI"] for test_vars in variables.values()]
        self.assertEqual(len(set(pabotlib_uris)), 1) # All should be the same
        queue_indices = [test_vars["PABOTQUEUEINDEX"] for test_vars in variables.values()]
        self.assertListEqual(sorted(queue_indices), ["0", "1", "2", "3"])
        pool_ids = [test_vars["PABOTEXECUTIONPOOLID"] for test_vars in variables.values()]
        self.assertListEqual(sorted(pool_ids), ["0", "0", "1", "1"])
        batch_sizes = [test_vars["PABOTEXECUTIONBATCHSIZE"] for test_vars in variables.values()]
        self.assertListEqual(sorted(batch_sizes), ["4", "4", "4", "4"])
        process_counts = [test_vars["PABOTNUMBEROFPROCESSES"] for test_vars in variables.values()]
        self.assertListEqual(sorted(process_counts), ["2", "2", "2", "2"])
        caller_ids = [test_vars["CALLER_ID"] for test_vars in variables.values()]
        self.assertEqual(len(set(caller_ids)), 4) # All should be different

    def test_check_variables_more_processes_than_tests(self):
        """
        Checks that the expected pabot variables are set correctly in all test
        cases when there are more processes than test cases.
        """
        process = self._run_pabot([
            "--processes", "8", "--testlevelsplit",
            self.variables_suite,
        ])
        assert process.returncode == 0, f"Pabot failed: {process.stdout}\n{process.stderr}"

        results = self._read_results()
        self.assertEqual(results["Test A"], "PASS")
        self.assertEqual(results["Test B"], "PASS")
        self.assertEqual(results["Test C"], "PASS")
        self.assertEqual(results["Test D"], "PASS")

        variables = self._read_logged_variables()
        self.assert_all_variables_present(variables)
        # Check the values of all variables are correct.
        pabotlib_uris = [test_vars["PABOTLIBURI"] for test_vars in variables.values()]
        self.assertEqual(len(set(pabotlib_uris)), 1) # All should be the same
        queue_indices = [test_vars["PABOTQUEUEINDEX"] for test_vars in variables.values()]
        self.assertListEqual(sorted(queue_indices), ["0", "1", "2", "3"])
        pool_ids = [test_vars["PABOTEXECUTIONPOOLID"] for test_vars in variables.values()]
        self.assertListEqual(sorted(pool_ids), ["0", "1", "2", "3"])
        batch_sizes = [test_vars["PABOTEXECUTIONBATCHSIZE"] for test_vars in variables.values()]
        self.assertListEqual(sorted(batch_sizes), ["4", "4", "4", "4"])
        process_counts = [test_vars["PABOTNUMBEROFPROCESSES"] for test_vars in variables.values()]
        self.assertListEqual(sorted(process_counts), ["8", "8", "8", "8"])
        caller_ids = [test_vars["CALLER_ID"] for test_vars in variables.values()]
        self.assertEqual(len(set(caller_ids)), 4) # All should be different
