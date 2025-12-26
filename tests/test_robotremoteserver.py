import sys
import unittest
from unittest.mock import patch

from pabot.robotremoteserver import StandardStreamInterceptor, KeywordRunner


class TestStandardStreamInterceptor(unittest.TestCase):

    def test_safe_getvalue_normal_case(self):
        """Test normal case where streams are not restored"""
        interceptor = StandardStreamInterceptor()
        with interceptor:
            sys.stdout.write("test output")

        self.assertEqual(interceptor.output, "test output")

    def test_safe_getvalue_stream_restored(self):
        """Test case where stream is restored during execution"""
        interceptor = StandardStreamInterceptor()

        # Simulate stream being restored
        sys.stdout = sys.__stdout__

        # This should trigger the warning
        stdout_result = interceptor._safe_getvalue(sys.stdout, interceptor.stdout_capture)

        self.assertEqual(stdout_result, "")

    def test_safe_getvalue_with_captured_data(self):
        """Test case where stream is restored but capture has data"""
        interceptor = StandardStreamInterceptor()

        # Write to capture before restoration
        interceptor.stdout_capture.write("captured data")

        # Simulate stream restoration
        sys.stdout = sys.__stdout__

        result = interceptor._safe_getvalue(sys.stdout, interceptor.stdout_capture)

        self.assertEqual(result, "captured data")


class TestKeywordRunnerWarning(unittest.TestCase):

    def test_warning_message_in_output(self):
        """Test that warning message appears in keyword runner output when stream is interrupted"""

        def test_keyword():
            # Simulate stream restoration during keyword execution
            sys.stdout = sys.__stdout__
            return "keyword result"

        runner = KeywordRunner(test_keyword)

        result = runner.run_keyword([], {})

        # Check that warning appears in output
        self.assertIn("*WARN* Stream capture was interrupted", result.get('output', ''))


if __name__ == '__main__':
    unittest.main()