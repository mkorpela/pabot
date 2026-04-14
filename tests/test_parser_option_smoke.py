import unittest

from pabot.arguments import _parse_pabot_args
from pabot import pabot


class ParserOptionSmokeTests(unittest.TestCase):
    def test_parse_args_collects_parser(self):
        remaining, pabot_args = _parse_pabot_args([
            "--parser",
            "my.parsers.CustomParser",
            "tests",
        ])
        self.assertEqual(remaining, ["tests"])
        self.assertEqual(pabot_args["parser"], ["my.parsers.CustomParser"])

    def test_parser_is_removed_from_rebot_options(self):
        options = {
            "parser": ["my.parsers.CustomParser"],
            "metadata": [],
            "variable": [],
            "variablefile": [],
            "listener": [],
            "prerunmodifier": [],
            "monitorcolors": "on",
            "language": None,
        }

        rebot_options = pabot._options_for_rebot(options, "start", "end")
        self.assertNotIn("parser", rebot_options)


if __name__ == "__main__":
    unittest.main()