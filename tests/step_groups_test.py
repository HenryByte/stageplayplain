"""Step groups and picture changes: which moments earn a margin plan."""

import io
from pathlib import Path

from screenplain import fse
from screenplain.fse.groups import has_text_between, top_of_scene
from screenplain.fse.model import Cue
from screenplain.parsers import fountain

HERE = Path(__file__).parent

DECLARATIONS = (
    "[[FSE STAGE type=proscenium width=10 depth=8]]\n"
    "[[FSE ENTITY door type=entrance pos=5,0]]\n"
    "[[FSE ENTITY hamlet type=cast]]\n"
    "[[FSE ENTITY horatio type=cast]]\n"
    "[[FSE ENTITY skull type=prop]]\n\n"
    "INT. HALL\n\n"
    "[[FSE PRESET hamlet pos=0,0; PRESET horatio pos=0,0.5; PRESET skull pos=0,0]]\n\n"
    "Hamlet waits.\n\n"
)


def process(source: str) -> fse.Blocking:
    return fse.process(fountain.parse(io.StringIO(source)))


def groups(source: str) -> list[list[str]]:
    """Each group's directives."""
    blocking = process(DECLARATIONS + source)
    return [
        [d.text for step in group.steps for d in step.directives]
        for group in fse.step_groups(blocking)
    ]


# Picture changes


def test_moves_enters_and_exits_are_picture_changes() -> None:
    assert [["MOVE hamlet pos=1,1"], ["EXIT horatio via=door"]] == groups(
        "[[FSE MOVE hamlet pos=1,1]]\n\nHe crosses.\n\n"
        "[[FSE EXIT horatio via=door]]\n\nHe goes.\n"
    )


def test_a_turn_in_place_is_a_picture_change() -> None:
    assert [["SET hamlet facing=90"]] == groups(
        "[[FSE SET hamlet facing=90]]\n\nHe turns.\n"
    )


def test_setting_the_facing_it_has_is_not_a_picture_change() -> None:
    assert [["SET hamlet facing=90"]] == groups(
        "[[FSE SET hamlet facing=90]]\n\nHe turns.\n\n"
        "[[FSE SET hamlet facing=90]]\n\nHe stays turned.\n"
    )


def test_facing_someone_who_moves_is_not_a_picture_change() -> None:
    blocking = process(
        DECLARATIONS + "[[FSE SET hamlet facing=horatio]]\n\nHe turns.\n\n"
        "[[FSE MOVE horatio pos=3,3]]\n\nHoratio crosses.\n"
    )
    _, cross = fse.step_groups(blocking)
    assert {"horatio"} == fse.picture_changes(blocking, cross.before, cross.after)


def test_a_move_to_where_it_stands_is_not_a_picture_change() -> None:
    assert [] == groups("[[FSE MOVE hamlet pos=0,0]]\n\nHe stays.\n")


def test_picking_up_and_putting_down_are_picture_changes() -> None:
    assert [["SET skull with=hamlet"], ["SET skull pos=0,0"]] == groups(
        "[[FSE SET skull with=hamlet]]\n\nHe holds it.\n\n"
        "[[FSE SET skull pos=0,0]]\n\nHe puts it down.\n"
    )


def test_a_hand_over_in_place_is_not_a_picture_change() -> None:
    source = (
        "[[FSE MOVE horatio pos=0,0]]\n\nHoratio joins him.\n\n"
        "[[FSE SET skull with=hamlet]]\n\nHe holds it.\n\n"
        "[[FSE SET skull with=horatio]]\n\nHe hands it over.\n"
    )
    assert ["SET skull with=horatio"] not in groups(source)


def test_every_event_of_an_open_move_is_a_picture_change() -> None:
    assert [
        ["MOVE hamlet pos=4,0 until=arrive"],
        ["VIA hamlet pos=2,2"],
        ["ARRIVE hamlet"],
    ] == groups(
        "[[FSE MOVE hamlet pos=4,0 until=arrive]]\n\nHe sets off.\n\n"
        "[[FSE VIA hamlet pos=2,2]]\n\nOn he goes.\n\n"
        "[[FSE ARRIVE hamlet]]\n\nHe is there.\n"
    )


def test_offstage_changes_are_not_picture_changes() -> None:
    # Handing the struck skull to Horatio in the wings shows on no plan.
    assert [["EXIT horatio via=door"], ["STRIKE skull"]] == groups(
        "[[FSE EXIT horatio via=door]]\n\nHe goes.\n\n"
        "[[FSE STRIKE skull]]\n\nIt goes.\n\n"
        "[[FSE SET skull with=horatio]]\n\nOff, he takes it.\n\n"
        "[[FSE SET horatio facing=90]]\n\nOff, he turns.\n"
    )


# Grouping


def test_stacked_and_adjacent_notes_are_one_group() -> None:
    assert [["MOVE hamlet pos=1,1", "MOVE horatio pos=2,2", "SET skull pos=3,3"]] == (
        groups(
            "[[FSE MOVE hamlet pos=1,1]]\n[[FSE MOVE horatio pos=2,2]]\n\n"
            "[[FSE SET skull pos=3,3]]\n\nThey move.\n"
        )
    )


def test_anything_between_notes_separates_groups() -> None:
    assert [["MOVE hamlet pos=1,1"], ["MOVE horatio pos=2,2"]] == groups(
        "Hamlet moves. [[FSE MOVE hamlet pos=1,1]] Then [[FSE MOVE horatio pos=2,2]]\n"
    )


def test_inline_notes_with_only_space_between_are_one_group() -> None:
    assert [["MOVE hamlet pos=1,1", "MOVE horatio pos=2,2"]] == groups(
        "Hamlet moves. [[FSE MOVE hamlet pos=1,1]] [[FSE MOVE horatio pos=2,2]]\n"
    )


def test_a_note_at_the_end_of_a_line_groups_with_a_standalone_note_after() -> None:
    assert [["MOVE hamlet pos=1,1", "MOVE horatio pos=2,2"]] == groups(
        "Hamlet moves. [[FSE MOVE hamlet pos=1,1]]\n\n"
        "[[FSE MOVE horatio pos=2,2]]\n\nThey stop.\n"
    )


def test_a_character_cue_separates_groups() -> None:
    assert [["MOVE hamlet pos=1,1"], ["MOVE pos=2,2"]] == groups(
        "[[FSE MOVE hamlet pos=1,1]]\n\nHAMLET\n[[FSE MOVE pos=2,2]] To be.\n"
    )


def test_has_text_between() -> None:
    blocking = process(
        DECLARATIONS + "Hamlet waits. [[FSE MOVE hamlet pos=1,1]] Then  waits.\n"
    )
    paragraphs = blocking.screenplay.paragraphs
    action = len(paragraphs) - 1
    assert has_text_between(paragraphs, Cue(action, 0, 0, 0), Cue(action, 0, 0, 14))
    assert not has_text_between(
        paragraphs, Cue(action, 0, 0, 14), Cue(action, 0, 0, 15)
    )
    assert has_text_between(paragraphs, Cue(action, 0, 0, 14), Cue(action, 0, 0, 20))


# Scenes


def test_top_of_scene_steps_get_no_margin_plan() -> None:
    blocking = process(DECLARATIONS + "[[FSE MOVE hamlet pos=1,1]]\n\nHe moves.\n")
    scene = blocking.scenes[0]
    assert 1 == top_of_scene(scene)
    (group,) = fse.step_groups(blocking)
    assert scene.steps[1] is group.steps[0]
    assert group.before is scene.preset


def test_hamlet_groups() -> None:
    blocking = process((HERE / "fse" / "hamlet.fountain").read_text())
    assert [
        ["ENTER hamlet from=vom-b pos=3,1", "ENTER horatio from=vom-b pos=3.5,2",
         "SET lantern with=horatio"],
        ["SET skull pos=graveside by=first-gravedigger"],
        ["MOVE pos=graveside facing=grave"],
        ["SET skull with=hamlet"],
        ["SET skull pos=grave by=hamlet", "EXIT hamlet via=vom-c",
         "EXIT horatio via=vom-c"],
        ["ENTER hamlet from=vom-a pos=0,-2", "ENTER horatio from=vom-a pos=1,-3"],
    ] == [
        [d.text for step in group.steps for d in step.directives]
        for group in fse.step_groups(blocking)
    ]  # fmt: skip
    scenes = [blocking.scenes.index(group.scene) for group in fse.step_groups(blocking)]
    assert [0, 0, 0, 0, 0, 1] == scenes
