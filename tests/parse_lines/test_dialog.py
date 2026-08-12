import pytest

from screenplain.parsers.fountain import parse_lines
from screenplain.richstring import empty_string, plain
from screenplain.types import Action, Dialog, DualDialog


def lines(source: str) -> list[str]:
    return source.split("\n")


ALL_CAPS_CHARACTER_SOURCE = """\
SOME GUY
Hello
"""


def test_all_caps_line_is_parsed_as_character() -> None:
    # Given a line entirely in caps followed by a line of dialogue
    # When the source is parsed
    screenplay = parse_lines(lines(ALL_CAPS_CHARACTER_SOURCE))

    # Then it is parsed as a single Dialog paragraph
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Dialog)
    assert plain("SOME GUY") == paras[0].character
    assert [(False, plain("Hello"))] == paras[0].blocks


ALPHANUMERIC_CHARACTER_SOURCE = """\
R2D2
Bee-bop
"""


def test_alphanumeric_character_is_parsed_as_character() -> None:
    # Given a character name that mixes letters and digits
    # When the source is parsed
    screenplay = parse_lines(lines(ALPHANUMERIC_CHARACTER_SOURCE))

    # Then it is parsed as dialogue
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Dialog)
    assert plain("R2D2") == paras[0].character


NUMERIC_ONLY_CHARACTER_SOURCE = """\
23
Hello
"""


def test_character_without_any_letters_is_not_dialog() -> None:
    # Given a "character" line with no alphabetical characters
    # When the source is parsed
    screenplay = parse_lines(lines(NUMERIC_ONLY_CHARACTER_SOURCE))

    # Then it falls back to being parsed as an action
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Action)


AT_SIGN_FORCED_CHARACTER_SOURCE = """\
@McCLANE
Yippee ki-yay
"""


def test_at_sign_forces_dialog_and_is_stripped() -> None:
    # Given a lower/mixed-case character name preceded by "@"
    # When the source is parsed
    screenplay = parse_lines(lines(AT_SIGN_FORCED_CHARACTER_SOURCE))

    # Then it is parsed as dialogue with the "@" removed from the name
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Dialog)
    assert plain("McCLANE") == paras[0].character


CHARACTER_WITH_EXTENSION_SOURCE = """\
JULIET (O.S.)
Wherefore art thou Romeo?
"""


def test_character_with_parenthetical_extension_is_parsed_as_character() -> None:
    # Given a character name followed by a parenthetical extension, e.g. (O.S.)
    # When the source is parsed
    screenplay = parse_lines(lines(CHARACTER_WITH_EXTENSION_SOURCE))

    # Then the whole line, including the extension, becomes the character name
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Dialog)
    assert plain("JULIET (O.S.)") == paras[0].character


TWO_TRAILING_SPACES_SOURCE = """\
SCANNING THE AISLES...
Where is that pit boss?
"""


def test_two_trailing_spaces_prevents_character() -> None:
    # Given an all-caps line ending in two trailing spaces
    # When the source is parsed
    screenplay = parse_lines(lines(TWO_TRAILING_SPACES_SOURCE))

    # Then it is not treated as a character cue, and falls back to action
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Action)


PARENTHETICAL_SOURCE = """\
STEEL
(starting the engine)
So much for retirement!
"""


def test_parenthetical_line_is_marked_in_blocks() -> None:
    # Given a dialogue block containing a parenthetical
    # When the source is parsed
    screenplay = parse_lines(lines(PARENTHETICAL_SOURCE))

    # Then the parenthetical line is flagged as such in the resulting blocks
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Dialog)
    assert [
        (True, plain("(starting the engine)")),
        (False, plain("So much for retirement!")),
    ] == paras[0].blocks


TWOSPACE_BLANK_LINE_SOURCE = "SOMEONE\nOne\n  \nTwo\n"


def test_double_space_line_keeps_dialogue_together_as_blank_block() -> None:
    # Given a dialogue block with a line of just two spaces in the middle
    # When the source is parsed
    screenplay = parse_lines(lines(TWOSPACE_BLANK_LINE_SOURCE))

    # Then the paragraph is not split, and the two-space line becomes an empty block
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Dialog)
    assert [
        (False, plain("One")),
        (False, empty_string),
        (False, plain("Two")),
    ] == paras[0].blocks


DUAL_DIALOG_SOURCE = """\
BRICK
Fuck retirement.

STEEL ^
Fuck retirement!
"""


def test_caret_after_character_creates_dual_dialog() -> None:
    # Given two dialogue blocks where the second character ends in "^"
    # When the source is parsed
    screenplay = parse_lines(lines(DUAL_DIALOG_SOURCE))

    # Then they are combined into a single DualDialog paragraph
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], DualDialog)
    dual = paras[0]
    assert plain("BRICK") == dual.left.character
    assert [(False, plain("Fuck retirement."))] == dual.left.blocks
    assert plain("STEEL") == dual.right.character
    assert [(False, plain("Fuck retirement!"))] == dual.right.blocks


DUAL_DIALOG_WITHOUT_PRECEDING_DIALOG_SOURCE = """\
Brick strolls down the street.

BRICK ^
Nice retirement.
"""


def test_caret_raises_without_a_preceding_dialog() -> None:
    # Given a "^" character cue with no dialogue paragraph directly before it
    # When the source is parsed
    with pytest.raises(
        ValueError, match="Dual dialog needs to follow dialog, it followed: type=Action"
    ):
        # Then an error is raised
        parse_lines(lines(DUAL_DIALOG_WITHOUT_PRECEDING_DIALOG_SOURCE))


DUAL_DIALOG_AT_START_OF_SCREENPLAY = """\
BRICK ^
Nice retirement.
"""


def test_caret_raises_at_start_of_screenplay() -> None:
    # Given a "^" character cue at the start of the screenplay
    # When the source is parsed
    with pytest.raises(
        ValueError, match="Cannot have a dual dialog at the start of the screenplay"
    ):
        # Then an error is raised
        parse_lines(lines(DUAL_DIALOG_AT_START_OF_SCREENPLAY))


LEADING_AND_TRAILING_SPACES_SOURCE = (
    "JULIET\n"
    "O Romeo, Romeo! wherefore art thou Romeo?\n"
    "  Deny thy father and refuse thy name;  \n"
    "Or, if thou wilt not, be but sworn my love,\n"
    " And I'll no longer be a Capulet.\n"
)


def test_leading_and_trailing_spaces_are_stripped_from_dialog_lines() -> None:
    # Given dialogue lines with stray leading and trailing whitespace
    # When the source is parsed
    screenplay = parse_lines(lines(LEADING_AND_TRAILING_SPACES_SOURCE))

    # Then every line of dialogue is stripped of leading and trailing whitespace
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Dialog)
    assert [
        (False, plain("O Romeo, Romeo! wherefore art thou Romeo?")),
        (False, plain("Deny thy father and refuse thy name;")),
        (False, plain("Or, if thou wilt not, be but sworn my love,")),
        (False, plain("And I'll no longer be a Capulet.")),
    ] == paras[0].blocks
