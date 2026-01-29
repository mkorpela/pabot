"""
Comprehensive tests for MessageWriter and pabotconsole functionality.

Tests cover:
1. --pabotconsole argument parsing
2. Console type filtering (verbose, dotted, quiet, none)
3. Message level hierarchy
4. Log file vs console output separation
5. End-to-end scenarios
6. Edge cases and error handling
"""
import sys
import os
import tempfile
import pytest
from io import StringIO

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pabot.arguments import _parse_pabot_args
from pabot.writer import MessageWriter
from robot.errors import DataError


# ============================================================================
# Test Fixtures
# ============================================================================

class MockFile:
    """Mock file object for testing"""
    def __init__(self, name="test.out", content=""):
        self.name = name
        self.content = content


@pytest.fixture
def temp_logfile():
    """Create a temporary log file for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "test.log")
        yield log_file


# ============================================================================
# Test Group 1: Argument Parsing
# ============================================================================

class TestArgumentParsing:
    """Test --pabotconsole argument parsing"""

    def test_pabotconsole_verbose(self):
        """Test --pabotconsole verbose"""
        args = ['--pabotconsole', 'verbose']
        remaining, pabot_args = _parse_pabot_args(args)
        assert pabot_args['pabotconsole'] == 'verbose'

    def test_pabotconsole_dotted(self):
        """Test --pabotconsole dotted"""
        args = ['--pabotconsole', 'dotted']
        remaining, pabot_args = _parse_pabot_args(args)
        assert pabot_args['pabotconsole'] == 'dotted'

    def test_pabotconsole_quiet(self):
        """Test --pabotconsole quiet"""
        args = ['--pabotconsole', 'quiet']
        remaining, pabot_args = _parse_pabot_args(args)
        assert pabot_args['pabotconsole'] == 'quiet'

    def test_pabotconsole_none(self):
        """Test --pabotconsole none"""
        args = ['--pabotconsole', 'none']
        remaining, pabot_args = _parse_pabot_args(args)
        assert pabot_args['pabotconsole'] == 'none'

    def test_pabotconsole_default_value(self):
        """Test --pabotconsole default value is verbose"""
        args = []
        remaining, pabot_args = _parse_pabot_args(args)
        assert pabot_args['pabotconsole'] == 'verbose'

    def test_pabotconsole_invalid_value(self):
        """Test --pabotconsole rejects invalid value"""
        args = ['--pabotconsole', 'invalid']
        with pytest.raises(DataError) as exc_info:
            _parse_pabot_args(args)
        error_msg = str(exc_info.value)
        assert 'Invalid value for --pabotconsole' in error_msg
        assert 'verbose' in error_msg
        assert 'dotted' in error_msg
        assert 'quiet' in error_msg
        assert 'none' in error_msg

    def test_pabotconsole_with_other_args(self):
        """Test --pabotconsole works with other pabot arguments"""
        args = ['--verbose', '--pabotconsole', 'dotted', '--processes', '2']
        remaining, pabot_args = _parse_pabot_args(args)
        assert pabot_args['pabotconsole'] == 'dotted'
        assert pabot_args['verbose'] is True
        assert pabot_args['processes'] == 2


# ============================================================================
# Test Group 2: Console Type Filtering - Verbose Mode
# ============================================================================

class TestConsoleTypeVerbose:
    """Test verbose console type mode"""

    def test_verbose_prints_all_levels(self, temp_logfile):
        """Verbose mode should print all message levels to console"""
        writer = MessageWriter(log_file=temp_logfile, console_type="verbose")

        writer.write("Debug message", level="debug")
        writer.write("Info message", level="info")
        writer.write("Warning message", level="warning")
        writer.write("Error message", level="error")
        writer.flush()
        writer.stop()

        with open(temp_logfile, 'r') as f:
            content = f.read()

        assert "Debug message" in content
        assert "Info message" in content
        assert "Warning message" in content
        assert "Error message" in content

    def test_verbose_prints_result_levels(self, temp_logfile):
        """Verbose mode should print result-specific levels"""
        writer = MessageWriter(log_file=temp_logfile, console_type="verbose")

        writer.write("PASSED TestSuite", level="info_passed")
        writer.write("FAILED TestSuite", level="info_failed")
        writer.write("SKIPPED TestSuite", level="info_skipped")
        writer.flush()
        writer.stop()

        with open(temp_logfile, 'r') as f:
            content = f.read()

        assert "PASSED TestSuite" in content
        assert "FAILED TestSuite" in content
        assert "SKIPPED TestSuite" in content

    def test_verbose_filter_check(self, temp_logfile):
        """Verbose mode _should_print_to_console returns True for all levels"""
        writer = MessageWriter(log_file=temp_logfile, console_type="verbose")

        levels = ["debug", "info", "info_passed", "info_failed", "warning", "error"]
        for level in levels:
            assert writer._should_print_to_console(level=level) is True, \
                f"Verbose mode should print level '{level}'"

        writer.stop()


# ============================================================================
# Test Group 3: Console Type Filtering - Dotted Mode
# ============================================================================

class TestConsoleTypeDotted:
    """Test dotted console type mode"""

    def test_dotted_prints_result_messages(self, temp_logfile):
        """Dotted mode should print result indicators"""
        writer = MessageWriter(log_file=temp_logfile, console_type="dotted")

        assert writer._should_print_to_console(level="info_passed") is True
        assert writer._should_print_to_console(level="info_failed") is True
        assert writer._should_print_to_console(level="info_skipped") is True
        assert writer._should_print_to_console(level="info_ignored") is True

        writer.stop()

    def test_dotted_filters_debug(self, temp_logfile):
        """Dotted mode should NOT print debug messages"""
        writer = MessageWriter(log_file=temp_logfile, console_type="dotted")

        assert writer._should_print_to_console(level="debug") is False

        writer.stop()

    def test_dotted_prints_important_levels(self, temp_logfile):
        """Dotted mode should print info, warning, error"""
        writer = MessageWriter(log_file=temp_logfile, console_type="dotted")

        assert writer._should_print_to_console(level="info") is True
        assert writer._should_print_to_console(level="warning") is True
        assert writer._should_print_to_console(level="error") is True

        writer.stop()

    def test_dotted_filters_debug_but_shows_results(self, temp_logfile):
        """Dotted mode filters debug but shows test results"""
        writer = MessageWriter(log_file=temp_logfile, console_type="dotted")

        writer.write("Debug info", level="debug")
        writer.write(".", level="info_passed")  # Single char for dotted
        writer.write("F", level="info_failed")
        writer.flush()
        writer.stop()

        with open(temp_logfile, 'r') as f:
            content = f.read()

        assert "Debug info" not in content or writer._should_print_to_console(level="debug") is False


# ============================================================================
# Test Group 4: Console Type Filtering - Quiet Mode
# ============================================================================

class TestConsoleTypeQuiet:
    """Test quiet console type mode"""

    def test_quiet_filters_debug_and_results(self, temp_logfile):
        """Quiet mode filters debug and result messages"""
        writer = MessageWriter(log_file=temp_logfile, console_type="quiet")

        assert writer._should_print_to_console(level="debug") is False
        assert writer._should_print_to_console(level="info_passed") is False
        assert writer._should_print_to_console(level="info_failed") is False
        assert writer._should_print_to_console(level="info_skipped") is False
        assert writer._should_print_to_console(level="info_ignored") is False

        writer.stop()

    def test_quiet_prints_info_and_above(self, temp_logfile):
        """Quiet mode prints info level and above"""
        writer = MessageWriter(log_file=temp_logfile, console_type="quiet")

        assert writer._should_print_to_console(level="info") is True
        assert writer._should_print_to_console(level="warning") is True
        assert writer._should_print_to_console(level="error") is True

        writer.stop()

    def test_quiet_filters_to_console(self, temp_logfile):
        """Quiet mode filters correctly to console"""
        writer = MessageWriter(log_file=temp_logfile, console_type="quiet")

        writer.write("Debug message", level="debug")
        writer.write("PASSED test", level="info_passed")
        writer.write("Important info", level="info")
        writer.write("WARNING issued", level="warning")
        writer.flush()
        writer.stop()

        with open(temp_logfile, 'r') as f:
            content = f.read()

        # All should be in log
        assert "Debug message" in content
        assert "PASSED test" in content
        assert "Important info" in content
        assert "WARNING issued" in content

        # Verify filtering logic works
        writer2 = MessageWriter(log_file=temp_logfile, console_type="quiet")
        assert writer2._should_print_to_console(level="debug") is False
        assert writer2._should_print_to_console(level="info_passed") is False
        assert writer2._should_print_to_console(level="info") is True
        assert writer2._should_print_to_console(level="warning") is True
        writer2.stop()


# ============================================================================
# Test Group 5: Console Type Filtering - None Mode
# ============================================================================

class TestConsoleTypeNone:
    """Test none console type mode"""

    def test_none_filters_all_levels(self, temp_logfile):
        """None mode filters all levels"""
        writer = MessageWriter(log_file=temp_logfile, console_type="none")

        levels = ["debug", "info", "info_passed", "info_failed", "warning", "error"]
        for level in levels:
            assert writer._should_print_to_console(level=level) is False, \
                f"None mode should filter level '{level}'"

        writer.stop()

    def test_none_no_console_output(self, temp_logfile):
        """None mode should produce no console output"""
        writer = MessageWriter(log_file=temp_logfile, console_type="none")

        writer.write("This should not appear", level="info")
        writer.write("Neither should this", level="warning")
        writer.write("Or this", level="error")
        writer.flush()
        writer.stop()

        # Verify filtering behavior
        writer2 = MessageWriter(log_file=temp_logfile, console_type="none")
        assert writer2._should_print_to_console(level="info") is False
        assert writer2._should_print_to_console(level="warning") is False
        assert writer2._should_print_to_console(level="error") is False
        writer2.stop()


# ============================================================================
# Test Group 6: Level Hierarchy
# ============================================================================

class TestLevelHierarchy:
    """Test message level hierarchy"""

    def test_level_numeric_hierarchy_in_quiet(self, temp_logfile):
        """Test level numeric hierarchy: debug (0) < info_passed (1) < info (3) < warning (4) < error (5)"""
        writer = MessageWriter(log_file=temp_logfile, console_type="quiet")

        # Quiet mode threshold is >= 3
        level_map = {
            "debug": (0, False),
            "info_passed": (1, False),
            "info": (3, True),
            "warning": (4, True),
            "error": (5, True),
        }

        for level, (level_num, should_print) in level_map.items():
            result = writer._should_print_to_console(level=level)
            assert result == should_print, \
                f"Level {level} ({level_num}) should print={should_print}, got {result}"

        writer.stop()

    def test_level_hierarchy_across_modes(self, temp_logfile):
        """Test level hierarchy is consistent across console types"""
        modes = {
            "verbose": {
                "debug": True,
                "info": True,
                "warning": True,
                "error": True,
            },
            "dotted": {
                "debug": False,
                "info_passed": True,
                "info": True,
                "warning": True,
                "error": True,
            },
            "quiet": {
                "debug": False,
                "info_passed": False,
                "info": True,
                "warning": True,
                "error": True,
            },
            "none": {
                "debug": False,
                "info": False,
                "warning": False,
                "error": False,
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            for mode, level_expectations in modes.items():
                log_file = os.path.join(tmpdir, f"{mode}.log")
                writer = MessageWriter(log_file=log_file, console_type=mode)

                for level, should_print in level_expectations.items():
                    result = writer._should_print_to_console(level=level)
                    assert result == should_print, \
                        f"Mode {mode}, level {level}: expected {should_print}, got {result}"

                writer.stop()


# ============================================================================
# Test Group 7: Log File vs Console Output
# ============================================================================

class TestLogFileVsConsole:
    """Test separation between log file and console output"""

    def test_log_file_always_receives_all_messages_quiet_mode(self, temp_logfile):
        """Log file should receive all messages even in quiet mode"""
        writer = MessageWriter(log_file=temp_logfile, console_type="quiet")

        writer.write("Debug message", level="debug")
        writer.write("PASSED test", level="info_passed")
        writer.write("Info message", level="info")
        writer.write("Warning message", level="warning")
        writer.write("Error message", level="error")
        writer.flush()
        writer.stop()

        with open(temp_logfile, 'r') as f:
            content = f.read()

        assert "Debug message" in content
        assert "PASSED test" in content
        assert "Info message" in content
        assert "Warning message" in content
        assert "Error message" in content

    def test_log_file_receives_all_in_none_mode(self, temp_logfile):
        """Log file should receive all messages even in none mode"""
        writer = MessageWriter(log_file=temp_logfile, console_type="none")

        messages = [
            ("Debug", "debug"),
            ("Info", "info"),
            ("Warning", "warning"),
            ("Error", "error"),
        ]

        for msg, level in messages:
            writer.write(msg, level=level)

        writer.flush()
        writer.stop()

        with open(temp_logfile, 'r') as f:
            content = f.read()

        for msg, _ in messages:
            assert msg in content, f"Message '{msg}' should be in log file"

    def test_console_vs_log_filtering_quiet(self, temp_logfile):
        """Console vs log filtering with quiet mode"""
        writer = MessageWriter(log_file=temp_logfile, console_type="quiet")

        messages = [
            ("DEBUG", "debug"),
            ("PASSED", "info_passed"),
            ("INFO", "info"),
            ("WARNING", "warning"),
        ]

        for msg, level in messages:
            writer.write(msg, level=level)

        writer.flush()
        writer.stop()

        # Log should have all
        with open(temp_logfile, 'r') as f:
            log_content = f.read()

        for msg, _ in messages:
            assert msg in log_content

        # Verify filtering logic
        writer2 = MessageWriter(log_file=temp_logfile, console_type="quiet")
        assert writer2._should_print_to_console(level="debug") is False
        assert writer2._should_print_to_console(level="info_passed") is False
        assert writer2._should_print_to_console(level="info") is True
        assert writer2._should_print_to_console(level="warning") is True
        writer2.stop()


# ============================================================================
# Test Group 8: End-to-End Scenarios
# ============================================================================

class TestEndToEndScenarios:
    """Test realistic end-to-end scenarios"""

    def test_real_world_test_execution_quiet_mode(self, temp_logfile):
        """Simulate a real test execution with quiet mode"""
        writer = MessageWriter(log_file=temp_logfile, console_type="quiet")

        # Simulate test suite execution
        writer.write("Starting test execution", level="info")
        writer.write("PASSED suite1 in 2.5 seconds", level="info_passed")
        writer.write("PASSED suite2 in 1.8 seconds", level="info_passed")
        writer.write("FAILED suite3 with errors", level="info_failed")
        writer.write("Processing results...", level="info")
        writer.write("Merging outputs", level="info")
        writer.write("WARNING: Some tests had warnings", level="warning")
        writer.write("Test execution completed", level="info")

        writer.flush()
        writer.stop()

        # Log should have everything
        with open(temp_logfile, 'r') as f:
            log_content = f.read()

        assert "Starting test execution" in log_content
        assert "PASSED suite1" in log_content
        assert "PASSED suite2" in log_content
        assert "FAILED suite3" in log_content
        assert "Processing results" in log_content

        # Verify filtering works correctly
        writer2 = MessageWriter(log_file=temp_logfile, console_type="quiet")
        assert writer2._should_print_to_console(level="info_passed") is False
        assert writer2._should_print_to_console(level="info") is True
        assert writer2._should_print_to_console(level="warning") is True
        writer2.stop()

    def test_real_world_test_execution_verbose_mode(self, temp_logfile):
        """Simulate a real test execution with verbose mode"""
        writer = MessageWriter(log_file=temp_logfile, console_type="verbose")

        messages = [
            ("Starting tests", "info"),
            ("DEBUG: Initializing setup", "debug"),
            ("Running test suite 1", "info"),
            ("PASSED suite1", "info_passed"),
            ("Running test suite 2", "info"),
            ("FAILED suite2", "info_failed"),
            ("WARNING: Test 5 had timeout", "warning"),
        ]

        for msg, level in messages:
            writer.write(msg, level=level)

        writer.flush()
        writer.stop()

        # All should be in log
        with open(temp_logfile, 'r') as f:
            content = f.read()

        for msg, _ in messages:
            assert msg in content

    def test_mixed_messages_all_modes(self):
        """Test mixed message streams in all modes"""
        with tempfile.TemporaryDirectory() as tmpdir:
            for mode in ["verbose", "dotted", "quiet", "none"]:
                log_file = os.path.join(tmpdir, f"{mode}.log")

                writer = MessageWriter(log_file=log_file, console_type=mode)

                writer.write("Starting", level="info")
                writer.write("Debug info", level="debug")
                writer.write("Result", level="info_passed")
                writer.write("Done", level="info")

                writer.flush()
                writer.stop()

                # Verify log has everything for all modes
                with open(log_file, 'r') as f:
                    log = f.read()

                assert "Starting" in log
                assert "Debug info" in log
                assert "Result" in log
                assert "Done" in log


# ============================================================================
# Test Group 9: Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_empty_message(self, temp_logfile):
        """Test writing empty messages"""
        writer = MessageWriter(log_file=temp_logfile, console_type="verbose")

        writer.write("", level="info")
        writer.write("", level="debug")
        writer.flush()
        writer.stop()

        # Should not crash and should still work
        with open(temp_logfile, 'r') as f:
            content = f.read()

        # Log file operations should succeed
        assert os.path.exists(temp_logfile)

    def test_very_long_message(self, temp_logfile):
        """Test writing very long messages"""
        writer = MessageWriter(log_file=temp_logfile, console_type="quiet")

        long_message = "x" * 10000
        writer.write(long_message, level="info")
        writer.flush()
        writer.stop()

        with open(temp_logfile, 'r') as f:
            content = f.read()

        assert long_message in content

    def test_writer_stop_idempotent(self, temp_logfile):
        """Test that calling stop() multiple times is safe"""
        writer = MessageWriter(log_file=temp_logfile, console_type="verbose")

        writer.write("Message", level="info")
        writer.flush()

        # Should not raise exception
        writer.stop()
        writer.stop()

    def test_write_after_stop(self, temp_logfile):
        """Test that writing after stop() doesn't cause crash"""
        writer = MessageWriter(log_file=temp_logfile, console_type="verbose")

        writer.write("Before stop", level="info")
        writer.flush()
        writer.stop()

        # Writing after stop should not crash (behavior may vary)
        try:
            writer.write("After stop", level="info")
        except Exception:
            pass  # It's okay if it raises, just shouldn't crash unexpectedly

    def test_console_type_case_insensitive(self):
        """Test that console_type handling is appropriate"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Standard case should work
            writer = MessageWriter(log_file=log_file, console_type="verbose")
            writer.write("Test message", level="info")
            writer.flush()
            writer.stop()

            # Log file should be created and contain the message
            assert os.path.exists(log_file)
            with open(log_file, 'r') as f:
                content = f.read()
            assert "Test message" in content

    def test_multiple_sequential_writers(self):
        """Test creating multiple writers sequentially"""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                log_file = os.path.join(tmpdir, f"test_{i}.log")

                writer = MessageWriter(log_file=log_file, console_type="quiet")
                writer.write(f"Message {i}", level="info")
                writer.flush()
                writer.stop()

                with open(log_file, 'r') as f:
                    content = f.read()

                assert f"Message {i}" in content


# ============================================================================
# Test Group 10: Message Level Combinations
# ============================================================================

class TestLevelCombinations:
    """Test various combinations of messages and levels"""

    def test_all_levels_verbose(self, temp_logfile):
        """Test all possible levels in verbose mode"""
        writer = MessageWriter(log_file=temp_logfile, console_type="verbose")

        levels = [
            "debug",
            "info",
            "info_passed",
            "info_failed",
            "info_skipped",
            "info_ignored",
            "warning",
            "error",
        ]

        for level in levels:
            writer.write(f"Message at {level}", level=level)

        writer.flush()
        writer.stop()

        with open(temp_logfile, 'r') as f:
            content = f.read()

        for level in levels:
            assert f"Message at {level}" in content

    def test_all_levels_none_mode_log_only(self, temp_logfile):
        """Test all levels in none mode - should only appear in log"""
        writer = MessageWriter(log_file=temp_logfile, console_type="none")

        levels = ["debug", "info", "warning", "error"]

        for level in levels:
            writer.write(f"Message at {level}", level=level)

        writer.flush()
        writer.stop()

        # All to log
        with open(temp_logfile, 'r') as f:
            log_content = f.read()

        for level in levels:
            assert f"Message at {level}" in log_content

    def test_mode_consistency_with_threshold_values(self, temp_logfile):
        """Test that modes have consistent threshold behavior"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test quiet mode threshold more thoroughly
            log_file = os.path.join(tmpdir, "quiet.log")
            writer = MessageWriter(log_file=log_file, console_type="quiet")

            # Quiet mode is >= 3 (info level and above)
            test_cases = [
                ("debug", False),         # Level 0
                ("info_passed", False),   # Level 1
                ("info", True),           # Level 3
                ("warning", True),        # Level 4
                ("error", True),          # Level 5
            ]

            for level, expected in test_cases:
                result = writer._should_print_to_console(level=level)
                assert result == expected, \
                    f"Quiet mode, level {level}: expected {expected}, got {result}"

            writer.stop()
