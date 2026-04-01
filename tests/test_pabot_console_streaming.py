import unittest
import subprocess
import re
from datetime import datetime

class TestPabotRealtimeLogging(unittest.TestCase):
    def test_pabot_log_delay(self):
        pabot_cmd = [
            "pabot",
            "--testlevelsplit",
            "tests/ci"
        ]

        process = subprocess.Popen(
            pabot_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )

        timestamp_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)")

        max_allowed_delay = 0.5  # seconds
        delays = []

        for line in process.stdout:
            line = line.rstrip()
            match = timestamp_pattern.search(line)
            now = datetime.now()

            if match:
                log_time_str = match.group(1)
                log_time = datetime.strptime(log_time_str, "%Y-%m-%d %H:%M:%S.%f")
                delta = (now - log_time).total_seconds()
                delays.append(delta)
                print(f"{now.isoformat()} | {line} | delay: {delta:.6f}s")
            else:
                print(f"{now.isoformat()} | {line} | delay: N/A")

        process.wait()

        # Assert that all log delays are within the allowed threshold
        for delta in delays:
            self.assertLessEqual(delta, max_allowed_delay, 
                f"Log delay too high: {delta:.6f}s")

if __name__ == "__main__":
    unittest.main()
