from screenplain.parsers.fountain import parse_lines
from screenplain.richstring import plain
from screenplain.types import Dialog


def lines(source: str) -> list[str]:
    return source.split("\n")


LOTS_EMPTY_LINES = """\
JULIET
Wherefore art thou Romeo?



"""


def test_multiple_empty_lines_at_end() -> None:
    # Given a character name followed by a parenthetical extension, e.g. (O.S.)
    # When the source is parsed
    screenplay = parse_lines(lines(LOTS_EMPTY_LINES))

    # Then the whole line, including the extension, becomes the character name
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Dialog)
    assert plain("JULIET") == paras[0].character
