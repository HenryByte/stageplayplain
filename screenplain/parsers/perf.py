import re
from collections.abc import Iterable, Sequence

from screenplain.richstring import RichString, parse_emphasis, plain
from screenplain.types import (
    SCREENPLAY_TYPES,
    Action,
    Dialog,
    DualDialog,
    PageBreak,
    Screenplay,
    Section,
    Slug,
    Transition,
)

slug_regexes = (
    re.compile(r"^(INT|EXT|EST)[ .]", re.IGNORECASE),
    re.compile(r"^(INT\.?/EXT\.?)[ .]", re.IGNORECASE),
    re.compile(r"^I/E[ .]", re.IGNORECASE),
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
note_re = re.compile(r"\[\[.*?\]\]", re.DOTALL)


def _preprocess_line(raw_line: str) -> str:
    r"""Replaces tabs with spaces and removes trailing end of line markers.

    >>> _preprocess_line('foo \r\n\n')
    'foo '

    """
    return raw_line.expandtabs(4).rstrip("\r\n")


def _is_blank(line: str) -> bool:
    return line == "" or line == " "


def _sequence_to_rich(lines: Iterable[str]) -> list[RichString]:
    """Converts a sequence of strings into a list of RichString."""
    return [parse_emphasis(line) for line in lines]


def _string_to_rich(line: str) -> RichString:
    """Converts a single string into a RichString."""
    return parse_emphasis(line)


class InputParagraph:
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines

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
        text = text.upper()
        if not period and not any(regex.match(text) for regex in slug_regexes):
            return False

        match = scene_number_re.match(text)
        if match:
            text, scene_number = match.groups()
            paragraphs.append(Slug(_string_to_rich(text), plain(scene_number)))
        else:
            paragraphs.append(Slug(_string_to_rich(text)))
        return True

    def append_sections_and_synopsises(
        self, paragraphs: list[SCREENPLAY_TYPES]
    ) -> bool:
        new_paragraphs = []

        for line in self.lines:
            match = section_re.match(line)
            if match:
                hashes, text = match.groups()
                section = Section(_string_to_rich(text), len(hashes))
                new_paragraphs.append(section)
            elif (
                line.startswith("=")
                and new_paragraphs
                and hasattr(new_paragraphs[-1], "set_synopsis")
            ):
                new_paragraphs[-1].set_synopsis(line[1:].lstrip())
            else:
                return False

        paragraphs += new_paragraphs
        return True

    def append_centered_action(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        matches = []
        for line in self.lines:
            match = centered_re.match(line)
            if not match:
                return False
            matches.append(match.group(1))
        if not matches:
            return False
        paragraphs.append(Action(_sequence_to_rich(matches), centered=True))
        return True

    def _create_dialog(self, character: str) -> Dialog:
        return Dialog(
            parse_emphasis(character.strip()),
            _sequence_to_rich(line.strip() for line in self.lines[1:]),
        )

    def append_dialog(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        if len(self.lines) < 2:
            return False

        character = self.lines[0]
        if character.endswith(TWOSPACE):
            return False
        if character.startswith("@") and len(character) >= 2:
            character = character[1:]
        else:
            before_paren, *_ = character.split("(", 1)
            if not before_paren.isupper():
                return False

        if paragraphs and isinstance(paragraphs[-1], Dialog):
            dual_match = dual_dialog_re.match(character)
            if dual_match:
                previous = paragraphs.pop()
                assert isinstance(previous, Dialog)
                dialog = self._create_dialog(dual_match.group(1))
                paragraphs.append(DualDialog(previous, dialog))
                return True

        paragraphs.append(self._create_dialog(character))
        return True

    def append_transition(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        if len(self.lines) != 1:
            return False

        match = transition_re.match(self.lines[0])
        if not match:
            return False
        greater_than, text, to_colon = match.groups()

        if greater_than:
            paragraphs.append(
                Transition(_string_to_rich(text.upper() + (to_colon or "")))
            )
            return True

        if text.isupper() and to_colon:
            paragraphs.append(Transition(_string_to_rich(text + to_colon)))
            return True

        return False

    def append_forced_action(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        if self.lines[0].startswith("!"):
            return self.append_action(paragraphs)
        else:
            return False

    def append_action(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        paragraphs.append(
            Action(
                _sequence_to_rich(
                    line[1:].rstrip() if line.startswith("!") else line.rstrip()
                    for line in self.lines
                )
            )
        )
        return True

    def append_synopsis(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        if (
            len(self.lines) == 1
            and self.lines[0].startswith("=")
            and paragraphs
            and isinstance(paragraphs[-1], (Slug, Section))
        ):
            paragraphs[-1].set_synopsis(self.lines[0][1:].lstrip())
            return True
        else:
            return False

    def append_page_break(self, paragraphs: list[SCREENPLAY_TYPES]) -> bool:
        if len(self.lines) == 1 and page_break_re.match(self.lines[0]):
            paragraphs.append(PageBreak())
            return True
        else:
            return False


def create_action(lines: Sequence[str], start_idx: int, end_idx: int) -> Action:
    return Action(
        _sequence_to_rich(
            line[1:].rstrip() if line.startswith("!") else line.rstrip()
            for line in lines[start_idx:end_idx]
        )
    )


def create_centered_action(
    lines: Sequence[str], start_idx: int, end_idx: int
) -> Action:

    stripped_lines = []
    for line in lines[start_idx:end_idx]:
        if line[0] != ">" or line[-1] != "<":
            raise ValueError(f"Invalid centered action: {line}")
        stripped_lines.append(line[1:-1].strip())
    return Action(_sequence_to_rich(stripped_lines), centered=True)


def create_slug(line: str, has_period: bool = False) -> Slug:
    text = line[1:] if has_period else line
    text = text.upper()

    match = scene_number_re.match(text)
    if match:
        text, scene_number = match.groups()
        return Slug(_string_to_rich(text), plain(scene_number))
    else:
        return Slug(_string_to_rich(text))


def _create_dialog(
    character: str, lines: Sequence[str], start_idx: int, end_idx: int
) -> Dialog:
    return Dialog(
        parse_emphasis(character.strip()),
        _sequence_to_rich(lines[i].strip() for i in range(start_idx, end_idx)),
    )


def create_dialog(
    lines: Sequence[str],
    start_idx: int,
    end_idx: int,
    state: list[SCREENPLAY_TYPES],
    *,
    forced_dialog: bool = False,
) -> Dialog | DualDialog:
    char_idx = 1 if forced_dialog else 0
    if lines[start_idx][-1] == "^":
        if not state:
            raise ValueError("Cannot have a dual dialog at the start of the screenplay")
        if not isinstance(state[-1], Dialog):
            raise ValueError(
                f"Dual dialog needs to follow dialog, it followed: type={type(state[-1]).__name__}"
            )

        # This removes the previous value from state, which is bad, refactor this later
        previous = state.pop()
        assert isinstance(previous, Dialog)
        dialog = _create_dialog(
            lines[start_idx][char_idx:-1], lines, start_idx + 1, end_idx
        )
        return DualDialog(previous, dialog)

    return _create_dialog(lines[start_idx][char_idx:], lines, start_idx + 1, end_idx)


def process_lines(
    lines: Sequence[str], start_idx: int, end_idx: int, state: list[SCREENPLAY_TYPES]
) -> SCREENPLAY_TYPES:
    command_line = lines[start_idx]
    if command_line[0] == "!":
        # A forced action
        return create_action(lines, start_idx, end_idx)
    elif command_line[0] == ">":
        if command_line[-1] == "<":
            # TODO this is just a hack to accommodate the current bug
            #  Fixed with https://github.com/HenryByte/stageplayplain/issues/9
            if all(
                line[0] == ">" and line[-1] == "<" for line in lines[start_idx:end_idx]
            ):
                return create_centered_action(lines, start_idx, end_idx)
        else:
            # Transition
            pass
    elif start_idx == end_idx - 1:
        # Only stuff with a single line

        # Scene header
        if command_line[0] == ".":
            return create_slug(command_line, True)
        elif any(regex.match(command_line) for regex in slug_regexes):
            return create_slug(command_line)
    elif end_idx >= start_idx + 2:
        # There are at least 2 lines
        if command_line[0] == "@":
            if len(command_line) < 2:
                raise ValueError(f"Character line too short: {command_line}")
            return create_dialog(lines, start_idx, end_idx, state, forced_dialog=True)
        else:
            # This is a really weird thing which makes sure it's an Action
            if not command_line.endswith(TWOSPACE):
                paren = command_line.find("(")
                # Allocation but implemented in c so faster
                if (
                    paren != -1 and command_line[:paren].isupper()
                ) or command_line.isupper():
                    # This is dialog
                    return create_dialog(lines, start_idx, end_idx, state)

    return create_action(lines, start_idx, end_idx)
    print(lines)
    print(lines[start_idx:end_idx])
    return None
    # raise Exception("Not implemented")


def parse_body(source: Sequence[str], source_idx: int) -> list[SCREENPLAY_TYPES]:
    """Reads lines of the main screenplay and generates paragraph objects."""

    paragraphs: list[SCREENPLAY_TYPES] = []

    # tmp_idx = source_idx

    # TODO: Duplicate, make a parser or something when it's all working
    def read_line(strip: bool = True) -> str:
        nonlocal source_idx
        raw = source[source_idx]
        source_idx += 1
        # Keep lines with 2 spaces, because of a dumb rule with diaglogue
        raw = raw.strip() if strip and raw != "  " else raw
        return _preprocess_line(raw)

    # Sections are always followed by a blank line.
    # Gather lines as we go and let the functions parse the lines
    start_idx = source_idx
    while source_idx < len(source):
        line = read_line()
        print(line)

        if _is_blank(line):
            end_idx = source_idx - 1
            if end_idx == start_idx:
                start_idx = source_idx
                # Empty section
                continue
            # We've hit the end of a type, store it
            value = process_lines(source, start_idx, end_idx, paragraphs)
            print(value)
            paragraphs.append(value)
            start_idx = source_idx
        elif source_idx == len(source):
            # We've hit the end of the file
            value = process_lines(source, start_idx, source_idx, paragraphs)
            print(value)
            paragraphs.append(value)
            break

    # for blank, input_lines in itertools.groupby(itertools.islice(source, tmp_idx, None), _is_blank):
    #     if not blank:
    #         as_string = note_re.sub("", "\n".join(input_lines))
    #         if _is_blank(as_string):
    #             continue
    #         paragraph = InputParagraph(as_string.split("\n"))
    #         paragraph.update_list(paragraphs)

    return paragraphs


def parse_lines_iter(source: list[str]) -> Screenplay:
    """Reads raw text input and generates paragraph objects.

    Returns a Screenplay object.

    """
    if not source:
        raise ValueError("Invalid fountain syntax: no contents")
    # Strip the leading blank lines.
    title_page: dict[str, list[str]] = {}
    source_idx = 0

    def read_line(strip: bool = True) -> str:
        nonlocal source_idx
        raw = source[source_idx]
        source_idx += 1
        raw = raw.strip() if strip else raw
        return _preprocess_line(raw)

    # Go through and find all the title pages
    line = read_line()
    while line == "":
        line = read_line()

    while True:
        # If it matches a title then use it
        key_match = title_page_key_re.match(line)
        if not key_match:
            source_idx -= 1
            break
        key, value = key_match.groups()
        key = key.capitalize()
        if value:
            # Single line key/value
            title_page.setdefault(key, []).append(value)
            if source_idx >= len(source):
                break
            line = read_line()
        else:
            # Multiline key/value
            end_of_lines = False
            while True:
                if source_idx >= len(source):
                    end_of_lines = True
                    break
                line = read_line(strip=False)
                value_match = title_page_value_re.match(line)
                if not value_match:
                    break
                title_page.setdefault(key, []).append(value_match.group(1))
            if end_of_lines:
                break

    if line != "" and title_page:
        raise ValueError(f"Invalid title page format on line '{line}'")

    return Screenplay(title_page, parse_body(source, source_idx))
