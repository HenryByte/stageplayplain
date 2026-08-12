from screenplain.parsers.fountain import parse_lines
from screenplain.richstring import plain
from screenplain.types import Action, Dialog, Slug


def lines(source: str) -> list[str]:
    return source.split("\n")


ACTION_SOURCE = """\
INT. SOMEWHERE - DAY

John walks across the room and opens the door.
"""


def test_action_without_leading_bang() -> None:
    # Given a plain action line with no leading "!"
    # When the source is parsed
    screenplay = parse_lines(lines(ACTION_SOURCE))

    # Then it is parsed as a regular, un-centered action
    paras = screenplay.paragraphs
    assert 2 == len(paras)
    assert isinstance(paras[0], Slug)
    assert isinstance(paras[1], Action)
    assert not paras[1].centered
    assert [plain("John walks across the room and opens the door.")] == paras[1].lines


FORCED_ACTION_SOURCE = """\
INT. SOMEWHERE - DAY

!John walks across the room and opens the door.
"""


def test_action_with_leading_bang_strips_the_bang() -> None:
    # Given an action line with a leading "!"
    # When the source is parsed
    screenplay = parse_lines(lines(FORCED_ACTION_SOURCE))

    # Then the "!" is stripped from the resulting action text
    paras = screenplay.paragraphs
    assert 2 == len(paras)
    assert isinstance(paras[0], Slug)
    assert isinstance(paras[1], Action)
    assert not paras[1].centered
    assert [plain("John walks across the room and opens the door.")] == paras[1].lines


FORCED_ACTION_OVERRIDES_SLUG_SOURCE = """\
Once upon a time.

!int. house - day
"""


def test_leading_bang_forces_action_even_when_it_looks_like_a_slug() -> None:
    # Given a slug-like line marked with a leading "!"
    # When the source is parsed
    screenplay = parse_lines(lines(FORCED_ACTION_OVERRIDES_SLUG_SOURCE))

    # Then it is parsed as an untouched action instead of a slug
    paras = screenplay.paragraphs
    assert 2 == len(paras)
    assert isinstance(paras[0], Action)
    assert isinstance(paras[1], Action)
    assert not paras[1].centered
    assert [plain("int. house - day")] == paras[1].lines


FORCED_ACTION_MULTILINE_SOURCE = """\
INT. SOMEWHERE - DAY

!She smiles.
He smiles back.
"""


def test_leading_bang_only_stripped_from_lines_that_have_it() -> None:
    # Given a multi-line action where only the first line has a leading "!"
    # When the source is parsed
    screenplay = parse_lines(lines(FORCED_ACTION_MULTILINE_SOURCE))

    # Then the "!" is stripped only from the line that has it
    paras = screenplay.paragraphs
    assert 2 == len(paras)
    assert isinstance(paras[0], Slug)
    assert isinstance(paras[1], Action)
    assert [plain("She smiles."), plain("He smiles back.")] == paras[1].lines


CENTERED_ACTION_SOURCE = """\
INT. SOMEWHERE - DAY

> THE END <
"""


def test_single_line_centered_action() -> None:
    # Given a single action line wrapped in "> ... <"
    # When the source is parsed
    screenplay = parse_lines(lines(CENTERED_ACTION_SOURCE))

    # Then it is parsed as a centered action with the markers removed
    paras = screenplay.paragraphs
    assert 2 == len(paras)
    assert isinstance(paras[0], Slug)
    assert isinstance(paras[1], Action)
    assert paras[1].centered
    assert [plain("THE END")] == paras[1].lines


CENTERED_ACTION_MULTILINE_SOURCE = """\
INT. SOMEWHERE - DAY

> Scene One <
> The Beginning <
"""


def test_multi_line_centered_action() -> None:
    # Given several action lines, each wrapped in "> ... <"
    # When the source is parsed
    screenplay = parse_lines(lines(CENTERED_ACTION_MULTILINE_SOURCE))

    # Then it is parsed as a single centered action with the markers removed
    paras = screenplay.paragraphs
    assert 2 == len(paras)
    assert isinstance(paras[0], Slug)
    assert isinstance(paras[1], Action)
    assert paras[1].centered
    assert [plain("Scene One"), plain("The Beginning")] == paras[1].lines


MIXED_CENTERED_AND_PLAIN_SOURCE = """\
INT. SOMEWHERE - DAY

> Centered line <
Not a centered line
"""


# This seems odd, but it is how it currently works
def test_paragraph_is_only_centered_when_every_line_matches() -> None:
    # Given a paragraph mixing a centered line with a non-centered line
    # When the source is parsed
    screenplay = parse_lines(lines(MIXED_CENTERED_AND_PLAIN_SOURCE))

    # Then it falls back to a regular, un-centered, untouched action
    paras = screenplay.paragraphs
    assert 2 == len(paras)
    assert isinstance(paras[0], Slug)
    assert isinstance(paras[1], Action)
    assert not paras[1].centered
    assert [
        plain("> Centered line <"),
        plain("Not a centered line"),
    ] == paras[1].lines


SLUG_WITHOUT_BLANK_LINE_SOURCE = """\
INT. SOMEWHERE - DAY
!John walks across the room and opens the door.
"""


def test_slug_without_blank_line_before_action_is_not_parsed_as_action() -> None:
    # Given a slug line directly followed by a forced action line
    # When the source is parsed
    screenplay = parse_lines(lines(SLUG_WITHOUT_BLANK_LINE_SOURCE))

    # Then the lines are merged into one paragraph and parsed as Dialog
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert not isinstance(paras[0], Action)
    assert isinstance(paras[0], Dialog)
