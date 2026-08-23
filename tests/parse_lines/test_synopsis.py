import pytest

from screenplain.parsers.fountain import parse_lines
from screenplain.types import Action, Section, Slug


def lines(source: str) -> list[str]:
    return source.split("\n")


# --- append_synopsis: a lone "=" paragraph following a Slug/Section ---

SLUG_THEN_SYNOPSIS_SOURCE = """\
INT. HOUSE - DAY

=A tense confrontation
"""


def test_synopsis_paragraph_after_slug_sets_slug_synopsis() -> None:
    # Given a slug followed, in its own paragraph, by a "=" synopsis line
    # When the source is parsed
    screenplay = parse_lines(lines(SLUG_THEN_SYNOPSIS_SOURCE))

    # Then the synopsis is attached to the slug rather than becoming its
    # own paragraph
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Slug)
    assert "A tense confrontation" == paras[0].synopsis


SECTION_THEN_SYNOPSIS_SOURCE = """\
# Act One

=The beginning
"""


def test_synopsis_paragraph_after_section_sets_section_synopsis() -> None:
    # Given a section heading followed, in its own paragraph, by a "="
    # synopsis line
    # When the source is parsed
    screenplay = parse_lines(lines(SECTION_THEN_SYNOPSIS_SOURCE))

    # Then the synopsis is attached to the section rather than becoming its
    # own paragraph
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Section)
    assert "The beginning" == paras[0].synopsis


SYNOPSIS_WITH_LEADING_WHITESPACE_SOURCE = """\
INT. HOUSE - DAY

=   padded synopsis
"""


def test_synopsis_paragraph_strips_leading_whitespace() -> None:
    # Given a synopsis line with extra whitespace between "=" and the text
    # When the source is parsed
    screenplay = parse_lines(lines(SYNOPSIS_WITH_LEADING_WHITESPACE_SOURCE))

    # Then the leading whitespace is stripped from the stored synopsis
    paras = screenplay.paragraphs
    assert isinstance(paras[0], Slug)
    assert "padded synopsis" == paras[0].synopsis


ORPHAN_SYNOPSIS_SOURCE = """\
Some action line.

=A synopsis-like line
"""


def test_synopsis_paragraph_without_preceding_slug_or_section_is_an_action() -> None:
    # Given a "=" paragraph that does not follow a slug or section
    # When the source is parsed
    screenplay = parse_lines(lines(ORPHAN_SYNOPSIS_SOURCE))

    # Then it is not treated as a synopsis and instead falls back to being
    # parsed as an action
    paras = screenplay.paragraphs
    assert [Action, Action] == [type(p) for p in paras]


SYNOPSIS_AS_FIRST_PARAGRAPH_SOURCE = """\
=Opening synopsis
"""


def test_synopsis_paragraph_as_first_paragraph_is_an_action() -> None:
    # Given a document that starts with a "=" paragraph, so there is no
    # preceding slug or section to attach to
    # When the source is parsed
    screenplay = parse_lines(lines(SYNOPSIS_AS_FIRST_PARAGRAPH_SOURCE))

    # Then it falls back to being parsed as an action
    paras = screenplay.paragraphs
    assert [Action] == [type(p) for p in paras]


SYNOPSIS_MULTILINE_SOURCE = """\
INT. HOUSE - DAY

=First line
Second line
"""


def test_multiline_paragraph_starting_with_equals_is_not_a_synopsis() -> None:
    # Given a multi-line paragraph whose first line looks like a synopsis
    # marker
    # When the source is parsed
    screenplay = parse_lines(lines(SYNOPSIS_MULTILINE_SOURCE))

    # Then append_synopsis only ever applies to single-line paragraphs, so
    # this falls back to being parsed as an action
    paras = screenplay.paragraphs
    assert 2 == len(paras)
    assert isinstance(paras[0], Slug)
    assert isinstance(paras[1], Action)
    assert 2 == len(paras[1].lines)


# --- append_sections_and_synopsises: sections/synopses sharing a paragraph ---


def test_lone_section_heading_has_no_synopsis() -> None:
    # Given a section heading with no synopsis line
    # When the source is parsed
    screenplay = parse_lines(lines("# Act One"))

    # Then a Section paragraph is created with synopsis left unset
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Section)
    assert 1 == paras[0].level
    assert paras[0].synopsis is None


SECTION_AND_SYNOPSIS_SAME_BLOCK_SOURCE = """\
# Act One
=The beginning
"""


def test_section_and_synopsis_sharing_a_paragraph_sets_synopsis() -> None:
    # Given a section heading immediately followed by a "=" synopsis line,
    # with no blank line separating them
    # When the source is parsed
    screenplay = parse_lines(lines(SECTION_AND_SYNOPSIS_SAME_BLOCK_SOURCE))

    # Then the synopsis is attached to that section
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Section)
    assert "Act One" == str(paras[0].text)
    assert "The beginning" == paras[0].synopsis


NESTED_SECTIONS_WITH_SYNOPSES_SOURCE = """\
# Act One
=Act synopsis
## Scene One
=Scene synopsis
"""


def test_nested_sections_each_get_their_own_synopsis() -> None:
    # Given two section headings of different levels, each immediately
    # followed by its own synopsis line, all in one paragraph block
    # When the source is parsed
    screenplay = parse_lines(lines(NESTED_SECTIONS_WITH_SYNOPSES_SOURCE))

    # Then two Section paragraphs are produced, each with the synopsis
    # belonging to it and not the other
    paras = screenplay.paragraphs
    assert 2 == len(paras)
    assert isinstance(paras[0], Section)
    assert 1 == paras[0].level
    assert "Act synopsis" == paras[0].synopsis
    assert isinstance(paras[1], Section)
    assert 2 == paras[1].level
    assert "Scene synopsis" == paras[1].synopsis


MULTIPLE_SECTIONS_NO_SYNOPSIS_SOURCE = """\
# Act One
## Scene One
"""


def test_multiple_section_headings_without_synopsis_lines() -> None:
    # Given two section headings in the same paragraph block, with no "="
    # synopsis lines at all
    # When the source is parsed
    screenplay = parse_lines(lines(MULTIPLE_SECTIONS_NO_SYNOPSIS_SOURCE))

    # Then both are parsed as separate Section paragraphs with no synopsis
    paras = screenplay.paragraphs
    assert 2 == len(paras)
    assert isinstance(paras[0], Section)
    assert paras[0].synopsis is None
    assert isinstance(paras[1], Section)
    assert paras[1].synopsis is None


SYNOPSIS_BEFORE_ANY_SECTION_SOURCE = """\
=orphan synopsis
# Section
"""


def test_synopsis_line_before_any_section_in_the_block_is_not_a_synopsis() -> None:
    # Given a paragraph block where a "=" line appears before any section
    # heading has been created within that same block
    # When the source is parsed
    screenplay = parse_lines(lines(SYNOPSIS_BEFORE_ANY_SECTION_SOURCE))

    # Then append_sections_and_synopsises has nothing to attach the
    # synopsis to and bails out, so the whole block falls back to being
    # parsed as a single action
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Action)
    assert 2 == len(paras[0].lines)


SECTION_BLOCK_WITH_INVALID_LINE_SOURCE = """\
# Section
Some plain action text
= synopsis
"""


def test_strict_section_block_followed_by_action() -> None:
    # Given a paragraph block that starts out looking like a section, but
    # contains a line that is neither a section heading nor a synopsis line
    # When the source is parsed
    with pytest.raises(
        ValueError,
        match="Section needs to be followed by an empty line or synopsis: 'Some plain action text'",
    ):
        parse_lines(lines(SECTION_BLOCK_WITH_INVALID_LINE_SOURCE))


TOO_MANY_HASHES_SOURCE = """\
####### Too many
"""


def test_more_than_six_hashes_is_not_a_section_heading() -> None:
    # Given a heading-like line with more than the six "#" levels the
    # fountain spec supports
    # When the source is parsed
    with pytest.raises(ValueError) as exc_info:
        parse_lines(lines(TOO_MANY_HASHES_SOURCE))
    assert str(exc_info.value) == (
        "Section has too many '#' characters: '####### Too many'"
    )


SECTION_SYNOPSIS_LEADING_WHITESPACE_SOURCE = """\
# Section
=    padded synopsis
"""


def test_section_synopsis_strips_leading_whitespace() -> None:
    # Given a synopsis line within a section block that has extra
    # whitespace between "=" and the text
    # When the source is parsed
    screenplay = parse_lines(lines(SECTION_SYNOPSIS_LEADING_WHITESPACE_SOURCE))

    # Then the leading whitespace is stripped from the stored synopsis
    paras = screenplay.paragraphs
    assert 1 == len(paras)
    assert isinstance(paras[0], Section)
    assert "padded synopsis" == paras[0].synopsis
