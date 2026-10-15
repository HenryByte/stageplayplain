"""The FSE conformance corpus.

Each `tests/fse/*.fountain` fixture lists the reports it expects in
single-line boneyard comments, `/* expect: 7: error: E21 */`. Reports are
compared on line, severity and code only. A fixture with no `expect`
lines must produce no reports.
"""

import re
from pathlib import Path

import pytest

from screenplain import fse
from screenplain.fse import Report
from screenplain.parsers import fountain

FIXTURES = sorted((Path(__file__).parent / "fse").glob("*.fountain"))

expect_re = re.compile(r"/\*\s*expect:\s*(\d+):\s*(error|warning):\s*(\w+)\s*\*/")


def run(path: Path) -> list[Report]:
    """Parses and processes a fixture; returns every report."""
    with path.open(encoding="utf-8") as stream:
        screenplay = fountain.parse(stream)  # ty: ignore[invalid-argument-type]
    try:
        return fse.process(screenplay).reports
    except fse.FseError as error:
        return [*error.warnings, error.report]


@pytest.mark.parametrize("path", FIXTURES, ids=[path.stem for path in FIXTURES])
def test_fixture(path: Path) -> None:
    expected = sorted(
        (int(line), severity, code)
        for line, severity, code in expect_re.findall(path.read_text(encoding="utf-8"))
    )
    actual = sorted(
        (report.line, str(report.severity), report.code) for report in run(path)
    )
    assert expected == actual, "\n".join(
        report.format(path.name) for report in run(path)
    )
