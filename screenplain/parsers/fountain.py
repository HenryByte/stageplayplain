# Copyright (c) 2011 Martin Vilcans
# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php

import itertools
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from io import StringIO

from screenplain.richstring import RichString, emphasis_offset, parse_emphasis, plain
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

slug_regexes = (
    re.compile(r"^(INT|EXT|EST)[ .]"),
    re.compile(r"^(INT\.?/EXT\.?)[ .]"),
    re.compile(r"^I/E[ .]"),
)

boneyard_re = re.compile(r"/\*.*?\*/", flags=re.DOTALL)

TWOSPACE = " " * 2

linebreak_re = re.compile("\r\n|\n|\r")

title_page_key_re = re.compile(r"([^:]+):\s*(.*)")
title_page_value_re = re.compile(r"(?:\s{3,}|\t)(.+)")

centered_re = re.compile(r"\s*>\s*(.*?)\s*<\s*$")
dual_dialog_re = re.compile(r"^(.+?)(\s*\^)$")
slug_re = re.compile(r"(?:(\.)(?=[^.])\s*)?(\S.*?)\s*$")
scene_number_re = re.compile(r"(.*?)\s*(?:#([\w\-.]+)#)\s*$")
section_re = re.compile(r"^(#{1,6})\s*([^#].*)$")
transition_re = re.compile(r"(>?)\s*(.+?)(TO:)?$")
page_break_re = re.compile(r"^={3,}$")
note_re = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)
# A title page line holding nothing but notes, with its line break.
title_page_note_line_re = re.compile(
    r"^[ \t]*(?:\[\[.*?\]\][ \t]*)+(?:\n|\Z)", re.DOTALL | re.MULTILINE
)


def _sequence_to_rich(lines: Iterable[str]) -> list[RichString]:
    """Converts a sequence of strings into a list of RichString."""
    return [parse_emphasis(line) for line in lines]


def _string_to_rich(line: str) -> RichString:
    """Converts a single string into a RichString."""
    return parse_emphasis(line)


@dataclass
class _CutNote:
    """A note cut out of a paragraph, before the paragraph is classified.

    `row` and `column` give its place in the paragraph's lines after
    every note has been cut out.
    """

    text: str
    line: int
    row: int
    column: int


def _offset(raw: str, column: int, start: int, source: str, upper: bool = False) -> int:
    """Maps a column in a raw line to an offset into the rendered text.

    `source` is the text passed to `parse_emphasis`. It starts at `start`
    in `raw` and matches it character for character, or after `upper()`
    when `upper` is set. A column outside `source` is clamped to its ends.

    >>> _offset('!  fa*ir* ', 5, 1, '  fa*ir*')
    4
    >>> _offset('.int. hall #1#', 9, 1, 'INT. HALL', upper=True)
    8
    >>> _offset('  hello  ', 9, 2, 'hello')
    5
    """
    prefix = raw[start : max(start, column)]
    if upper:
        prefix = prefix.upper()
    return emphasis_offset(source, min(len(prefix), len(source)))


class InputParagraph:
    def __init__(
        self,
        lines: list[str],
        notes: list[_CutNote] | None = None,
        line: int | None = None,
    ) -> None:
        self.lines = lines
        self.notes = notes or []
        # The 1-based source line of the first line, when known.
        self.line = line

    def _add_note(
        self,
        element: SCREENPLAY_TYPES,
        note: _CutNote,
        part: int | str | None,
        start: int = 0,
        source: str | None = None,
        upper: bool = False,
    ) -> None:
        """Records `note` on `element`.

        `source` is the text of `part` passed to `parse_emphasis`, found at
        `start` in the note's line. Without it the note gets no offset.
        """
        assert not isinstance(element, (DualDialog, Note))
        offset = (
            None
            if source is None
            else _offset(self.lines[note.row], note.column, start, source, upper)
        )
        element.notes.append(InlineNote(note.text, note.line, part, offset))

    def update_list(self, previous_paragraphs: list[SCREENPLAY_TYPES]) -> None:
        """Inserts this paragraph into a list.
        Modifies the `previous_paragraphs` list.
        """
        (
            self.append_forced_action(previous_paragraphs)
            or self.append_page_break(previous_paragraphs)
            or self.append_synopsis(previous_paragraphs)
            or self.append_sections_and_synopsises(previous_paragraphs)
            or self.append_slug(previous_paragraphs)
            or self.append_centered_action(previous_paragraphs)
            or self.append_dialog(previous_paragraphs)
            or self.append_transition(previous_paragraphs)
            or self.append_action(previous_paragraphs)
        )

    def append_slug(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        if len(self.lines) != 1:
            return False

        match = slug_re.match(self.lines[0])
        if not match:
            return False

        period, text = match.groups()
        start = match.start(2)
        text = text.upper()
        if not period and not any(regex.match(text) for regex in slug_regexes):
            return False

        match = scene_number_re.match(text)
        if match:
            text, scene_number = match.groups()
            slug = Slug(_string_to_rich(text), plain(scene_number))
        else:
            slug = Slug(_string_to_rich(text))
        for note in self.notes:
            self._add_note(slug, note, None, start, text, upper=True)
        paragraphs.append(slug)
        return True

    def append_sections_and_synopsises(
        self, paragraphs: list[SCREENPLAY_TYPES]
    ) -> bool:
        new_paragraphs = []

        # The section each line belongs to, and the line's match if it is
        # the heading rather than a synopsis.
        owners: list[tuple[Section, re.Match[str] | None]] = []

        for line in self.lines:
            match = section_re.match(line)
            if match:
                hashes, text = match.groups()
                section = Section(_string_to_rich(text), len(hashes))
                new_paragraphs.append(section)
                owners.append((section, match))
            elif (
                line.startswith("=")
                and new_paragraphs
                and hasattr(new_paragraphs[-1], "set_synopsis")
            ):
                new_paragraphs[-1].set_synopsis(line[1:].lstrip())
                owners.append((new_paragraphs[-1], None))
            else:
                return False

        for note in self.notes:
            section, match = owners[note.row]
            if match:
                self._add_note(section, note, None, match.start(2), match.group(2))
            else:
                self._add_note(section, note, "synopsis")
        paragraphs += new_paragraphs
        return True

    def append_centered_action(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        matches = []
        for line in self.lines:
            match = centered_re.match(line)
            if not match:
                return False
            matches.append(match)
        if not matches:
            return False
        action = Action(
            _sequence_to_rich(match.group(1) for match in matches), centered=True
        )
        for note in self.notes:
            match = matches[note.row]
            self._add_note(action, note, note.row, match.start(1), match.group(1))
        paragraphs.append(action)
        return True

    def _create_dialog(self, character: str, start: int) -> Dialog:
        """Creates a dialogue whose character cue is `character`,
        found at `start` in the first line.
        """
        dialog = Dialog(
            parse_emphasis(character.strip()),
            _sequence_to_rich(line.strip() for line in self.lines[1:]),
        )
        dialog.line = self.line
        for note in self.notes:
            if note.row == 0:
                text, part = character, "character"
                text_start = start
            else:
                text, part = self.lines[note.row], note.row - 1
                text_start = 0
            text_start += len(text) - len(text.lstrip())
            self._add_note(dialog, note, part, text_start, text.strip())
        return dialog

    def append_dialog(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        if len(self.lines) < 2:
            return False

        character = self.lines[0]
        start = 0
        if character.endswith(TWOSPACE):
            return False
        if character.startswith("@") and len(character) >= 2:
            character = character[1:]
            start = 1
        else:
            before_paren, *_ = character.split("(", 1)
            if not before_paren.isupper():
                return False

        if paragraphs and isinstance(paragraphs[-1], Dialog):
            dual_match = dual_dialog_re.match(character)
            if dual_match:
                previous = paragraphs.pop()
                assert isinstance(previous, Dialog)
                dialog = self._create_dialog(dual_match.group(1), start)
                paragraphs.append(DualDialog(previous, dialog))
                return True

        paragraphs.append(self._create_dialog(character, start))
        return True

    def append_transition(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        if len(self.lines) != 1:
            return False

        match = transition_re.match(self.lines[0])
        if not match:
            return False
        greater_than, text, to_colon = match.groups()

        if greater_than:
            text = text.upper() + (to_colon or "")
        elif text.isupper() and to_colon:
            text = text + to_colon
        else:
            return False

        transition = Transition(_string_to_rich(text))
        for note in self.notes:
            self._add_note(
                transition, note, None, match.start(2), text, upper=bool(greater_than)
            )
        paragraphs.append(transition)
        return True

    def append_forced_action(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        if self.lines[0].startswith("!"):
            return self.append_action(paragraphs)
        else:
            return False

    def append_action(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        action = Action(
            _sequence_to_rich(
                line[1:].rstrip() if line.startswith("!") else line.rstrip()
                for line in self.lines
            )
        )
        for note in self.notes:
            line = self.lines[note.row]
            start = 1 if line.startswith("!") else 0
            self._add_note(action, note, note.row, start, line[start:].rstrip())
        paragraphs.append(action)
        return True

    def append_synopsis(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        if (
            len(self.lines) == 1
            and self.lines[0].startswith("=")
            and paragraphs
            and isinstance(paragraphs[-1], (Slug, Section))
        ):
            paragraphs[-1].set_synopsis(self.lines[0][1:].lstrip())
            for note in self.notes:
                self._add_note(paragraphs[-1], note, "synopsis")
            return True
        else:
            return False

    def append_page_break(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        if len(self.lines) == 1 and page_break_re.match(self.lines[0]):
            page_break = PageBreak()
            for note in self.notes:
                self._add_note(page_break, note, None)
            paragraphs.append(page_break)
            return True
        else:
            return False


def _preprocess_line(raw_line: str) -> str:
    r"""Replaces tabs with spaces and removes trailing end of line markers.

    >>> _preprocess_line('foo \r\n\n')
    'foo '

    """
    return raw_line.expandtabs(4).rstrip("\r\n")


def _is_blank(line: str) -> bool:
    return line == "" or line == " "


def parse(stream: StringIO) -> Screenplay:
    """Parses Fountain source.

    Returns a Screenplay object.

    """
    lines, line_numbers = _remove_boneyard(stream.read())
    return parse_lines(lines, line_numbers)


def _remove_boneyard(content: str) -> tuple[list[str], list[int]]:
    r"""Removes boneyard (`/* ... */`) and splits the content into lines.

    Returns the lines and the 1-based source line number of each.

    >>> _remove_boneyard('a /* b\n c */d\ne')
    (['a d', 'e'], [1, 3])
    """
    lines = [""]
    line_numbers = [1]
    line_number = 1
    pos = 0
    for match in itertools.chain(boneyard_re.finditer(content), [None]):
        end = match.start() if match else len(content)
        first, *rest = linebreak_re.split(content[pos:end])
        lines[-1] += first
        for line in rest:
            line_number += 1
            lines.append(line)
            line_numbers.append(line_number)
        if match:
            line_number += len(linebreak_re.findall(match.group(0)))
            pos = match.end()
    return lines, line_numbers


def parse_lines(
    source: list[str], line_numbers: Sequence[int] | None = None
) -> Screenplay:
    """Reads raw text input and generates paragraph objects.

    `line_numbers` gives the 1-based source line number of each line
    and defaults to counting from 1.

    Returns a Screenplay object.

    """
    if line_numbers is None:
        line_numbers = range(1, len(source) + 1)

    # Strip the leading blank lines.
    start = next(
        (i for i, line in enumerate(source) if line.strip() != ""), len(source)
    )
    lines = [_preprocess_line(line) for line in source[start:]]
    line_numbers = line_numbers[start:]

    end = next((i for i, line in enumerate(lines) if line == ""), len(lines))
    title_page_lines = lines[:end]

    title_page_notes: list[Note] = []
    unclosed_notes: list[Note] = []
    if title_page_lines and title_page_key_re.match(title_page_lines[0]):
        title_page_lines, title_page_notes, unclosed_notes = _cut_title_page_notes(
            title_page_lines, line_numbers
        )

    # parse_title_page converts the keys to consistent casing.
    # As of now, the only use of the dictionary is generating the title page,
    # but if an export module displays the keys, this may not
    # look like the author intended.
    title_page = parse_title_page(title_page_lines)

    if title_page:
        # The first lines were a title page.
        # Parse the rest of the source as screenplay body.
        paragraphs = parse_body(
            lines[end + 1 :], line_numbers[end + 1 :], unclosed_notes
        )
        return Screenplay(title_page, paragraphs, title_page_notes, unclosed_notes)
    else:
        # The first lines were not a title page.
        # Parse them as part of the screenplay body.
        unclosed_notes = []
        paragraphs = parse_body(lines, line_numbers, unclosed_notes)
        return Screenplay({}, paragraphs, unclosed_notes=unclosed_notes)


def _cut_title_page_notes(
    lines: list[str], line_numbers: Sequence[int]
) -> tuple[list[str], list[Note], list[Note]]:
    """Removes the title page lines that hold nothing but notes.

    Returns the remaining lines, every note on the title page, and the
    unclosed notes in it.
    """
    content = "\n".join(lines)
    notes: list[Note] = []
    unclosed: list[Note] = []
    if "[[" in content:
        _, cut_notes, unclosed = _cut_notes(content, line_numbers)
        notes = [Note(note.text, note.line) for note in cut_notes]

    cut_any = False

    def cut(match: re.Match[str]) -> str:
        nonlocal cut_any
        cut_any = True
        return ""

    content = title_page_note_line_re.sub(cut, content)
    if not cut_any:
        return lines, notes, unclosed
    # A note-only last line leaves the line break before it.
    remaining = content.removesuffix("\n")
    return (remaining.split("\n") if remaining else []), notes, unclosed


def parse_body(
    source: list[str],
    line_numbers: Sequence[int] | None = None,
    unclosed_notes: list[Note] | None = None,
) -> list[SCREENPLAY_TYPES]:
    """Reads lines of the main screenplay and generates paragraph objects.

    `line_numbers` gives the 1-based source line number of each line
    and defaults to counting from 1. Unclosed notes are appended to
    `unclosed_notes` when it is given.
    """
    if line_numbers is None:
        line_numbers = range(1, len(source) + 1)

    paragraphs: list[SCREENPLAY_TYPES] = []
    end = 0
    for blank, group in itertools.groupby(source, _is_blank):
        input_lines = list(group)
        start = end
        end += len(input_lines)
        if blank:
            continue
        as_string = "\n".join(input_lines)
        if "[[" not in as_string:
            InputParagraph(as_string.split("\n"), line=line_numbers[start]).update_list(
                paragraphs
            )
            continue

        as_string, notes, unclosed = _cut_notes(as_string, line_numbers[start:end])
        if unclosed_notes is not None:
            unclosed_notes += unclosed
        if notes and as_string.strip() == "":
            # A standalone note, or several stacked.
            paragraphs += [Note(note.text, note.line) for note in notes]
            continue
        if _is_blank(as_string):
            continue
        paragraph = InputParagraph(as_string.split("\n"), notes, line_numbers[start])
        paragraph.update_list(paragraphs)

    return paragraphs


def _cut_notes(
    paragraph: str, line_numbers: Sequence[int]
) -> tuple[str, list[_CutNote], list[Note]]:
    """Cuts every note out of a paragraph whose lines have the source line
    numbers `line_numbers`.

    Returns the paragraph without notes, the notes in source order, and
    the unclosed notes: each `[[` left with no `]]` after it, which stays
    in the paragraph.
    """
    pieces: list[str] = []
    notes: list[_CutNote] = []
    row = 0
    column = 0
    pos = 0
    unclosed: list[Note] = []

    def find_unclosed(start: int, end: int) -> None:
        index = paragraph.find("[[", start, end)
        while index != -1:
            line = line_numbers[paragraph.count("\n", 0, index)]
            unclosed.append(Note(paragraph[index + 2 :], line))
            index = paragraph.find("[[", index + 2, end)

    for match in note_re.finditer(paragraph):
        find_unclosed(pos, match.start())
        piece = paragraph[pos : match.start()]
        pieces.append(piece)
        if "\n" in piece:
            row += piece.count("\n")
            column = len(piece) - piece.rindex("\n") - 1
        else:
            column += len(piece)
        line = line_numbers[paragraph.count("\n", 0, match.start())]
        notes.append(_CutNote(match.group(1), line, row, column))
        pos = match.end()
    find_unclosed(pos, len(paragraph))
    pieces.append(paragraph[pos:])
    return "".join(pieces), notes, unclosed


def parse_title_page(lines: list[str]) -> dict[str, list[str]] | None:
    """Parse the title page.

    Spec: http://fountain.io/syntax/#title-page
    Returns None if the document does not have a title page section,
    otherwise a dictionary with the data.

    Converts the keys using str.capitalize,
    (all lowercase except for the first letter, which is uppercase).
    So writing the key as "Author:" and "author:" both
    will add to the same "Author" key in the resulting dictionary.
    """
    result: dict[str, list[str]] = {}

    it = iter(lines)
    try:
        line = next(it)
        key_match = title_page_key_re.match(line)
        if not key_match:
            return None
        while True:
            key, value = key_match.groups()
            key = key.capitalize()
            if value:
                # Single line key/value
                result.setdefault(key, []).append(value)
                line = next(it)
            else:
                for line in it:
                    value_match = title_page_value_re.match(line)
                    if not value_match:
                        break
                    result.setdefault(key, []).append(value_match.group(1))
                else:
                    # Last line has been processed
                    break

            key_match = title_page_key_re.match(line)
            if not key_match:
                raise ValueError(f"Invalid title page format on line '{line}'")
    except StopIteration:
        pass
    return result
