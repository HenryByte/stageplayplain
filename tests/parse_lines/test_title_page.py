import pytest

from screenplain.parsers.fountain import parse_lines
from screenplain.richstring import plain
from screenplain.types import Action, Screenplay, Slug

TITLE_PAGE_SOURCE = """\
Title: My Screenplay
Author: Your Name
Contact:
    your.email@example.com
    (555) 123-4567

FADE IN:

SPACE
"""


def lines(source: str) -> list[str]:
    return source.split("\n")


def test_title_page_keys_and_values() -> None:
    screenplay = parse_lines(lines(TITLE_PAGE_SOURCE))

    assert isinstance(screenplay, Screenplay)
    assert {
        "Title": ["My Screenplay"],
        "Author": ["Your Name"],
        "Contact": ["your.email@example.com", "(555) 123-4567"],
    } == screenplay.title_page

    paras = screenplay.paragraphs
    assert 2 == len(paras)
    assert isinstance(paras[0], Action)
    assert isinstance(paras[1], Action)
    assert [plain("FADE IN:")] == paras[0].lines
    assert [plain("SPACE")] == paras[1].lines


INVALID_TITLE_PAGE_SOURCE = """\
Title: My Screenplay
Author: Your Name
Contact:
    your.email@example.com
    (555) 123-4567
@ANDREW
Hi there
"""


def test_invalid_title_page_raises() -> None:
    with pytest.raises(ValueError, match="Invalid title page format on line '@ANDREW'"):
        _screenplay = parse_lines(lines(INVALID_TITLE_PAGE_SOURCE))


NO_TITLE_TEST = """\
INT. SOMEWHERE - DAY

Some action.
"""


def test_no_title_page() -> None:
    screenplay = parse_lines(lines(NO_TITLE_TEST))

    assert {} == screenplay.title_page
    paras = screenplay.paragraphs
    assert 2 == len(paras)
    assert isinstance(paras[0], Slug)
    assert isinstance(paras[1], Action)


def test_empty_source() -> None:
    screenplay = parse_lines([])

    assert {} == screenplay.title_page
    assert [] == screenplay.paragraphs
