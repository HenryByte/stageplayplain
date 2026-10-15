"""The Blocking: the Hamlet golden test (§9), the timeline, script
positions and interpolation in transit.
"""

from io import StringIO
from pathlib import Path

import pytest

from screenplain import fse
from screenplain.fse import Blocking, Step
from screenplain.fse.directives import Move, Set
from screenplain.fse.model import (
    OFFSTAGE,
    At,
    Cue,
    Moving,
    Place,
    Point,
    Toward,
    With,
)
from screenplain.parsers import fountain
from screenplain.types import Dialog

HAMLET = Path(__file__).parent / "fse" / "hamlet.fountain"


def process(source: str) -> Blocking:
    return fse.process(fountain.parse(StringIO(source)))


@pytest.fixture(scope="module")
def hamlet() -> Blocking:
    return process(HAMLET.read_text(encoding="utf-8"))


def step_with(blocking: Blocking, text: str) -> Step:
    """The step holding a directive with this text."""
    return next(
        step
        for step in blocking.timeline.steps
        if any(d.text == text for d in step.directives)
    )


# The Hamlet example (§9)


def test_hamlet_is_clean(hamlet: Blocking) -> None:
    assert [] == hamlet.reports
    assert hamlet.stage is not None
    assert ("round", 6.0, "vom-a") == (
        hamlet.stage.type,
        hamlet.stage.radius,
        hamlet.stage.front,
    )
    assert 2 == len(hamlet.scenes)


def test_hamlet_scene_change_one_to_two(hamlet: Blocking) -> None:
    changes = {change.entity: change for change in hamlet.scenes[1].change}
    assert {"first-gravedigger", "spade", "skull"} == set(changes)

    gravedigger = changes["first-gravedigger"]
    assert (At(Place("grave")), OFFSTAGE) == (gravedigger.before, gravedigger.after)
    assert (Toward(Place("vom-a")), None) == (
        gravedigger.facing_before,
        gravedigger.facing_after,
    )

    # The spade goes off with the gravedigger and is no longer his.
    spade = changes["spade"]
    assert (With("first-gravedigger"), OFFSTAGE) == (spade.before, spade.after)

    skull = changes["skull"]
    assert (At(Place("grave")), OFFSTAGE) == (skull.before, skull.after)


def test_hamlet_spade_set_offstage_comes_on_at_preset(hamlet: Blocking) -> None:
    initial = hamlet.timeline.initial
    assert With("first-gravedigger") == initial.whereabouts("spade")
    assert not initial.onstage("spade")

    scene = hamlet.scenes[0]
    assert With("first-gravedigger") == scene.preset.whereabouts("spade")
    assert scene.preset.onstage("spade")
    assert "spade" in {change.entity for change in scene.change}


def test_hamlet_lantern_track(hamlet: Blocking) -> None:
    assert OFFSTAGE == hamlet.timeline.initial.whereabouts("lantern")

    entered = step_with(hamlet, "SET lantern with=horatio")
    assert With("horatio") == entered.state.whereabouts("lantern")
    assert entered.state.onstage("lantern")

    exited = step_with(hamlet, "EXIT horatio via=vom-c")
    assert OFFSTAGE == exited.state.whereabouts("lantern")

    # Not back in V.ii: Horatio enters without it.
    scene_two = hamlet.scenes[1]
    assert OFFSTAGE == scene_two.carried.whereabouts("lantern")
    for step in scene_two.steps:
        assert OFFSTAGE == step.state.whereabouts("lantern")
    assert scene_two.steps[-1].state.onstage("horatio")


def test_hamlet_timing(hamlet: Blocking) -> None:
    let_me_see = step_with(hamlet, "MOVE pos=graveside facing=grave")
    (move,) = let_me_see.directives
    assert isinstance(move, Move)
    assert ("hamlet", True, False) == (
        move.subject,
        move.implied_subject,
        move.until_arrive,
    )
    assert At(Place("graveside")) == let_me_see.state.whereabouts("hamlet")
    assert Toward(Place("grave")) == let_me_see.state.facing("hamlet")

    alas = step_with(hamlet, "SET skull with=hamlet")
    (set_skull,) = alas.directives
    assert isinstance(set_skull, Set)
    assert With("hamlet") == alas.state.whereabouts("skull")

    # Both notes are inline in one speech line: before "Let" and "Alas".
    assert let_me_see.cue.paragraph == alas.cue.paragraph
    dialog = hamlet.element_at(alas.cue)
    assert isinstance(dialog, Dialog)
    text = str(dialog.blocks[alas.cue.part][1])
    assert text[let_me_see.cue.offset :].split()[0] == "Let"
    assert text[alas.cue.offset :].split()[0] == "Alas,"
    assert 3 == hamlet.script_position(alas.cue) - hamlet.script_position(
        let_me_see.cue
    )


def test_hamlet_timeline_queries(hamlet: Blocking) -> None:
    alas = step_with(hamlet, "SET skull with=hamlet")
    assert alas in hamlet.timeline.steps_at(alas.cue.paragraph)
    assert alas.state == hamlet.timeline.state_at(alas.cue)
    later = Cue(alas.cue.paragraph, alas.cue.side, alas.cue.part, alas.cue.offset + 1)
    assert alas.state == hamlet.timeline.state_at(later)
    assert hamlet.timeline.initial == hamlet.timeline.state_at(Cue(0))
    assert Point(1.2, -0.5) == hamlet.point_at("skull", alas.cue)


def test_hamlet_cast_for(hamlet: Blocking) -> None:
    gravedigger = hamlet.cast_for("First Gravedigger (CONT'D)")
    assert gravedigger is not None
    assert "first-gravedigger" == gravedigger.id
    hamlet_cast = hamlet.cast_for("HAMLET")
    assert hamlet_cast is not None
    assert "hamlet" == hamlet_cast.id
    assert hamlet.cast_for("OPHELIA") is None


def test_hamlet_directives_in_script_order(hamlet: Blocking) -> None:
    lines = [directive.line for directive in hamlet.directives]
    assert lines == sorted(lines)
    assert 26 == len(hamlet.directives)


# Script positions


def test_script_position_counts_performed_words_only() -> None:
    blocking = process(
        "[[FSE STAGE type=proscenium width=10 depth=8]]\n"
        "[[FSE ENTITY bob type=cast pos=0,0]]\n"
        "\n"
        "INT. HALL\n"
        "\n"
        "Bob *sits* — down.\n"  # 4 words
        "\n"
        "> CENTRED TEXT <\n"
        "\n"
        "BOB\n"
        "(quietly)\n"  # 1 word
        "Hel[[FSE SET bob facing=90]]lo there.\n"  # on "Hello": 1 word
        "\n"
        "CUT TO:\n"
        "\n"
        "[[FSE SET bob facing=0]]\n"
    )
    first, second = blocking.timeline.steps
    assert 4 + 1 + 1 == blocking.script_position(first.cue)
    assert 4 + 1 + 2 == blocking.script_position(second.cue)


def test_dual_dialogue_counts_left_then_right() -> None:
    blocking = process(
        "[[FSE STAGE type=proscenium width=10 depth=8]]\n"
        "[[FSE ENTITY brick type=cast pos=0,0]]\n"
        "[[FSE ENTITY steel type=cast pos=1,0]]\n"
        "\n"
        "BRICK\n"
        "One two [[FSE SET facing=90]]three.\n"
        "\n"
        "STEEL ^\n"
        "Four [[FSE SET facing=90]]five.\n"
    )
    left, right = blocking.timeline.steps
    assert (0, 1) == (left.cue.side, right.cue.side)
    assert left.cue < right.cue
    assert 2 == blocking.script_position(left.cue)
    assert 3 + 1 == blocking.script_position(right.cue)


# Open moves and interpolation

MOVE_SCRIPT = (
    "[[FSE STAGE type=proscenium width=20 depth=20]]\n"
    "[[FSE ENTITY hamlet type=cast pos=-5,0]]\n"
    "[[FSE ENTITY skull type=prop pos=0,0]]\n"
    "\n"
    "INT. HALL\n"
    "\n"
    "[[FSE MOVE hamlet pos=5,0 until=arrive]]\n"
    "\n"
    "{action}\n"
    "\n"
    "[[FSE ARRIVE hamlet]]\n"
)


def action_with_set(word: int) -> str:
    """Ten words of action, with a SET by Hamlet after `word` of them."""
    words = [f"w{i}" for i in range(10)]
    words.insert(word, "[[FSE SET skull with=hamlet by=hamlet]]")
    return " ".join(words)


@pytest.mark.parametrize(
    ("word", "warns"),
    [(0, True), (2, True), (3, True), (4, False), (5, False), (6, False), (7, True)],
)
def test_reach_uses_the_interpolated_position(word: int, warns: bool) -> None:
    # Hamlet crosses from -5,0 to 5,0 over ten words: at word k he is at
    # k - 5, so |k - 5| from the skull. 3.5 m reach is 1.5 m from it.
    blocking = process(MOVE_SCRIPT.format(action=action_with_set(word)))
    assert warns == any(report.code == "W04" for report in blocking.reports)
    set_step = blocking.timeline.steps[1]
    assert Point(word - 5, 0) == blocking.point_at("hamlet", set_step.cue)
    # The skull is carried: it shares Hamlet's interpolated point.
    assert Point(word - 5, 0) == blocking.point_at("skull", set_step.cue)


def test_reach_at_a_fractional_position() -> None:
    # Word 3.5 of 10: a note inside the fourth word falls on that word, so
    # it counts as 4 words in, putting Hamlet 1 m from the skull.
    action = "w0 w1 w2 w[[FSE SET skull with=hamlet by=hamlet]]3 w4 w5 w6 w7 w8 w9"
    blocking = process(MOVE_SCRIPT.format(action=action))
    assert [] == blocking.reports
    assert Point(-1, 0) == blocking.point_at("hamlet", blocking.timeline.steps[1].cue)


def test_reach_with_waypoints() -> None:
    # Two segments: -5,0 to -5,4 over words 0..4, then on to 5,0 by word 10.
    source = MOVE_SCRIPT.format(
        action="w0 w1 w2 w3 [[FSE VIA hamlet pos=-5,4]]w4 w5 w6 w7 w8 w9"
    )
    blocking = process(source)
    move, via, arrive = blocking.timeline.steps
    assert isinstance(via.state.whereabouts("hamlet"), Moving)
    assert Point(-5, 0) == blocking.point_at("hamlet", move.cue)
    assert Point(-5, 4) == blocking.point_at("hamlet", via.cue)
    halfway = Cue(via.cue.paragraph, 0, 0, len("w0 w1 w2 w3 w4 w5 w6"))
    assert Point(0, 2) == blocking.point_at("hamlet", halfway)
    assert At(Point(5, 0)) == arrive.state.whereabouts("hamlet")


def test_segments_with_no_script_length() -> None:
    blocking = process(
        "[[FSE STAGE type=proscenium width=20 depth=20]]\n"
        "[[FSE ENTITY hamlet type=cast pos=0,0]]\n"
        "\n"
        "INT. HALL\n"
        "\n"
        "[[FSE MOVE hamlet pos=4,4 until=arrive]]\n"
        "[[FSE VIA hamlet pos=0,4]]\n"
        "[[FSE VIA hamlet pos=-4,4]]\n"
        "[[FSE ARRIVE hamlet]]\n"
    )
    move, first, second, arrive = blocking.timeline.steps
    assert Point(0, 0) == blocking.point_at("hamlet", move.cue)
    # Every step sits at the same script position; the route is not skipped.
    vias = [step.state.whereabouts("hamlet") for step in (first, second)]
    assert [Point(0, 4), Point(-4, 4)] == [
        via.move.vias[-1].location for via in vias if isinstance(via, Moving)
    ]
    assert At(Point(4, 4)) == arrive.state.whereabouts("hamlet")


def test_not_an_fse_script() -> None:
    blocking = process("Hamlet waits.\n\n[[FSE move hamlet]]\n")
    assert blocking.stage is None
    assert ["W01"] == [report.code for report in blocking.reports]
    assert [] == blocking.timeline.steps


def test_has_fse_notes() -> None:
    def has(source: str) -> bool:
        return fse.has_fse_notes(fountain.parse(StringIO(source)))

    assert not has("Hamlet waits. [[a note]]\n\n[[fse MOVE x]]")
    assert has("Hamlet waits. [[FSE MOVE x]]")
    assert has("BOB\nHi.\n\nJIM ^\nHo. [[FSE MOVE x]]")
    assert has("Title: T\n[[FSE STAGE]]\n\nText")
    assert has("Hamlet waits. [[FSE MOVE x")
