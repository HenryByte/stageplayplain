"""Fountain notes carried inside the Screenplay: standalone `Note`
paragraphs, inline notes on their element, and title page notes.
"""

from io import StringIO

import pytest

from screenplain.parsers import fountain
from screenplain.richstring import bold, empty_string, plain
from screenplain.stageplay import to_stageplay
from screenplain.types import (
    SCREENPLAY_TYPES,
    Action,
    Dialog,
    DualDialog,
    FrontMatterSection,
    InlineNote,
    Note,
    PageBreak,
    Screenplay,
    Section,
    Slug,
    StageDirection,
    Transition,
)


def parse_screenplay(source: str) -> Screenplay:
    return fountain.parse(StringIO(source))


def parse(source: str) -> list[SCREENPLAY_TYPES]:
    return parse_screenplay(source).paragraphs


def only(source: str) -> SCREENPLAY_TYPES:
    (para,) = parse(source)
    return para


def action_notes(source: str) -> list[InlineNote]:
    para = only(source)
    assert isinstance(para, Action)
    return para.notes


# Standalone notes


def test_standalone_note_is_a_note_paragraph() -> None:
    paras = parse("Before\n\n[[a note]]\n\nAfter")
    assert [Action, Note, Action] == [type(para) for para in paras]
    assert Note("a note", 3) == paras[1]


def test_stacked_note_lines_give_one_note_each_and_no_action() -> None:
    assert [Note("a", 1), Note("b", 2)] == parse("[[a]]\n[[b]]")


def test_two_notes_on_one_line_give_one_note_each_in_order() -> None:
    assert [Note("a", 1), Note("b", 1)] == parse("[[a]] [[b]]")


def test_equal_notes_are_not_merged() -> None:
    assert [Note("a", 1), Note("a", 2)] == parse("[[a]]\n[[a]]")


def test_multiline_standalone_note_is_on_its_first_line() -> None:
    assert [Note("one\ntwo", 3)] == parse("\n\n[[one\ntwo]]")


def test_standalone_note_with_trailing_spaces() -> None:
    assert [Note("a", 1)] == parse("[[a]]  ")


def test_line_numbers_count_lines_removed_with_boneyard() -> None:
    paras = parse("/* one\ntwo\nthree */\n\n[[a]]\n\nX /* y\n */[[b]]")
    assert Note("a", 5) == paras[0]
    action = paras[1]
    assert isinstance(action, Action)
    # Boneyard joins lines 7 and 8 into one; a note on it gets line 7.
    assert [InlineNote("b", 7, 0, 1)] == action.notes


def test_line_numbers_after_title_page() -> None:
    screenplay = parse_screenplay("Title: T\n\n[[a]]")
    assert [Note("a", 3)] == screenplay.paragraphs


# Inline notes in action


def test_inline_note_does_not_change_the_text() -> None:
    para = only("Yorick! [[x]] I knew him.")
    assert isinstance(para, Action)
    assert [plain("Yorick!  I knew him.")] == para.lines


@pytest.mark.parametrize(
    ("source", "offset"),
    [
        ("[[x]]Hello there", 0),
        ("Hello there[[x]]", 11),
        ("Hello [[x]]there", 6),
        ("Are you fa[[x]]ir?", 10),
        ("Hello there [[x]]", 11),
        ("**fa[[x]]ir**", 2),
        ("**fair**[[x]] lady", 4),
        ("*a* _b_ [[x]]c", 4),
        ("\\*a[[x]]", 2),
        ("    Indented [[x]]text", 13),
    ],
)
def test_action_offset(source: str, offset: int) -> None:
    assert [InlineNote("x", 1, 0, offset)] == action_notes(source)


def test_action_part_is_the_line_index() -> None:
    notes = action_notes("One\nTwo [[a]]and [[b]]three\nFour[[c]]")
    assert [
        InlineNote("a", 2, 1, 4),
        InlineNote("b", 2, 1, 8),
        InlineNote("c", 3, 2, 4),
    ] == notes


def test_multiline_inline_note_is_on_its_first_line() -> None:
    para = only("Before [[a\nmultiline\nnote]]After\nNext")
    assert isinstance(para, Action)
    assert [plain("Before After"), plain("Next")] == para.lines
    assert [InlineNote("a\nmultiline\nnote", 1, 0, 7)] == para.notes


def test_forced_action() -> None:
    para = only("![[x]]SHOUTING [[y]]TEXT")
    assert isinstance(para, Action)
    assert [plain("SHOUTING TEXT")] == para.lines
    assert [InlineNote("x", 1, 0, 0), InlineNote("y", 1, 0, 9)] == para.notes


def test_forced_action_on_a_later_line() -> None:
    notes = action_notes("Text\n!FO[[x]]RCED")
    assert [InlineNote("x", 2, 1, 2)] == notes


def test_centered_action() -> None:
    para = only("> THE[[x]] END <\n>  [[y]]Credits<")
    assert isinstance(para, Action)
    assert para.centered
    assert [plain("THE END"), plain("Credits")] == para.lines
    assert [InlineNote("x", 1, 0, 3), InlineNote("y", 2, 1, 0)] == para.notes


# Inline notes in dialogue


def test_dialogue_blocks() -> None:
    para = only("HAMLET\n  (aside[[a]])\nTo be, or *not*[[b]] to be. [[c]]")
    assert isinstance(para, Dialog)
    assert [
        InlineNote("a", 2, 0, 6),
        InlineNote("b", 3, 1, 13),
        InlineNote("c", 3, 1, 20),
    ] == para.notes


def test_note_in_character_cue() -> None:
    para = only("HAMLET [[a]]\nWords.")
    assert isinstance(para, Dialog)
    assert plain("HAMLET") == para.character
    assert [InlineNote("a", 1, "character", 6)] == para.notes


def test_note_in_forced_character_cue() -> None:
    para = only("@Ham[[a]]let\nWords.")
    assert isinstance(para, Dialog)
    assert plain("Hamlet") == para.character
    assert [InlineNote("a", 1, "character", 3)] == para.notes


def test_glued_note_under_dialogue_keeps_the_dialogue() -> None:
    para = only("HAMLET\nWords.\n[[a]]")
    assert isinstance(para, Dialog)
    assert [(False, plain("Words.")), (False, empty_string)] == para.blocks
    assert [InlineNote("a", 3, 1, 0)] == para.notes


def test_dual_dialogue_notes_are_on_the_inner_dialogues() -> None:
    para = only("BRICK\nScr[[a]]ew\n\nSTEEL ^[[b]]\nYou[[c]].")
    assert isinstance(para, DualDialog)
    assert [InlineNote("a", 2, 0, 3)] == para.left.notes
    assert [InlineNote("b", 4, "character", 5), InlineNote("c", 5, 0, 3)] == (
        para.right.notes
    )


# Inline notes in other elements


def test_slug() -> None:
    para = only("int. hall[[a]] - day")
    assert isinstance(para, Slug)
    assert plain("INT. HALL - DAY") == para.line
    assert [InlineNote("a", 1, None, 9)] == para.notes


def test_forced_slug_with_scene_number() -> None:
    para = only(".  **cel[[a]]lar** #1# [[b]]")
    assert isinstance(para, Slug)
    assert bold("CELLAR") == para.line
    assert [InlineNote("a", 1, None, 3), InlineNote("b", 1, None, 6)] == para.notes


def test_section() -> None:
    para = only("## Act[[a]] One")
    assert isinstance(para, Section)
    assert [InlineNote("a", 1, None, 3)] == para.notes


def test_synopsis_in_section_paragraph() -> None:
    one, two = parse("# One\n= Synopsis [[a]]\n## Two [[b]]")
    assert isinstance(one, Section)
    assert isinstance(two, Section)
    assert "Synopsis " == one.synopsis
    assert [InlineNote("a", 2, "synopsis", None)] == one.notes
    assert [InlineNote("b", 3, None, 4)] == two.notes


def test_synopsis_paragraph_after_slug() -> None:
    para = only("INT. HALL\n\n= [[a]]Synopsis")
    assert isinstance(para, Slug)
    assert "Synopsis" == para.synopsis
    assert [InlineNote("a", 3, "synopsis", None)] == para.notes


@pytest.mark.parametrize(
    ("source", "text", "offset"),
    [
        ("CUT TO:[[a]]", "CUT TO:", 7),
        ("CUT[[a]] TO:", "CUT TO:", 3),
        ("> fade[[a]] out", "FADE OUT", 4),
    ],
)
def test_transition(source: str, text: str, offset: int) -> None:
    # Text first, so the transition is not read as a title page key.
    _, para = parse("Text\n\n" + source)
    assert isinstance(para, Transition)
    assert plain(text) == para.line
    assert [InlineNote("a", 3, None, offset)] == para.notes


def test_page_break() -> None:
    para = only("===[[a]]")
    assert isinstance(para, PageBreak)
    assert [InlineNote("a", 1, None, None)] == para.notes


def test_paragraphs_without_notes_have_empty_notes() -> None:
    paras = parse("INT. HALL\n\nAction.\n\nBOB\nHi.\n\nCUT TO:\n\n# S\n\n===")
    assert 6 == len(paras)
    for para in paras:
        assert not isinstance(para, (Note, DualDialog))
        assert [] == para.notes


# Title page


def test_note_only_title_page_line_parses() -> None:
    screenplay = parse_screenplay("Title: T\n[[a]] [[b]]\nAuthor: A\n\nText")
    assert {"Title": ["T"], "Author": ["A"]} == screenplay.title_page
    assert [Note("a", 2), Note("b", 2)] == screenplay.title_page_notes
    (para,) = screenplay.paragraphs
    assert isinstance(para, Action)
    assert [plain("Text")] == para.lines


def test_note_only_line_inside_title_page_value() -> None:
    screenplay = parse_screenplay("Contact:\n    a@b.c\n    [[a\nb]]\n    555\n")
    assert {"Contact": ["a@b.c", "555"]} == screenplay.title_page
    assert [Note("a\nb", 3)] == screenplay.title_page_notes


def test_note_only_last_title_page_line() -> None:
    screenplay = parse_screenplay("Title: T\n[[a]]\n\nText")
    assert {"Title": ["T"]} == screenplay.title_page
    assert [Note("a", 2)] == screenplay.title_page_notes
    assert 1 == len(screenplay.paragraphs)


def test_note_only_first_lines_are_not_a_title_page() -> None:
    screenplay = parse_screenplay("[[a]]\nTitle: T\n\nText")
    assert {} == screenplay.title_page
    assert [] == screenplay.title_page_notes


# Stage play


def test_stage_play_drops_standalone_notes() -> None:
    play = to_stageplay(parse_screenplay("# Notes\n\n[[a]]\n\n===\n\n[[b]]\n\nGo."))
    (section,) = play.front_matter
    assert isinstance(section, FrontMatterSection)
    assert [] == section.paragraphs
    assert [StageDirection([[plain("Go.")]])] == play.body
