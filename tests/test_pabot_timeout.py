import subprocess
import xml.etree.ElementTree as ET


def test_pabot_and_robot_timeouts(tmp_path):
    # -------------------------------
    # Create Robot test suite
    # -------------------------------
    suite = tmp_path / "timeouts.robot"
    suite.write_text(
        """
*** Test Cases ***
Normal Test Without Sleep
    Log    Hello world

RF Timeout Short Sleep
    [Timeout]    1s
    Sleep        2s

RF Timeout Long Sleep
    [Timeout]    1s
    Sleep        6s

Pabot Process Timeout
    Sleep    6s
""",
        encoding="utf-8",
    )

    output = tmp_path / "output.xml"

    # -------------------------------
    # Run pabot
    # -------------------------------
    cmd = [
        "pabot",
        "--processtimeout",
        "3",
        "--testlevelsplit",
        "--outputdir",
        str(tmp_path),
        str(suite),
    ]

    result = subprocess.run(
        cmd,
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # pabot should return non-zero due to failures (total 3 tests failing)
    assert result.returncode == 3
    assert output.exists(), f"output.xml not created\nSTDERR:\n{result.stderr}"

    # -------------------------------
    # Parse output.xml
    # -------------------------------
    tree = ET.parse(output)
    root = tree.getroot()

    results = {}
    for test in root.iter("test"):
        status = test.find("status")
        results[test.attrib["name"]] = {
            "status": status.attrib["status"],
            "message": (status.text or "").strip(),
        }

    # -------------------------------
    # Assertions
    # -------------------------------
    assert results["Normal Test Without Sleep"]["status"] == "PASS"

    assert results["RF Timeout Short Sleep"]["status"] == "FAIL"
    assert "timeout" in results["RF Timeout Short Sleep"]["message"].lower()

    assert results["RF Timeout Long Sleep"]["status"] == "FAIL"
    assert "timeout" in results["RF Timeout Long Sleep"]["message"].lower()

    assert results["Pabot Process Timeout"]["status"] == "FAIL"
    assert "pabot's --processtimeout option has been reached" in results[
        "Pabot Process Timeout"
    ]["message"].lower()
