# Copyright (c) 2011 Martin Vilcans
# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import override

from screenplain.richstring import RichString, parse_emphasis

# The paragraph types that are script elements, i.e. everything but notes.
type ELEMENT_TYPES = (
    Slug | Section | Dialog | DualDialog | Action | Transition | PageBreak
)

type SCREENPLAY_TYPES = ELEMENT_TYPES | Note


@dataclass
class Note:
    """A Fountain note that is a paragraph of its own (a standalone note).

    `text` is everything between `[[` and `]]`; `line` is the 1-based
    source line the note starts on. Exporters skip it.
    """

    text: str
    line: int


@dataclass
class InlineNote:
    """A Fountain note inside another paragraph.

    `part` says which part of the paragraph the note sits in, and depends
    on the paragraph type: an index into `Action.lines` or `Dialog.blocks`,
    `"character"` for a dialogue's character cue, `"synopsis"` for the
    synopsis of a `Slug` or `Section`, or None where the paragraph has a
    single line (`Slug`, `Section`, `Transition`) or no text (`PageBreak`).

    `offset` counts characters of `str()` of that part before the note.
    It is None for a synopsis and a page break.
    """

    text: str
    line: int
    part: int | str | None
    offset: int | None


class Screenplay:
    def __init__(
        self,
        title_page: dict[str, list[str]] | None = None,
        paragraphs: list[SCREENPLAY_TYPES] | None = None,
        title_page_notes: list[Note] | None = None,
    ) -> None:
        """
        Create a Screenplay object.

        `title_page` is a dictionary mapping string keys to strings.
        `paragraphs` is a sequence of paragraph objects.
        """

        # Key/value pairs for title page
        if title_page is None:
            self.title_page: dict[str, list[str]] = {}
        else:
            self.title_page: dict[str, list[str]] = title_page

        # The paragraphs of the actual script
        if paragraphs is None:
            self.paragraphs: list[SCREENPLAY_TYPES] = []
        else:
            self.paragraphs: list[SCREENPLAY_TYPES] = paragraphs

        # Notes on title page lines that hold nothing but notes
        self.title_page_notes: list[Note] = title_page_notes or []

    def get_rich_attribute(
        self, name: str, default: list[RichString] | None = None
    ) -> list[RichString]:
        """Get an attribute from the title page parsed into a RichString.
        Returns a list of RichString objects.

        E.g. `screenplay.get_rich_attribute('Title')`

        """
        if default is None:
            default = []
        if name in self.title_page:
            return [parse_emphasis(line) for line in self.title_page[name]]
        else:
            return default

    def append(self, paragraph: SCREENPLAY_TYPES) -> None:
        """Append a paragraph to this screenplay."""
        self.paragraphs.append(paragraph)

    def __iter__(self) -> Iterator[SCREENPLAY_TYPES]:
        """Get an iterator over the paragraphs of this screenplay."""
        return iter(self.paragraphs)


class Slug:
    def __init__(
        self, line: RichString, scene_number: RichString | None = None
    ) -> None:
        """Creates a scene heading (slug).
        The line parameter is a RichString with the slugline.
        The scene_number parameter is an optional RichString.

        """
        self.line: RichString = line
        self.scene_number = scene_number
        self.synopsis = None
        self.notes: list[InlineNote] = []

    @property
    def lines(self) -> list[RichString]:
        return [self.line]

    def set_synopsis(self, text: str) -> None:
        self.synopsis = text


class Section:
    """A section heading."""

    def __init__(
        self, text: RichString, level: int, synopsis: str | None = None
    ) -> None:
        self.text: RichString = text
        self.level: int = level
        self.synopsis: str | None = synopsis
        self.notes: list[InlineNote] = []

    def set_synopsis(self, text: str) -> None:
        self.synopsis = text

    @override
    def __repr__(self) -> str:
        return f"Section({self.text!r}, {self.level!r}, {self.synopsis!r})"

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Section):
            return NotImplemented

        return (
            self.text == other.text
            and self.level == other.level
            and self.synopsis == other.synopsis
        )


class Dialog:
    def __init__(
        self, character: RichString, lines: list[RichString] | None = None
    ) -> None:
        self.character: RichString = character
        self.blocks = []  # list of tuples of (is_parenthetical, text)
        self.notes: list[InlineNote] = []
        if lines:
            self._parse(lines)

    def _parse(self, lines: list[RichString]) -> None:
        inside_parenthesis = False
        for line in lines:
            if line.startswith("("):
                inside_parenthesis = True
            self.blocks.append((inside_parenthesis, line))
            if line.endswith(")"):
                inside_parenthesis = False

    def add_line(self, line: str) -> None:
        parenthetical = line.startswith("(")
        self.blocks.append((parenthetical, line))


class DualDialog:
    def __init__(self, left_dialog: Dialog, right_dialog: Dialog) -> None:
        self.left: Dialog = left_dialog
        self.right: Dialog = right_dialog


class Action:
    def __init__(self, lines: list[RichString], centered: bool = False) -> None:
        self.lines: list[RichString] = lines
        self.centered = centered
        self.notes: list[InlineNote] = []


class Transition:
    def __init__(self, line: RichString) -> None:
        self.line = line
        self.notes: list[InlineNote] = []

    @property
    def lines(self) -> list[RichString]:
        return [self.line]


class PageBreak:
    def __init__(self) -> None:
        self.notes: list[InlineNote] = []


# Stage play types. See screenplain/stageplay.py for how a parsed Screenplay
# is restructured into a StagePlay.


@dataclass
class CharacterName:
    """A character name referenced inline in a stage direction with `@`."""

    name: RichString


@dataclass
class StageDirection:
    """An action paragraph in a stage play.

    Each line is a sequence of parts: plain text or inline character names.
    """

    lines: list[list[RichString | CharacterName]]


@dataclass
class Act:
    text: RichString


@dataclass
class Scene:
    text: RichString


@dataclass
class CastMember:
    name: RichString
    description: list[RichString] = field(default_factory=list)


@dataclass
class CastGroup:
    title: RichString


@dataclass
class CastList:
    """A front matter section listing the characters of the play."""

    title: RichString
    entries: list[CastMember | CastGroup | StageDirection] = field(default_factory=list)


type FRONT_MATTER_PARAGRAPH_TYPES = StageDirection | Section | ELEMENT_TYPES


@dataclass
class FrontMatterSection:
    """A generic front matter section, such as Notes, Time or Setting.

    `title` is None for front matter text before the first heading.
    """

    title: RichString | None
    paragraphs: list[FRONT_MATTER_PARAGRAPH_TYPES] = field(default_factory=list)


type STAGEPLAY_TYPES = (
    Act | Scene | StageDirection | Dialog | DualDialog | Action | Transition | PageBreak
)


class StagePlay(Screenplay):
    """A stage play: title page, front matter and the play body.

    Iterating over a StagePlay yields nothing; use `body` instead.
    """

    def __init__(
        self,
        title_page: dict[str, list[str]] | None = None,
        front_matter: list[FrontMatterSection | CastList] | None = None,
        body: list[STAGEPLAY_TYPES] | None = None,
    ) -> None:
        super().__init__(title_page)
        self.front_matter: list[FrontMatterSection | CastList] = front_matter or []
        self.body: list[STAGEPLAY_TYPES] = body or []
