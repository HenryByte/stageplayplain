"""The FSE tokeniser: splitting a note into keyword-led directives."""

import pytest

from screenplain.fse.tokens import (
    LeadingSeparator,
    NearMiss,
    RawDirective,
    is_fse_note,
    tokenise,
)


def one(text: str) -> RawDirective:
    (directive,) = tokenise(text)
    return directive


def test_keyword_subject_and_attributes() -> None:
    directive = one("FSE MOVE hamlet pos=1,2 facing=window")
    assert "MOVE" == directive.keyword
    assert "hamlet" == directive.subject
    assert (("pos", "1,2"), ("facing", "window")) == directive.attributes
    assert "MOVE hamlet pos=1,2 facing=window" == directive.text


def test_subject_is_optional() -> None:
    directive = one("FSE MOVE pos=1,2")
    assert directive.subject is None
    assert (("pos", "1,2"),) == directive.attributes


def test_keyword_alone() -> None:
    directive = one("FSE ARRIVE")
    assert (None, ()) == (directive.subject, directive.attributes)


def test_compound_directives() -> None:
    directives = tokenise("FSE MOVE hamlet pos=window ;MOVE horatio pos=0,0")
    assert ["MOVE hamlet pos=window", "MOVE horatio pos=0,0"] == [
        d.text for d in directives
    ]


def test_trailing_separator_is_ignored() -> None:
    assert 1 == len(tokenise("FSE STRIKE all ; "))


def test_line_breaks_are_whitespace() -> None:
    directives = tokenise(
        "\n  FSE\nSTRIKE all;\n      PRESET throne pos=0,4;\n  PRESET x\n"
    )
    assert ["STRIKE", "PRESET", "PRESET"] == [d.keyword for d in directives]
    assert [2, 3, 4] == [d.line_offset for d in directives]


def test_value_after_first_equals() -> None:
    assert (("label", "a=b"),) == one("FSE ENTITY x label=a=b").attributes


def test_quoted_values_and_escapes() -> None:
    directive = one(r'FSE ENTITY x label="say \"hi\"; a\\b \n"')
    assert (("label", 'say "hi"; a\\b \\n'),) == directive.attributes


def test_empty_quoted_value() -> None:
    assert (("label", ""),) == one('FSE ENTITY x label=""').attributes


def test_quoted_subject() -> None:
    assert "Hamlet the Dane" == one('FSE MOVE "Hamlet the Dane" pos=1,2').subject


def test_keys_and_values_keep_their_case() -> None:
    assert (("Pos", "Window"),) == one("FSE MOVE x Pos=Window").attributes


@pytest.mark.parametrize(
    "text",
    [
        "FSE move hamlet pos=1,2",  # lowercase keyword
        "FSE WALK hamlet pos=1,2",  # unknown keyword
        'FSE ENTITY x label="open',  # unterminated quote
        'FSE ENTITY x label="a\nb"',  # line break in a quoted value
        "FSE MOVE hamlet 1,2",  # a second token without =
        "FSE MOVE pos=1,2 hamlet",  # a subject after an attribute
        "FSE MOVE hamlet pos=",  # empty value
        "FSE MOVE hamlet =1,2",  # empty key
        "FSE MOVE hamlet pos=[1",  # [ in a value
        'FSE ENTITY x label="a]"',  # ] in a quoted value
        "FSE MOVE x pos=1;; ARRIVE x",  # empty directive
        'FSE MOVE x pos="1"2',  # text straight after a quoted value
        'FSE MOVE x pos=1"2"',  # a quote inside a bare value
        "FSE ",  # no directive
    ],
)
def test_near_misses(text: str) -> None:
    with pytest.raises(NearMiss):
        tokenise(text)


def test_leading_separator() -> None:
    with pytest.raises(LeadingSeparator):
        tokenise("FSE ; MOVE hamlet pos=1,2")


def test_marker() -> None:
    assert is_fse_note("FSE MOVE x pos=1,2")
    assert is_fse_note("\n\t FSE\nMOVE x pos=1,2")
    assert not is_fse_note("fse MOVE x pos=1,2")
    assert not is_fse_note("MOVE this scene earlier?")
    assert not is_fse_note("FSEMOVE x")
    assert not is_fse_note("FSE")
