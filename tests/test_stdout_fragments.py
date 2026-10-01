"""Robot Framework stdout is a stream, not one message per write call."""

from robot import run

from pabot import writer as writer_module
from pabot.writer import MessageWriter, get_stdout_writer


def test_robot_result_paths_stay_on_one_line(tmp_path, capsys, monkeypatch):
    suite = tmp_path / "case.robot"
    suite.write_text("*** Test Cases ***\nPassing\n    No Operation\n")
    writer = MessageWriter(log_file=str(tmp_path / "pabot.log"))
    monkeypatch.setattr(writer_module, "_writer_instance", writer)
    try:
        assert run(str(suite), outputdir=str(tmp_path), stdout=get_stdout_writer()) == 0
    finally:
        writer.stop()
    output = capsys.readouterr().out
    for label, name in [
        ("Output:", "output.xml"),
        ("Log:", "log.html"),
        ("Report:", "report.html"),
    ]:
        assert any(
            line.startswith(label) and str(tmp_path / name) in line
            for line in output.splitlines()
        ), output


def test_stdout_fragments_and_flush(tmp_path, capsys, monkeypatch):
    writer = MessageWriter(log_file=str(tmp_path / "pabot.log"))
    monkeypatch.setattr(writer_module, "_writer_instance", writer)
    stream = get_stdout_writer()
    try:
        stream.write("Log: ")
        stream.flush()
        stream.write("report.html")
        stream.flush()
        stream.write("\nSecond line\nPartial")
        stream.finish()
    finally:
        writer.stop()
    assert capsys.readouterr().out == "Log: report.html\nSecond line\nPartial\n"
    assert (tmp_path / "pabot.log").read_text().splitlines() == [
        "[INFO]    Log: report.html",
        "[INFO]    Second line",
        "[INFO]    Partial",
    ]


def test_stdout_keeps_empty_lines(tmp_path, capsys, monkeypatch):
    writer = MessageWriter(log_file=str(tmp_path / "pabot.log"))
    monkeypatch.setattr(writer_module, "_writer_instance", writer)
    stream = get_stdout_writer()
    try:
        stream.write("first\n\nlast\n")
        stream.finish()
    finally:
        writer.stop()
    assert capsys.readouterr().out == "first\n\nlast\n"


def test_message_writer_adapter_stays_unbuffered():
    from unittest.mock import Mock
    from pabot.writer import ThreadSafeWriter

    writer = Mock()
    stream = ThreadSafeWriter(writer)
    stream.write("message", level="warning")
    writer.write.assert_called_once_with("message", level="warning")
