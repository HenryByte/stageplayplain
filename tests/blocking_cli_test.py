"""`--blocking` at the command line, and the screenplay column shift it
brings.
"""

import io
from pathlib import Path

import pytest
from reportlab.lib.units import inch
from reportlab.platypus import Flowable

from screenplain import fse
from screenplain.export import pdf
from screenplain.export.margin_plans import FlushMargin
from screenplain.main import main
from screenplain.parsers import fountain

STAGE = "[[FSE STAGE type=proscenium width=10 depth=8]]\n"

SCRIPT = (
    STAGE
    + "[[FSE ENTITY hamlet type=cast]]\n"
    + "\n"
    + "INT. HALL\n"
    + "\n"
    + "[[FSE PRESET hamlet pos=0,0]]\n"
    + "\n"
    + "HAMLET\n"
    + "To be.\n"
)

STAGE_PLAY = "Title: Hamlet\nFormat: Stage Play\n\n===\n\n" + SCRIPT

# A near-miss is an FSE note too.
FRONT_MATTER_NOTE = (
    "Title: Hamlet\nFormat: Stage Play\n\n"
    "A castle. [[FSE enter hamlet]]\n\n===\n\n" + SCRIPT
)

FRONT_MATTER_DECLARATIONS = (
    "Title: Hamlet\nFormat: Stage Play\n\n"
    + STAGE
    + "[[FSE ENTITY hamlet type=cast]]\n\n===\n\n"
    + "INT. HALL\n\n[[FSE PRESET hamlet pos=0,0]]\n\nHAMLET\nTo be.\n"
)

NO_FSE = "INT. HALL\n\nHAMLET\nTo be.\n"

NEAR_MISS = "INT. HALL\n\n[[FSE move hamlet]]\n\nHAMLET\nTo be.\n"


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


@pytest.mark.parametrize("out_format", ["html", "fdx"])
def test_blocking_needs_pdf_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], out_format: str
) -> None:
    # The input does not exist: the arguments are refused before it is read.
    missing = str(tmp_path / "missing.fountain")
    out = tmp_path / f"out.{out_format}"
    assert 2 == run(["--blocking", missing, str(out)])
    err = capsys.readouterr().err
    assert err.startswith("usage: ")
    assert f"--blocking is only supported for pdf, not {out_format}" in err
    assert not out.exists()


def test_blocking_needs_an_fse_script(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write(tmp_path, NO_FSE)
    out = tmp_path / "out.pdf"
    assert 1 == run(["--blocking", path, str(out)])
    assert [
        f"screenplain: --blocking needs an FSE script, but {path} has no (valid) "
        "FSE notes"
    ] == capsys.readouterr().err.splitlines()
    assert not out.exists()


def test_near_misses_warn_before_the_blocking_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write(tmp_path, NEAR_MISS)
    out = tmp_path / "out.pdf"
    assert 1 == run(["--blocking", path, str(out)])
    err = capsys.readouterr().err.splitlines()
    assert 2 == len(err)
    assert err[0].startswith(f"{path}:3: warning: W01 near-miss: ")
    assert err[1].startswith("screenplain: --blocking needs an FSE script")
    assert not out.exists()


def test_no_warnings_hides_near_misses_but_not_the_blocking_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write(tmp_path, NEAR_MISS)
    assert 1 == run(["--blocking", "--no-warnings", path, str(tmp_path / "out.pdf")])
    err = capsys.readouterr().err.splitlines()
    assert 1 == len(err)
    assert err[0].startswith("screenplain: --blocking needs an FSE script")


def test_near_misses_alone_still_write_output_without_blocking(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out.pdf"
    assert 0 == run(["--no-warnings", write(tmp_path, NEAR_MISS), str(out)])
    assert out.exists()


@pytest.mark.parametrize(
    ("source", "line"),
    [(FRONT_MATTER_NOTE, 4), (FRONT_MATTER_DECLARATIONS, 4)],
    ids=["near-miss", "declarations"],
)
def test_no_fse_in_stage_play_front_matter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], source: str, line: int
) -> None:
    path = write(tmp_path, source)
    out = tmp_path / "out.pdf"
    assert 1 == run(["--blocking", "--no-warnings", path, str(out)])
    assert [
        f"screenplain: --blocking needs FSE notes after the front matter, but "
        f"{path}:{line} has one before the first page break"
    ] == capsys.readouterr().err.splitlines()
    assert not out.exists()


def test_stage_play_front_matter_may_have_headings(tmp_path: Path) -> None:
    source = (
        "Title: Hamlet\nFormat: Stage Play\n\n"
        "# Dramatis Personae\n\nHAMLET\n\n# Setting\n\nA castle.\n\n===\n\n" + SCRIPT
    )
    out = tmp_path / "out.pdf"
    assert 0 == run(["--blocking", write(tmp_path, source), str(out)])
    assert out.exists()


def test_front_matter_rule_is_for_stage_plays_only(tmp_path: Path) -> None:
    # As a screenplay, the same declarations before a page break are fine.
    source = FRONT_MATTER_DECLARATIONS.replace("Format: Stage Play\n", "")
    out = tmp_path / "out.pdf"
    assert 0 == run(["--blocking", "--no-warnings", write(tmp_path, source), str(out)])
    assert out.exists()


def test_front_matter_notes_are_fine_without_blocking(tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    path = write(tmp_path, FRONT_MATTER_DECLARATIONS)
    assert 0 == run(["--no-warnings", path, str(out)])
    assert out.exists()


def test_fse_errors_still_win(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = SCRIPT.replace("PRESET hamlet pos=0,0", "MOVE hamlet pos=1,1")
    out = tmp_path / "out.pdf"
    assert 1 == run(["--blocking", write(tmp_path, source), str(out)])
    err = capsys.readouterr().err.splitlines()
    assert "error: E" in err[0]
    assert "screenplain: no output written (1 error)" == err[1]
    assert not out.exists()


@pytest.mark.parametrize("source", [SCRIPT, STAGE_PLAY], ids=["screenplay", "play"])
def test_blocking_writes_a_pdf(tmp_path: Path, source: str) -> None:
    out = tmp_path / "out.pdf"
    assert 0 == run(["--blocking", write(tmp_path, source), str(out)])
    assert out.read_bytes().startswith(b"%PDF")


@pytest.mark.parametrize("source", [SCRIPT, STAGE_PLAY], ids=["screenplay", "play"])
def test_the_blocking_reaches_the_exporter_only_with_the_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    from screenplain.export import stageplay_pdf

    seen: list[object] = []
    module = stageplay_pdf if source is STAGE_PLAY else pdf

    def to_pdf(*args: object, blocking: object = None, **kwargs: object) -> None:
        seen.append(blocking)

    monkeypatch.setattr(module, "to_pdf", to_pdf)
    path = write(tmp_path, source)
    run([path, str(tmp_path / "plain.pdf")])
    run(["--blocking", path, str(tmp_path / "blocking.pdf")])
    assert seen[0] is None
    assert isinstance(seen[1], fse.Blocking)


# The screenplay column shift


# Long enough for several pages, with no scene boundary, so no scene plans.
LONG = (
    "Title: Shift\n\n"
    + STAGE
    + "[[FSE ENTITY hamlet type=cast pos=0,0]]\n\n"
    + "".join(
        f"HAMLET\nSpeech {n}, which runs long enough to wrap onto a second "
        "line of dialogue in the column.\n\n"
        f"Hamlet paces, {n} times, back and forth across the hall.\n\n"
        for n in range(60)
    )
)


def layout(
    blocking: fse.Blocking | None, monkeypatch: pytest.MonkeyPatch
) -> list[tuple[int, float, float, float]]:
    """Where each flowable lands: page, frame left, y after it, height."""
    placed: list[tuple[int, float, float, float]] = []

    def after(doc: pdf.DocTemplate, flowable: Flowable) -> None:
        if isinstance(flowable, FlushMargin):
            return
        frame = doc.frame
        assert frame is not None
        placed.append((doc.page, frame._x1, frame._y, getattr(flowable, "height", 0)))

    monkeypatch.setattr(pdf.DocTemplate, "afterFlowable", after, raising=False)
    screenplay = fountain.parse(io.StringIO(LONG))
    pdf.to_pdf(screenplay, io.BytesIO(), blocking=blocking)  # ty: ignore[invalid-argument-type]
    return placed


def test_blocking_shifts_the_screenplay_column_without_repaginating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    screenplay = fountain.parse(io.StringIO(LONG))
    blocking = fse.process(screenplay)
    assert [] == blocking.scenes

    plain = layout(None, monkeypatch)
    shifted = layout(blocking, monkeypatch)

    assert len(plain) == len(shifted)
    assert plain[-1][0] == shifted[-1][0] > 2
    for (page, x, y, height), (page2, x2, y2, height2) in zip(
        plain, shifted, strict=True
    ):
        assert (page, y, height) == (page2, y2, height2)
        assert x - x2 == pytest.approx(0.5 * inch)


def test_blocking_margins() -> None:
    settings = pdf.Settings(font_settings=pdf.get_standard_font_settings())
    shifted = pdf.with_blocking_margins(settings)
    assert 1.0 * inch == pytest.approx(shifted.left_margin)
    assert 1.4 * inch == pytest.approx(shifted.right_margin)
    assert settings.frame_width == shifted.frame_width
    assert 1.5 * inch == settings.left_margin
