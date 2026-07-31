# Copyright (c) 2011 Martin Vilcans
# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php

"""Performance benchmarks for the Fountain parser.

Run with:

    make perf

These are excluded from the normal test run (see the ``perf`` marker).
"""

from io import StringIO
from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from screenplain.parsers import fountain

EXAMPLE = Path(__file__).parent.parent.parent / "examples" / "Big-Fish.fountain"

# Number of copies of the example used for the "large document" benchmark.
LARGE_MULTIPLIER = 10


@pytest.fixture(scope="module")
def source() -> str:
    return EXAMPLE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def lines(source: str) -> list[str]:
    """The example split into lines, as parse() would hand them to parse_lines."""
    return fountain.linebreak_re.split(fountain.boneyard_re.sub("", source))


@pytest.fixture(scope="module")
def large_lines(lines: list[str]) -> list[str]:
    """A body-only document repeated to get a workload larger than one screenplay.

    The title page is dropped from the copies so that the result is still a
    single valid document instead of title page keys appearing mid-body.
    """
    body = lines[lines.index("") :]
    return lines + body * (LARGE_MULTIPLIER - 1)


@pytest.mark.perf
def test_parse_big_fish(benchmark: BenchmarkFixture, source: str) -> None:
    """Benchmark the whole entry point: read, strip boneyard, split, parse."""
    screenplay = benchmark(lambda: fountain.parse(StringIO(source)))
    assert len(screenplay.paragraphs) > 0


@pytest.mark.perf
def test_parse_lines_big_fish(benchmark: BenchmarkFixture, lines: list[str]) -> None:
    """Benchmark parse_lines alone, without the read/boneyard/split overhead."""
    screenplay = benchmark(lambda: fountain.parse_lines(list(lines)))
    assert len(screenplay.paragraphs) > 0


@pytest.mark.perf
def test_parse_lines_large_document(
    benchmark: BenchmarkFixture, large_lines: list[str]
) -> None:
    """Benchmark parse_lines on a document ~10x the size of one screenplay."""
    screenplay = benchmark(lambda: fountain.parse_lines(list(large_lines)))
    assert len(screenplay.paragraphs) > 0
