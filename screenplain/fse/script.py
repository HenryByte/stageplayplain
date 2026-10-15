"""Where FSE notes sit in a Screenplay, and script positions (words)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import accumulate

from screenplain.fse.model import Cue
from screenplain.fse.tokens import is_fse_note, is_unclosed_fse_note
from screenplain.types import (
    SCREENPLAY_TYPES,
    Action,
    Dialog,
    DualDialog,
    InlineNote,
    Note,
    PageBreak,
    Screenplay,
    Section,
    Slug,
    Transition,
)

_word_re = re.compile(r"\S+")

# Where a misplaced note sits, for messages, by paragraph type.
_MISPLACED = {
    Slug: "a scene heading",
    Section: "a section heading",
    Transition: "a transition",
    PageBreak: "a page break",
}

TITLE_PAGE = -1


@dataclass(frozen=True)
class Site:
    """An FSE note and where it sits.

    `misplaced` names the element it may not appear in (E12), or is None.
    `glued` says it is alone on a line of a paragraph with other text
    (W09). `speaker` is the character cue's text when the note is in a
    speech or parenthetical, for an implied subject.
    """

    text: str
    line: int
    cue: Cue
    misplaced: str | None = None
    glued: bool = False
    speaker: str | None = None


def _element_sites(
    element: Action | Dialog | Slug | Section | Transition | PageBreak,
    paragraph: int,
    side: int = 0,
) -> Iterator[Site]:
    for note in element.notes:
        if not is_fse_note(note.text):
            continue
        yield _inline_site(element, note, paragraph, side)


def _inline_site(
    element: Action | Dialog | Slug | Section | Transition | PageBreak,
    note: InlineNote,
    paragraph: int,
    side: int,
) -> Site:
    offset = note.offset or 0
    if isinstance(element, Action):
        assert isinstance(note.part, int)
        cue = Cue(paragraph, side, note.part, offset)
        if element.centered:
            return Site(note.text, note.line, cue, misplaced="centred text")
        glued = str(element.lines[note.part]).strip() == ""
        return Site(note.text, note.line, cue, glued=glued)
    if isinstance(element, Dialog):
        if note.part == "character":
            cue = Cue(paragraph, side, -1, 0)
            return Site(note.text, note.line, cue, misplaced="a character cue")
        assert isinstance(note.part, int)
        cue = Cue(paragraph, side, note.part, offset)
        glued = str(element.blocks[note.part][1]).strip() == ""
        return Site(
            note.text, note.line, cue, glued=glued, speaker=str(element.character)
        )
    where = _MISPLACED[type(element)]
    if note.part == "synopsis":
        where = "a synopsis"
    return Site(note.text, note.line, Cue(paragraph), misplaced=where)


def collect_sites(screenplay: Screenplay) -> list[Site]:
    """Every FSE note in the script, in script order."""
    sites = [
        Site(note.text, note.line, Cue(TITLE_PAGE), misplaced="the title page")
        for note in screenplay.title_page_notes
        if is_fse_note(note.text)
    ]
    for index, para in enumerate(screenplay.paragraphs):
        if isinstance(para, Note):
            if is_fse_note(para.text):
                sites.append(Site(para.text, para.line, Cue(index)))
        elif isinstance(para, DualDialog):
            sites += _element_sites(para.left, index, 0)
            sites += _element_sites(para.right, index, 1)
        else:
            sites += _element_sites(para, index)
    return sites


def has_fse_notes(screenplay: Screenplay) -> bool:
    """Whether a script has any FSE note, closed or not. Cheap enough to
    run on every script before deciding to process it.
    """
    if any(is_unclosed_fse_note(note.text) for note in screenplay.unclosed_notes):
        return True
    if any(is_fse_note(note.text) for note in screenplay.title_page_notes):
        return True
    for para in screenplay.paragraphs:
        if isinstance(para, Note):
            if is_fse_note(para.text):
                return True
        elif isinstance(para, DualDialog):
            notes = para.left.notes + para.right.notes
            if any(is_fse_note(note.text) for note in notes):
                return True
        elif any(is_fse_note(note.text) for note in para.notes):
            return True
    return False


def words(text: str) -> int:
    return len(_word_re.findall(text))


def _parts(element: SCREENPLAY_TYPES) -> list[str]:
    """The performed parts of an element (§6.7): action lines, and the
    lines of a speech including parentheticals. Anything else counts zero.
    """
    if isinstance(element, Action) and not element.centered:
        return [str(line) for line in element.lines]
    if isinstance(element, Dialog):
        return [str(text) for _, text in element.blocks]
    return []


class ScriptPositions:
    """Counts the words performed before each cue."""

    def __init__(self, screenplay: Screenplay) -> None:
        self.paragraphs = screenplay.paragraphs
        counts = [self._words(para) for para in self.paragraphs]
        self._before = [0, *accumulate(counts)]

    @staticmethod
    def _words(para: SCREENPLAY_TYPES) -> int:
        if isinstance(para, DualDialog):
            return sum(words(part) for part in _parts(para.left) + _parts(para.right))
        return sum(words(part) for part in _parts(para))

    def at(self, cue: Cue) -> int:
        """The script position of a cue. A note inside a word, or at the
        end of a line, falls on that word.
        """
        if cue.paragraph < 0:
            return 0
        position = self._before[cue.paragraph]
        if cue.part < 0:
            return position
        para = self.paragraphs[cue.paragraph]
        element = para
        if isinstance(para, DualDialog):
            element = para.left
            if cue.side == 1:
                position += sum(words(part) for part in _parts(para.left))
                element = para.right
        parts = _parts(element)
        position += sum(words(part) for part in parts[: cue.part])
        if cue.part < len(parts):
            starts = (match.start() for match in _word_re.finditer(parts[cue.part]))
            position += sum(1 for start in starts if start < cue.offset)
        return position
