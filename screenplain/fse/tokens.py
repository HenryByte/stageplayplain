"""The tokeniser: splits an FSE note into keyword-led directives.

Its output is internal; validation turns it into typed directives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

KEYWORDS = frozenset(
    (
        "STAGE",
        "ENTITY",
        "ENTER",
        "EXIT",
        "MOVE",
        "VIA",
        "ARRIVE",
        "SET",
        "STRIKE",
        "PRESET",
    )
)

_marker_re = re.compile(r"\s*FSE\s")
_unclosed_marker_re = re.compile(r"\s*FSE(?:\s|\Z)")


def is_fse_note(text: str) -> bool:
    """Whether a note's content begins with the `FSE` marker.

    >>> is_fse_note('\\n  FSE MOVE hamlet pos=1,2')
    True
    >>> is_fse_note('fse MOVE hamlet pos=1,2')
    False
    >>> is_fse_note('FSE')
    False
    """
    return _marker_re.match(text) is not None


def is_unclosed_fse_note(text: str) -> bool:
    """Whether the text after an unclosed `[[` begins with the marker."""
    return _unclosed_marker_re.match(text) is not None


@dataclass(frozen=True)
class RawDirective:
    """One directive as tokenised: keyword, optional subject, attributes in
    source order (duplicates kept), and its source text.

    `line_offset` counts the line breaks in the note before the directive.
    """

    keyword: str
    subject: str | None
    attributes: tuple[tuple[str, str], ...]
    text: str
    line_offset: int


class NearMiss(Exception):
    """The note carries the marker but cannot be tokenised."""


class LeadingSeparator(Exception):
    """A `;` straight after the marker (E19)."""


def _is_bare_char(char: str) -> bool:
    return not char.isspace() and char not in ';"[]'


class _Tokeniser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.n = len(text)

    def skip_space(self, i: int) -> int:
        while i < self.n and self.text[i].isspace():
            i += 1
        return i

    def check_token_end(self, i: int) -> None:
        if i < self.n and not self.text[i].isspace() and self.text[i] != ";":
            raise NearMiss(f"unexpected {self.text[i]!r}")

    def read_quoted(self, i: int) -> tuple[str, int]:
        """Reads a quoted value starting at the quote at `i`."""
        chars: list[str] = []
        i += 1
        while i < self.n:
            char = self.text[i]
            if char == "\\" and i + 1 < self.n and self.text[i + 1] in '"\\':
                chars.append(self.text[i + 1])
                i += 2
            elif char == '"':
                return "".join(chars), i + 1
            elif char in "\r\n":
                raise NearMiss("line break inside a quoted value")
            elif char in "[]":
                raise NearMiss(f"{char!r} in a value")
            else:
                chars.append(char)
                i += 1
        raise NearMiss("unterminated quote")

    def read_token(self, i: int) -> tuple[str | None, str, int]:
        """Reads a token at `i`. Returns its key (None for a subject),
        value and end.
        """
        if self.text[i] == '"':
            value, i = self.read_quoted(i)
            self.check_token_end(i)
            return None, value, i
        j = i
        while j < self.n and _is_bare_char(self.text[j]):
            j += 1
        if j < self.n and self.text[j] in "[]":
            raise NearMiss(f"{self.text[j]!r} in a value")
        run = self.text[i:j]
        quoted = j < self.n and self.text[j] == '"'
        if "=" not in run:
            if quoted:
                raise NearMiss("unexpected '\"'")
            self.check_token_end(j)
            return None, run, j
        key, value = run.split("=", 1)
        if not key:
            raise NearMiss(f"empty key in {run!r}")
        if quoted:
            if value:
                raise NearMiss("unexpected '\"'")
            value, j = self.read_quoted(j)
        elif not value:
            raise NearMiss(f"empty value for {key!r}")
        self.check_token_end(j)
        return key, value, j

    def tokenise(self) -> list[RawDirective]:
        match = _marker_re.match(self.text)
        if not match:
            raise NearMiss("no FSE marker")
        i = self.skip_space(match.end())
        if i < self.n and self.text[i] == ";":
            raise LeadingSeparator
        directives: list[RawDirective] = []
        while i < self.n:
            start = i
            while i < self.n and not self.text[i].isspace() and self.text[i] != ";":
                i += 1
            keyword = self.text[start:i]
            if keyword not in KEYWORDS:
                raise NearMiss(f"unknown keyword {keyword!r}")
            subject: str | None = None
            attributes: list[tuple[str, str]] = []
            first = True
            while True:
                i = self.skip_space(i)
                if i >= self.n or self.text[i] == ";":
                    break
                key, value, i = self.read_token(i)
                if key is None:
                    if not first:
                        raise NearMiss(f"{value!r} has no '='")
                    subject = value
                else:
                    attributes.append((key, value))
                first = False
            directives.append(
                RawDirective(
                    keyword,
                    subject,
                    tuple(attributes),
                    self.text[start:i].strip(),
                    self.text.count("\n", 0, start),
                )
            )
            if i >= self.n:
                break
            i = self.skip_space(i + 1)
            if i < self.n and self.text[i] == ";":
                raise NearMiss("empty directive between separators")
        if not directives:
            raise NearMiss("no directive")
        return directives


def tokenise(text: str) -> list[RawDirective]:
    """Splits the content of an FSE note into directives.

    Raises `NearMiss` if it cannot, and `LeadingSeparator` for a `;`
    straight after the marker.

    >>> [d.keyword for d in tokenise('FSE MOVE hamlet pos=1,2; ARRIVE x;')]
    ['MOVE', 'ARRIVE']
    """
    return _Tokeniser(text).tokenise()
