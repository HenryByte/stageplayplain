"""Performance benchmarks for notes in the parser and FSE processing.

Run with:

    make perf

`test_parse_big_fish` in test_fountain_perf.py parses the note-free
example; compare it with a run saved before notes were kept in the
Screenplay (`make perf ARGS='--benchmark-compare'`). A note-free script
never reaches `fse.process` (see tests/fse_cli_test.py), so FSE adds
nothing to it.

There is no numeric bound and no CI gate until the parser's O(n) rework
settles the baseline. FSE processing is expected to grow roughly
linearly, with state snapshots costing O(notes x entities).
"""

from io import StringIO
from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from screenplain import fse
from screenplain.parsers import fountain

EXAMPLE = Path(__file__).parent.parent.parent / "examples" / "Big-Fish.fountain"

# An FSE note goes in after every NOTE_EVERY paragraphs.
NOTE_EVERY = 5
LARGE_MULTIPLIER = 10
PROPS = 20

DECLARATIONS = "\n".join(
    [
        "[[FSE STAGE type=proscenium width=10 depth=8]]",
        "[[FSE ENTITY actor type=cast pos=0,0]]",
        *(
            f"[[FSE ENTITY prop-{i} type=prop pos={i % 5},{i % 4}]]"
            for i in range(PROPS)
        ),
    ]
)

NOTES = (
    "[[FSE MOVE actor pos=1,1 facing=90]]",
    "[[FSE MOVE actor pos=-1,-1]]",
    "[[an ordinary note]]",
)


def split(source: str) -> tuple[str, list[str]]:
    """Splits the example into its title page and body paragraphs."""
    title_page, body = source.split("\n\n", 1)
    return title_page, body.split("\n\n")


def annotate(source: str, multiplier: int = 1) -> str:
    """The example with a declaration block, and a note every NOTE_EVERY
    paragraphs, repeated `multiplier` times.
    """
    title_page, paragraphs = split(source)
    paragraphs = paragraphs * multiplier
    annotated = [DECLARATIONS]
    for index, paragraph in enumerate(paragraphs):
        annotated.append(paragraph)
        if index % NOTE_EVERY == NOTE_EVERY - 1:
            annotated.append(NOTES[index // NOTE_EVERY % len(NOTES)])
    return title_page + "\n\n" + "\n\n".join(annotated)


def with_ordinary_notes(source: str) -> str:
    """The example with an ordinary inline note on every paragraph."""
    title_page, paragraphs = split(source)
    noted = [paragraph + " [[a note]]" for paragraph in paragraphs]
    return title_page + "\n\n" + "\n\n".join(noted)


@pytest.fixture(scope="module")
def source() -> str:
    return EXAMPLE.read_text(encoding="utf-8")


def parse_and_process(source: str) -> fse.Blocking:
    return fse.process(fountain.parse(StringIO(source)))


@pytest.mark.perf
def test_parse_big_fish_with_ordinary_notes(
    benchmark: BenchmarkFixture, source: str
) -> None:
    """Notes cost the parser something only where they appear."""
    noted = with_ordinary_notes(source)
    screenplay = benchmark(lambda: fountain.parse(StringIO(noted)))
    assert not fse.has_fse_notes(screenplay)


@pytest.mark.perf
def test_fse_big_fish(benchmark: BenchmarkFixture, source: str) -> None:
    """Parse and process an FSE-annotated Big Fish."""
    annotated = annotate(source)
    blocking = benchmark(lambda: parse_and_process(annotated))
    assert len(blocking.timeline.steps) > 100


@pytest.mark.perf
def test_fse_big_fish_large(benchmark: BenchmarkFixture, source: str) -> None:
    """The same at 10x the size, to compare against the 1x run."""
    annotated = annotate(source, LARGE_MULTIPLIER)
    blocking = benchmark(lambda: parse_and_process(annotated))
    assert len(blocking.timeline.steps) > 1000
