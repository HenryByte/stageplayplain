# Copyright (c) 2011 Martin Vilcans
# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php

from __future__ import annotations

from collections.abc import Iterator
from typing import TypeAlias

from screenplain.richstring import RichString, parse_emphasis

SCREENPLAY_TYPES: TypeAlias = (
    "Slug | Section | Dialog | DualDialog | Action | Transition | PageBreak"
)


class Screenplay:
    def __init__(
        self,
        title_page: dict[str, list[str]] | None = None,
        paragraphs: list[SCREENPLAY_TYPES] | None = None,
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
    def __init__(self, line: RichString, scene_number: int = None) -> None:
        """Creates a scene heading (slug).
        The line parameter is a RichString with the slugline.
        The scene_number parameter is an optional RichString.

        """
        self.line: RichString = line
        self.scene_number = scene_number
        self.synopsis = None

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
        self.synopsis: str = synopsis

    def set_synopsis(self, text: str) -> None:
        self.synopsis = text

    def __repr__(self) -> str:
        return f"Section({self.text!r}, {self.level!r}, {self.synopsis!r})"

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
        if lines:
            self._parse(lines)

    def _parse(self, lines: list[RichString]):
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


class Transition:
    def __init__(self, line: RichString) -> None:
        self.line = line

    @property
    def lines(self) -> list[RichString]:
        return [self.line]


class PageBreak:
    pass
