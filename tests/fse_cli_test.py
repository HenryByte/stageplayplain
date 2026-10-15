"""The command line's handling of FSE reports: wording, order, exit codes,
untouched output, `--no-warnings` and when processing runs at all.
"""

import io
import sys
from pathlib import Path

import pytest

from screenplain import fse
from screenplain.main import main

STAGE = "[[FSE STAGE type=proscenium width=10 depth=8]]\n"

CLEAN = STAGE + "[[FSE ENTITY hamlet type=cast pos=0,0]]\n\nHAMLET\nTo be.\n"

# Line 6 is a W04 warning, line 7 an E05 error.
WARNING_AND_ERROR = (
    STAGE
    + "[[FSE ENTITY hamlet type=cast pos=0,0]]\n"
    + "[[FSE ENTITY skull type=prop pos=3,0]]\n"
    + "[[FSE ENTITY horatio type=cast]]\n"
    + "\n"
    + "[[FSE STRIKE skull by=hamlet]]\n"
    + "[[FSE MOVE horatio pos=1,2]]\n"
)

ONLY_WARNING = WARNING_AND_ERROR.replace(
    "[[FSE ENTITY horatio type=cast]]", "[[FSE ENTITY horatio type=cast pos=1,2]]"
).replace("[[FSE MOVE horatio pos=1,2]]\n", "")

NEAR_MISS = "Hamlet waits.\n\n[[FSE move hamlet]]\n\nHe waits.\n"

UNCLOSED = "Hamlet waits.\n\n[[FSE MOVE hamlet pos=1,2\n\nHe waits.\n"

WARNING_LINE = (
    "{path}:6: warning: W04 reach: STRIKE skull by=hamlet — hamlet is 3.0 m from skull"
)
ERROR_LINE = (
    "{path}:7: error: E05 not-onstage: MOVE horatio pos=1,2 — horatio is offstage"
)
NO_OUTPUT = "screenplain: no output written (1 error)"


def write(tmp_path: Path, source: str) -> str:
    path = tmp_path / "play.fountain"
    path.write_text(source, encoding="utf-8")
    return str(path)


def run(argv: list[str]) -> int:
    """Runs main and returns its exit code."""
    try:
        main(argv)
    except SystemExit as stop:
        return int(stop.code or 0)
    return 0


def run_stdin(monkeypatch: pytest.MonkeyPatch, source: str, argv: list[str]) -> int:
    stdin = io.TextIOWrapper(io.BytesIO(source.encode("utf-8")), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin)
    return run(argv)


def test_error_wording(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write(tmp_path, WARNING_AND_ERROR)
    assert 1 == run(["--no-warnings", path, str(tmp_path / "out.html")])
    assert [
        ERROR_LINE.format(path=path),
        NO_OUTPUT,
    ] == capsys.readouterr().err.splitlines()


def test_warning_wording(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write(tmp_path, ONLY_WARNING)
    assert 0 == run([path, str(tmp_path / "out.html")])
    assert [WARNING_LINE.format(path=path)] == capsys.readouterr().err.splitlines()


def test_stdin_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert 1 == run_stdin(monkeypatch, WARNING_AND_ERROR, ["-f", "html"])
    captured = capsys.readouterr()
    assert [
        WARNING_LINE.format(path="<stdin>"),
        ERROR_LINE.format(path="<stdin>"),
        NO_OUTPUT,
    ] == captured.err.splitlines()
    assert "" == captured.out


def test_warnings_print_before_the_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write(tmp_path, WARNING_AND_ERROR)
    assert 1 == run([path, str(tmp_path / "out.pdf")])
    assert [
        WARNING_LINE.format(path=path),
        ERROR_LINE.format(path=path),
        NO_OUTPUT,
    ] == capsys.readouterr().err.splitlines()


def test_clean_script_exits_0_silently(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out.html"
    assert 0 == run([write(tmp_path, CLEAN), str(out)])
    assert "" == capsys.readouterr().err
    assert "To be." in out.read_text(encoding="utf-8")


def test_warnings_exit_0_and_write_output(tmp_path: Path) -> None:
    out = tmp_path / "out.html"
    assert 0 == run([write(tmp_path, ONLY_WARNING), str(out)])
    assert out.exists()


def test_usage_error_wins_over_fse_error(tmp_path: Path) -> None:
    path = write(tmp_path, WARNING_AND_ERROR)
    assert 2 == run([path, str(tmp_path / "out.docx")])
    assert 2 == run(["--stageplay", "-f", "fdx", path, str(tmp_path / "out.fdx")])


def test_error_leaves_an_existing_output_untouched(tmp_path: Path) -> None:
    out = tmp_path / "out.html"
    out.write_bytes(b"previous output")
    assert 1 == run([write(tmp_path, WARNING_AND_ERROR), str(out)])
    assert b"previous output" == out.read_bytes()


def test_error_creates_no_output(tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    assert 1 == run([write(tmp_path, WARNING_AND_ERROR), str(out)])
    assert not out.exists()


def test_error_writes_nothing_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert 1 == run(["-f", "html", write(tmp_path, WARNING_AND_ERROR)])
    assert "" == capsys.readouterr().out


def test_no_warnings_silences_warnings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert 0 == run(["--no-warnings", write(tmp_path, ONLY_WARNING), "-f", "html"])
    assert "" == capsys.readouterr().err


def test_lone_near_miss_warns_and_writes_todays_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write(tmp_path, NEAR_MISS)
    out = tmp_path / "out.html"
    assert 0 == run([path, str(out)])
    err = capsys.readouterr().err.splitlines()
    assert 1 == len(err)
    assert err[0].startswith(f"{path}:3: warning: W01 near-miss: FSE move hamlet")

    plain = tmp_path / "plain.fountain"
    plain.write_text(NEAR_MISS.replace("FSE ", "x "), encoding="utf-8")
    expected = tmp_path / "expected.html"
    assert 0 == run([str(plain), str(expected)])
    assert expected.read_text(encoding="utf-8") == out.read_text(encoding="utf-8")


def test_lone_unclosed_note_blocks_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write(tmp_path, UNCLOSED)
    out = tmp_path / "out.html"
    assert 1 == run([path, str(out)])
    assert not out.exists()
    err = capsys.readouterr().err.splitlines()
    assert err[0].startswith(f"{path}:3: error: E21 unclosed-note: ")
    assert NO_OUTPUT == err[1]


def test_process_is_not_called_without_fse_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object) -> None:
        raise AssertionError("fse.process was called")

    monkeypatch.setattr(fse, "process", fail)
    source = (
        "INT. HALL\n\n[[an ordinary note]]\n\nHAMLET\nTo be. [[fse not a marker]]\n"
    )
    assert 0 == run([write(tmp_path, source), str(tmp_path / "out.html")])
