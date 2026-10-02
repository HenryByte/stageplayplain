# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php

"""Restructures a parsed Fountain screenplay into a stage play.

The Fountain parser is unaware of stage plays. This module takes its output
and applies the stage play conventions:

* The first page break (`===`) separates front matter from the play body.
* In the front matter, `#` headings start sections. A section named like a
  cast list (e.g. "Dramatis Personae") becomes a `CastList`.
* In the body, `#` headings are acts and `##` (or deeper) headings and
  sluglines are scenes.
* `@Name` inside action paragraphs marks a character name.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from screenplain.richstring import RichString, Segment, plain
from screenplain.types import (
    SCREENPLAY_TYPES,
    STAGEPLAY_TYPES,
    Act,
    Action,
    CastGroup,
    CastList,
    CastMember,
    CharacterName,
    Dialog,
    DualDialog,
    FrontMatterSection,
    PageBreak,
    Scene,
    Screenplay,
    Section,
    Slug,
    StageDirection,
    StagePlay,
    Transition,
)

FORMAT_VALUES = {"stage play", "stageplay"}
CAST_LIST_TITLES = {"dramatis personae", "cast", "characters", "cast of characters"}

cue_re = re.compile(r"^(.*?)\s*(\(.*\))?\s*$")
# `@` starting an inline name: at the start of a line or after a non-word
# character, so e.g. e-mail addresses are left alone.
inline_name_start_re = re.compile(r"(?<!\w)@")
fallback_name_re = re.compile(r"\w+(?:['\u2019-]\w+)*")
# Screenplay continuation markers, which have no place in a stage play.
continuation_re = re.compile(r"cont(?:['\u2019]?d|\.|inued)", re.IGNORECASE)
cue_parenthetical_re = re.compile(r"\s*\(([^()]*)\)")


def is_stageplay(screenplay: Screenplay) -> bool:
    """Checks whether the title page declares the document a stage play.

    >>> is_stageplay(Screenplay({'Format': ['Stage Play']}))
    True
    >>> is_stageplay(Screenplay({'Format': ['stageplay']}))
    True
    >>> is_stageplay(Screenplay({'Title': ['Hamlet']}))
    False
    """
    return any(
        value.strip().lower() in FORMAT_VALUES
        for value in screenplay.title_page.get("Format", [])
    )


def split_cue(character: RichString) -> tuple[str, str | None]:
    """Splits a dialogue cue into the name and an optional extension.

    >>> from screenplain.richstring import plain
    >>> split_cue(plain('Hamlet (aside)'))
    ('Hamlet', '(aside)')
    >>> split_cue(plain('MARY'))
    ('MARY', None)
    """
    match = cue_re.match(str(character))
    assert match
    name, extension = match.groups()
    return name, extension


def strip_continuation(cue: str) -> str:
    """Removes screenplay continuation markers like (CONT'D) from a cue.

    >>> strip_continuation("MARY (CONT'D)")
    'MARY'
    >>> strip_continuation("Mary (aside) (cont\u2019d)")
    'Mary (aside)'
    >>> strip_continuation("MARY (O.S., CONTINUED)")
    'MARY (O.S.)'
    >>> strip_continuation("MARY (CONTEMPTUOUS)")
    'MARY (CONTEMPTUOUS)'
    """

    def replace(match: re.Match[str]) -> str:
        items = [item.strip() for item in match.group(1).split(",")]
        kept = [item for item in items if not continuation_re.fullmatch(item)]
        if len(kept) == len(items):
            return match.group(0)
        return f" ({', '.join(kept)})" if kept else ""

    return cue_parenthetical_re.sub(replace, cue).strip()


def to_stageplay(screenplay: Screenplay) -> StagePlay:
    """Converts a parsed screenplay into a StagePlay."""
    paragraphs = list(screenplay)
    boundary = next(
        (i for i, para in enumerate(paragraphs) if isinstance(para, PageBreak)),
        None,
    )
    if boundary is None:
        front_paragraphs: list[SCREENPLAY_TYPES] = []
        body_paragraphs = paragraphs
    else:
        front_paragraphs = paragraphs[:boundary]
        body_paragraphs = paragraphs[boundary + 1 :]

    names = _collect_names(front_paragraphs, body_paragraphs)
    return StagePlay(
        screenplay.title_page,
        _front_matter(front_paragraphs, names),
        [_body_paragraph(para, names) for para in body_paragraphs],
    )


def _dialogs(paragraphs: Iterable[SCREENPLAY_TYPES]) -> Iterable[Dialog]:
    for para in paragraphs:
        if isinstance(para, Dialog):
            yield para
        elif isinstance(para, DualDialog):
            yield para.left
            yield para.right


def _collect_names(
    front: list[SCREENPLAY_TYPES], body: list[SCREENPLAY_TYPES]
) -> list[str]:
    """Collects known character names from dialogue cues and the cast list,
    longest first so that the longest match wins.
    """
    names = {split_cue(dialog.character)[0] for dialog in _dialogs(front + body)}
    in_cast_list = False
    for para in front:
        if isinstance(para, Section) and para.level == 1:
            in_cast_list = _is_cast_list_title(para.text)
        elif in_cast_list and isinstance(para, Action) and len(para.lines) == 1:
            names.add(str(para.lines[0]).strip())
    names.discard("")
    return sorted(names, key=len, reverse=True)


def _is_cast_list_title(title: RichString) -> bool:
    return str(title).strip().lower() in CAST_LIST_TITLES


def _front_matter(
    paragraphs: list[SCREENPLAY_TYPES], names: list[str]
) -> list[FrontMatterSection | CastList]:
    sections: list[FrontMatterSection | CastList] = []
    current: FrontMatterSection | CastList | None = None
    for para in paragraphs:
        if isinstance(para, Section) and para.level == 1:
            if _is_cast_list_title(para.text):
                current = CastList(para.text)
            else:
                current = FrontMatterSection(para.text)
            sections.append(current)
            continue
        if current is None:
            current = FrontMatterSection(None)
            sections.append(current)
        if isinstance(current, CastList):
            current.entries += _cast_entries(para, names)
        elif isinstance(para, Action) and not para.centered:
            current.paragraphs.append(_stage_direction(para, names))
        elif isinstance(para, (Dialog, DualDialog)):
            current.paragraphs.append(_without_continuation(para))
        else:
            current.paragraphs.append(para)
    return sections


def _cast_entries(
    para: SCREENPLAY_TYPES, names: list[str]
) -> list[CastMember | CastGroup | StageDirection]:
    if isinstance(para, Section):
        return [CastGroup(para.text)]
    if isinstance(para, Action) and len(para.lines) == 1:
        return [CastMember(_strip(para.lines[0]))]
    dialogs = list(_dialogs([para]))
    if dialogs:
        return [
            CastMember(dialog.character, [text for _, text in dialog.blocks])
            for dialog in dialogs
        ]
    if isinstance(para, Action):
        return [_stage_direction(para, names)]
    if isinstance(para, (Slug, Transition)):
        # These have no meaning in a cast list; keep their text as prose.
        return [_stage_direction(Action(para.lines), names)]
    return []


def _without_continuation(para: Dialog | DualDialog) -> Dialog | DualDialog:
    """Removes continuation markers from the cues of a dialogue paragraph."""
    if isinstance(para, DualDialog):
        return DualDialog(_strip_cue(para.left), _strip_cue(para.right))
    return _strip_cue(para)


def _strip_cue(dialog: Dialog) -> Dialog:
    cue = str(dialog.character)
    stripped = strip_continuation(cue)
    if stripped == cue:
        return dialog
    result = Dialog(plain(stripped))
    result.blocks = dialog.blocks
    return result


def _body_paragraph(para: SCREENPLAY_TYPES, names: list[str]) -> STAGEPLAY_TYPES:
    if isinstance(para, Section):
        return Act(para.text) if para.level == 1 else Scene(para.text)
    if isinstance(para, Slug):
        return Scene(para.line)
    if isinstance(para, Action) and not para.centered:
        return _stage_direction(para, names)
    if isinstance(para, (Dialog, DualDialog)):
        return _without_continuation(para)
    return para


def _stage_direction(action: Action, names: list[str]) -> StageDirection:
    return StageDirection([split_names(line, names) for line in action.lines])


def _strip(text: RichString) -> RichString:
    """Strips leading and trailing whitespace from a RichString."""
    segments = list(text.segments)
    if segments:
        first = segments[0]
        segments[0] = Segment(first.text.lstrip(), first.styles)
        last = segments[-1]
        segments[-1] = Segment(last.text.rstrip(), last.styles)
    return RichString(*(s for s in segments if s.text))


def split_names(line: RichString, names: list[str]) -> list[RichString | CharacterName]:
    """Splits a line into text and `@`-prefixed character names.

    `names` must be sorted longest first. A name after `@` matches the
    longest known name (case-insensitive), falling back to a single word.

    >>> from screenplain.richstring import plain
    >>> split_names(plain('@Mrs. Danvers greets @Max.'), ['Mrs. Danvers'])
    ... # doctest: +NORMALIZE_WHITESPACE
    [CharacterName(name=(plain)('Mrs. Danvers')), (plain)(' greets '),
     CharacterName(name=(plain)('Max')), (plain)('.')]
    """
    parts: list[RichString | CharacterName] = []
    pending: list[Segment] = []

    def flush() -> None:
        if pending:
            parts.append(RichString(*pending))
            pending.clear()

    for segment in line.segments:
        text = segment.text
        pos = 0
        for match in inline_name_start_re.finditer(text):
            start = match.end()
            if start < pos:
                continue
            length = _match_name(text, start, names)
            if not length:
                continue
            if match.start() > pos:
                pending.append(Segment(text[pos : match.start()], segment.styles))
            flush()
            name = text[start : start + length]
            parts.append(CharacterName(RichString(Segment(name, segment.styles))))
            pos = start + length
        if pos < len(text):
            pending.append(Segment(text[pos:], segment.styles))
    flush()
    return parts


def _match_name(text: str, start: int, names: list[str]) -> int:
    """Returns the length of the character name starting at `start`, or 0."""
    lowered = text.lower()
    for name in names:
        end = start + len(name)
        if lowered.startswith(name.lower(), start) and not (
            end < len(text) and text[end].isalnum()
        ):
            return len(name)
    match = fallback_name_re.match(text, start)
    return len(match.group(0)) if match else 0
