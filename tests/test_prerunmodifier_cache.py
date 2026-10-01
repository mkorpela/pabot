import pytest
from robot.api import SuiteVisitor

from pabot import arguments, pabot


class SelectTest(SuiteVisitor):
    def __init__(self):
        self.selected = "Alpha"

    def start_suite(self, suite):
        suite.name = self.selected
        suite.tests = [test for test in suite.tests if test.name == self.selected]


def setup_suite(tmp_path, monkeypatch, testlevelsplit):
    # Suite discovery logs asynchronously. These tests only inspect its result.
    monkeypatch.setattr(pabot, "_write", lambda *args, **kwargs: None)
    source = tmp_path / "suite.robot"
    source.write_text(
        "*** Test Cases ***\nAlpha\n    No Operation\nBeta\n    No Operation\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    cli = ["--testlevelsplit"] if testlevelsplit else []
    options, sources, pabot_args, _ = arguments.parse_args(cli + [str(source)])
    return options, sources, pabot_args


@pytest.mark.parametrize("testlevelsplit", [False, True])
def test_standard_prerunmodifier_refreshes_cached_selection(
    tmp_path, monkeypatch, testlevelsplit
):
    options, sources, pabot_args = setup_suite(tmp_path, monkeypatch, testlevelsplit)
    modifier = SelectTest()
    options["prerunmodifier"] = [modifier]
    output = str(tmp_path / "results")
    first = pabot.solve_suite_names(output, sources, options, pabot_args)
    assert [item.name for item in first] == [
        "Alpha.Alpha" if testlevelsplit else "Alpha"
    ]
    assert (tmp_path / ".pabotsuitenames").is_file()
    original_hash = pabot.get_hash_of_command(options, pabot_args)

    modifier.selected = "Beta"
    assert pabot.get_hash_of_command(options, pabot_args) == original_hash
    second = pabot.solve_suite_names(output, sources, options, pabot_args)
    assert [item.name for item in second] == ["Beta.Beta" if testlevelsplit else "Beta"]


def test_no_modifier_keeps_cache(tmp_path, monkeypatch):
    options, sources, pabot_args = setup_suite(tmp_path, monkeypatch, True)
    output = str(tmp_path / "results")
    first = pabot.solve_suite_names(output, sources, options, pabot_args)

    def unexpected_rebuild(*args, **kwargs):
        pytest.fail("An unchanged suite without modifiers should use its cache")

    monkeypatch.setattr(pabot, "generate_suite_names_with_builder", unexpected_rebuild)
    second = pabot.solve_suite_names(output, sources, options, pabot_args)
    assert [item.name for item in second] == [item.name for item in first]
