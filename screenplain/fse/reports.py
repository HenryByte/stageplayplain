"""Reports: the errors and warnings a processor gives about the blocking."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import override

NAMES = {
    "E01": "no-stage",
    "E02": "unknown-id",
    "E03": "duplicate-id",
    "E04": "wrong-type",
    "E05": "not-onstage",
    "E06": "already-onstage",
    "E07": "fixed-entity",
    "E08": "missing-attribute",
    "E09": "conflicting-location",
    "E10": "same-entity",
    "E11": "cycle",
    "E12": "misplaced",
    "E13": "already-in-transit",
    "E14": "not-in-transit",
    "E15": "unclosed-move",
    "E16": "unknown-attribute",
    "E17": "bad-value",
    "E18": "duplicate-attribute",
    "E19": "leading-separator",
    "E20": "attached",
    "E21": "unclosed-note",
    "W01": "near-miss",
    "W02": "speaker-offstage",
    "W03": "out-of-bounds",
    "W04": "reach",
    "W06": "unused",
    "W07": "unmatched-cue",
    "W09": "glued-note",
}


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Report:
    """An error or warning: its code, the source line, and the text of the
    directive (or other script text) that caused it.

    `message` explains the fault; it is for people and may change freely.
    """

    code: str
    line: int
    text: str
    message: str = ""

    @property
    def severity(self) -> Severity:
        return Severity.ERROR if self.code.startswith("E") else Severity.WARNING

    @property
    def name(self) -> str:
        return NAMES[self.code]

    def format(self, path: str) -> str:
        """Formats the report as a compiler-style line.

        >>> Report('E05', 42, 'MOVE hamlet  pos=1,2', 'hamlet is offstage').format('h.fountain')
        'h.fountain:42: error: E05 not-onstage: MOVE hamlet pos=1,2 — hamlet is offstage'
        """
        text = " ".join(self.text.split())
        result = f"{path}:{self.line}: {self.severity}: {self.code} {self.name}: {text}"
        if self.message:
            result += f" — {self.message}"
        return result


@dataclass
class FseError(Exception):
    """The first error in a script's blocking, with the warnings before it."""

    report: Report
    warnings: list[Report] = field(default_factory=list)

    @override
    def __str__(self) -> str:
        return self.report.format("<script>")
