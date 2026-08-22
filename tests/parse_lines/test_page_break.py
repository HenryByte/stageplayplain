from screenplain.parsers.fountain import parse_lines
from screenplain.types import Action, PageBreak, Slug


def lines(source: str) -> list[str]:
    return source.split("\n")


PAGE_BREAK_SOURCE = """\
INT. SOMEWHERE - DAY

===

John enters.
"""


def test_page_break_between_action_lines_is_parsed() -> None:
    # Given a page break surrounded by blank lines, between two actions
    # When the source is parsed
    screenplay = parse_lines(lines(PAGE_BREAK_SOURCE))

    # Then a PageBreak paragraph is inserted in the correct position
    paras = screenplay.paragraphs
    assert 3 == len(paras)
    assert isinstance(paras[0], Slug)
    assert isinstance(paras[1], PageBreak)
    assert isinstance(paras[2], Action)


PAGE_BREAK_ONLY_SOURCE = """\
===
"""


def test_document_consisting_of_only_a_page_break() -> None:
    # Given a source that is nothing but a page break
    # When the source is parsed
    screenplay = parse_lines(lines(PAGE_BREAK_ONLY_SOURCE))

    # Then the only paragraph is a PageBreak
    paras = screenplay.paragraphs
    assert [PageBreak] == [type(p) for p in paras]


PAGE_BREAK_MORE_THAN_THREE_EQUALS_SOURCE = """\
======
"""


def test_page_break_with_more_than_three_equals_signs_is_parsed() -> None:
    # Given a page break marker with more than three "=" characters
    # When the source is parsed
    screenplay = parse_lines(lines(PAGE_BREAK_MORE_THAN_THREE_EQUALS_SOURCE))

    # Then it is still parsed as a PageBreak
    paras = screenplay.paragraphs
    assert [PageBreak] == [type(p) for p in paras]


TWO_EQUALS_SIGNS_SOURCE = """\
==
"""


def test_two_equals_signs_is_not_a_page_break() -> None:
    # Given a line with only two "=" characters, one short of the minimum
    # When the source is parsed
    screenplay = parse_lines(lines(TWO_EQUALS_SIGNS_SOURCE))

    # Then it falls back to being parsed as an action
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Action)


PADDED_EQUALS_SIGNS_SOURCE = """\
 ===
"""


def test_page_break_marker_with_leading_whitespace_is_not_a_page_break() -> None:
    # Given a page break marker with leading whitespace
    # When the source is parsed
    screenplay = parse_lines(lines(PADDED_EQUALS_SIGNS_SOURCE))

    # Then it is not recognized as a page break and falls back to an action
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Action)


PAGE_BREAK_MIXED_WITH_OTHER_TEXT_SOURCE = """\
Some text
===
More text
"""


def test_page_break_marker_sharing_a_paragraph_with_other_lines_is_not_a_page_break() -> (
    None
):
    # Given a page break marker that is not isolated by blank lines, so it
    # ends up in a multi-line paragraph together with other text
    # When the source is parsed
    screenplay = parse_lines(lines(PAGE_BREAK_MIXED_WITH_OTHER_TEXT_SOURCE))

    # Then the whole paragraph, including the marker line, is parsed as a
    # single action rather than being split out into a PageBreak
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Action)
    assert 3 == len(paras[0].lines)


CONSECUTIVE_PAGE_BREAKS_SOURCE = """\
===

===
"""


def test_consecutive_page_breaks_are_each_parsed_separately() -> None:
    # Given two page breaks separated by a blank line
    # When the source is parsed
    screenplay = parse_lines(lines(CONSECUTIVE_PAGE_BREAKS_SOURCE))

    # Then two separate PageBreak paragraphs are produced
    paras = screenplay.paragraphs
    assert [PageBreak, PageBreak] == [type(p) for p in paras]
