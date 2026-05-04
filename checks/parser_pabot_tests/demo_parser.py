from pathlib import Path

from robot.running import TestSuite


class DemoParser:
    EXTENSION = ".demo"

    @staticmethod
    def parse(source: Path, defaults=None) -> TestSuite:
        suite = TestSuite(name=f"Demo::{source.stem}", source=source)
        for line in source.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                test_name, _payload = line.split(":", 1)
                test_name = test_name.strip()
            else:
                test_name = line
            test = suite.tests.create(name=test_name)
            test.body.create_keyword(name="No Operation")
        return suite
