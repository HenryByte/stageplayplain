"""Margin plans: movement, the drawing, cue tags in the text, and the
stacking down the margin.
"""

import io
from pathlib import Path

import pytest
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Flowable, Paragraph

from screenplain import fse
from screenplain.export import margin_plans, pdf, plans, stageplay_pdf
from screenplain.export.margin_plans import (
    MARGIN_PLAN_HEIGHT,
    STACK_GAP,
    Cues,
    MarginLayout,
    MarginPlan,
    Placed,
    html_with_cues,
    movement,
)
from screenplain.export.margin_plans import (
    margin_plans as all_margin_plans,
)
from screenplain.fse.model import Point
from screenplain.parsers import fountain
from screenplain.richstring import Bold, Italic, RichString, Segment, plain
from screenplain.stageplay import to_stageplay
from tests.recording_canvas import Recorder

HERE = Path(__file__).parent


def load(path: Path) -> fse.Blocking:
    return fse.process(fountain.parse(io.StringIO(path.read_text(encoding="utf-8"))))


def process(source: str) -> fse.Blocking:
    return fse.process(fountain.parse(io.StringIO(source)))


@pytest.fixture(scope="module")
def hamlet() -> fse.Blocking:
    return load(HERE / "fse" / "hamlet.fountain")


@pytest.fixture(scope="module")
def parlour() -> fse.Blocking:
    return load(HERE / "blocking" / "movement.fountain")


def group_with(blocking: fse.Blocking, text: str) -> fse.StepGroup:
    return next(
        group
        for group in fse.step_groups(blocking)
        if any(d.text == text for step in group.steps for d in step.directives)
    )


# Movement


def test_entrances_run_from_the_entrance(hamlet: fse.Blocking) -> None:
    moved = movement(hamlet, group_with(hamlet, "ENTER hamlet from=vom-b pos=3,1"))
    assert {"hamlet", "horatio", "lantern"} == moved.movers
    assert [Point(5.2, 3), Point(3, 1)] == moved.paths["hamlet"]
    # The lantern rides in with Horatio: inked, but no path of its own.
    assert "lantern" not in moved.paths
    assert {} == moved.ghosts


def test_exits_leave_a_ghost_and_run_to_the_entrance(hamlet: fse.Blocking) -> None:
    moved = movement(hamlet, group_with(hamlet, "EXIT hamlet via=vom-c"))
    assert {"hamlet", "horatio"} == set(moved.ghosts)
    assert Point(-5.2, 3) == moved.paths["horatio"][-1]
    # The lantern goes with Horatio: no ghost, and not drawn.
    assert "lantern" not in moved.ghosts
    assert "lantern" not in moved.movers
    # The skull is put down at the grave in the same group.
    assert "skull" in moved.movers


def test_a_pick_up_is_inked_without_a_path(hamlet: fse.Blocking) -> None:
    moved = movement(hamlet, group_with(hamlet, "SET skull with=hamlet"))
    assert {"skull"} == moved.movers
    assert {} == moved.paths


def test_open_move_events(parlour: fse.Blocking) -> None:
    start = movement(parlour, group_with(parlour, "MOVE mary pos=2.5,2.4 until=arrive"))
    assert {"mary"} == start.movers
    assert {} == start.paths
    assert [Point(0, -2.5), Point(2.5, 2.4)] == start.remainders["mary"]

    via = movement(parlour, group_with(parlour, "VIA mary pos=-0.5,2.2"))
    assert Point(-0.5, 2.2) == via.paths["mary"][-1]
    assert [Point(-0.5, 2.2), Point(2.5, 2.4)] == via.remainders["mary"]

    arrive = movement(parlour, group_with(parlour, "ARRIVE mary facing=dsc"))
    assert [Point(-0.5, 2.2), Point(2.5, 2.4)] == arrive.paths["mary"]
    assert {} == arrive.remainders


def test_others_in_transit_are_grey_with_no_path(parlour: fse.Blocking) -> None:
    group = group_with(parlour, "MOVE arthur pos=1.4,0.2")
    moved = movement(parlour, group)
    assert {"arthur"} == moved.movers
    assert "mary" not in moved.paths
    # Mary is drawn part way along her cross.
    point = parlour.point_in(group.after, "mary", group.last_cue)
    assert point is not None
    assert point not in (Point(0, -2.5), Point(-0.5, 2.2))


# Drawing


def draw(blocking: fse.Blocking, text: str, label: str = "4") -> Recorder:
    group = group_with(blocking, text)
    canvas = Recorder()
    numbers = plans.scene_key(blocking, group.scene).numbers
    margin_plans.draw_margin_plan(canvas, blocking, group, numbers, label)  # ty: ignore[invalid-argument-type]
    return canvas


def test_margin_plan_size_and_number(hamlet: fse.Blocking) -> None:
    canvas = draw(hamlet, "SET skull with=hamlet", "7")
    frame = canvas.shapes[0]
    assert (0, 0, margin_plans.MARGIN_PLAN_WIDTH, MARGIN_PLAN_HEIGHT) == frame.args
    number = canvas.text("7")
    assert number.args[1] > MARGIN_PLAN_HEIGHT - 10
    assert number.args[0] < 5
    # No labels at margin size.
    assert not {"FRONT", "vom-a", "grave"} & set(canvas.texts())


def test_movers_in_ink_and_the_rest_grey(parlour: fse.Blocking) -> None:
    canvas = draw(parlour, "MOVE arthur pos=1.4,0.2")
    assert plans.INK == canvas.text("AR").fill
    assert plans.GREY == canvas.text("MA").fill
    # A dotted path with an arrowhead.
    paths = [s for s in canvas.drawn("path") if s.dashed and not s.filled]
    heads = [s for s in canvas.drawn("path") if s.filled and s.fill == plans.INK]
    assert 1 == len(paths)
    assert 1 == len(heads)


def test_exit_ghosts_are_dashed(parlour: fse.Blocking) -> None:
    canvas = draw(parlour, "EXIT inspector via=french-windows")
    ghosts = [s for s in canvas.drawn("circle") if s.dashed]
    assert 2 == len(ghosts)
    assert {plans.GHOST_GREY} == {ghost.stroke for ghost in ghosts}
    assert ("Helvetica", plans.SYMBOL_FONT_SIZE) == canvas.text("IG").font


def test_carried_plan_number_has_a_triangle(hamlet: fse.Blocking) -> None:
    canvas = draw(hamlet, "SET skull with=hamlet", "▸7")
    assert "7" in canvas.texts()
    triangle = [
        s
        for s in canvas.drawn("path")
        if s.filled and s.args[1] > MARGIN_PLAN_HEIGHT - 10
    ]
    assert 1 == len(triangle)


# Which plans


def test_numbers_restart_in_each_scene(hamlet: fse.Blocking) -> None:
    assert [1, 2, 3, 4, 5, 1] == [plan.number for plan in all_margin_plans(hamlet)]


# Cue tags


def test_html_with_cues_splits_styled_text() -> None:
    text = RichString(Segment("Alas, ", ()), Segment("poor", {Italic, Bold}))
    html = html_with_cues(text, [(8, "p0"), (0, "p1")])
    tag = '<onDraw name="fse_cue" label="{}"/>'
    assert (
        tag.format("p1")
        + "Alas, <strong><em>po</em></strong>"
        + tag.format("p0")
        + "<strong><em>or</em></strong>"
    ) == html


def test_html_with_cues_and_none_is_to_html() -> None:
    text = plain(" leading space")
    assert text.to_html() == html_with_cues(text, [])


def test_cues_are_placed_by_paragraph(hamlet: fse.Blocking) -> None:
    margin = all_margin_plans(hamlet)
    cues = Cues.place(hamlet, margin)
    paragraphs = hamlet.screenplay.paragraphs
    # Plan 1 follows "The FIRST GRAVEDIGGER digs": the end of that action.
    (end,) = [index for index, ids in cues.end.items() if "p0" in ids]
    assert str(paragraphs[end].lines[0]).startswith("The FIRST")  # ty: ignore[unresolved-attribute]
    # Plans 3 and 4 are inline in Hamlet's speech.
    inline = {plan_id for ids in cues.inline.values() for _, plan_id in ids}
    assert {"p2", "p3"} == inline
    # Scene II has nothing but notes: its plan goes on its heading.
    (heading,) = [index for index, ids in cues.end.items() if "p5" in ids]
    assert paragraphs[heading] is hamlet.scenes[1].boundary


def test_stage_direction_cues_skip_the_at_signs() -> None:
    settings = stageplay_pdf.StagePlaySettings(
        font_settings=stageplay_pdf.get_standard_font_settings()
    )
    play = to_stageplay(
        fountain.parse(
            io.StringIO("Title: X\nFormat: Stage Play\n\n@Mary sits by @Arthur.\n")
        )
    )
    (direction,) = play.body
    assert isinstance(direction, stageplay_pdf.StageDirection)
    (line,) = direction.lines
    # "@Mary sits by @Arthur.": offset 6 is before "sits", 14 inside "@Arthur".
    html = stageplay_pdf._direction_line_html(line, settings, [(6, "a"), (16, "b")])
    tag = '<onDraw name="fse_cue" label="{}"/>'
    assert f" {tag.format('a')}sits by {tag.format('b')}<font" in html


# Stacking


class Layout(MarginLayout):
    def __init__(self, blocking: fse.Blocking) -> None:
        super().__init__(blocking, all_margin_plans(blocking), 400, 750, 72)
        self.margin = all_margin_plans(blocking)

    def cue(self, number: int, y: float) -> None:
        self.page.append(Placed(self.margin[number - 1], 1, 100, y))


def test_a_plan_sits_level_with_its_cue(hamlet: fse.Blocking) -> None:
    layout = Layout(hamlet)
    layout.cue(1, 600)
    page = layout.layout()
    ((plan, top, label, leader),) = page.plans
    assert (1, 600 + margin_plans.MARKER_FONT_SIZE, "1", None) == (
        plan.number,
        top,
        label,
        leader,
    )
    assert {600: ["1"]} == page.markers


def test_plans_are_pushed_down_with_a_leader(hamlet: fse.Blocking) -> None:
    layout = Layout(hamlet)
    layout.cue(1, 600)
    layout.cue(2, 590)
    first, second = layout.layout().plans
    assert second[1] == first[1] - MARGIN_PLAN_HEIGHT - STACK_GAP
    assert 590 == second[3]


def test_cues_on_one_line_share_a_marker(hamlet: fse.Blocking) -> None:
    layout = Layout(hamlet)
    layout.cue(3, 500)
    layout.cue(4, 500)
    assert {500: ["3", "4"]} == layout.layout().markers


def test_overflow_carries_to_the_next_page(hamlet: fse.Blocking) -> None:
    layout = Layout(hamlet)
    layout.cue(1, 150)
    layout.cue(2, 140)
    page = layout.layout()
    assert [1] == [plan.number for plan, *_ in page.plans]
    assert [2] == [plan.number for plan in page.carry]
    assert {150: ["1"], 140: ["2▸"]} == page.markers
    # Next page: the carried plan goes first, at the top.
    layout.carried, layout.page = page.carry, []
    layout.cue(3, 700)
    page = layout.layout()
    assert [
        ("▸2", 750),
        ("3", pytest.approx(750 - MARGIN_PLAN_HEIGHT - STACK_GAP)),
    ] == [(label, top) for _, top, label, _ in page.plans]


# In the PDF


def drawn_plans(
    monkeypatch: pytest.MonkeyPatch, layout: str, blocking: fse.Blocking
) -> list[tuple[int, str]]:
    """Each margin plan drawn: page and label."""
    drawn: list[tuple[int, str]] = []
    original = MarginLayout._draw_plan

    def record(
        self: MarginLayout, canvas: Canvas, plan: MarginPlan, top: float, label: str
    ) -> None:
        drawn.append((canvas.getPageNumber(), label))
        original(self, canvas, plan, top, label)

    monkeypatch.setattr(MarginLayout, "_draw_plan", record)
    if layout == "stageplay":
        play = to_stageplay(blocking.screenplay)
        stageplay_pdf.to_pdf(play, io.BytesIO(), blocking=blocking)  # ty: ignore[invalid-argument-type]
    else:
        pdf.to_pdf(blocking.screenplay, io.BytesIO(), blocking=blocking)  # ty: ignore[invalid-argument-type]
    return drawn


@pytest.mark.parametrize("layout", ["stageplay", "screenplay"])
def test_every_plan_is_drawn_once(
    monkeypatch: pytest.MonkeyPatch, layout: str, parlour: fse.Blocking
) -> None:
    drawn = drawn_plans(monkeypatch, layout, parlour)
    numbers = [int(label.strip("▸")) for _, label in drawn]
    assert list(range(1, 11)) == numbers


def test_plans_carried_past_the_last_page_get_a_page(
    monkeypatch: pytest.MonkeyPatch, parlour: fse.Blocking
) -> None:
    drawn = drawn_plans(monkeypatch, "stageplay", parlour)
    last_text_page = drawn[0][0]
    carried = [(page, label) for page, label in drawn if label.startswith("▸")]
    assert carried
    assert all(page == last_text_page + 1 for page, _ in carried)


def test_hamlet_scene_two_plan_is_drawn(
    monkeypatch: pytest.MonkeyPatch, hamlet: fse.Blocking
) -> None:
    drawn = drawn_plans(monkeypatch, "screenplay", hamlet)
    assert ["1", "2", "3", "4", "5", "1"] == [label for _, label in drawn]


@pytest.mark.parametrize("layout", ["stageplay", "screenplay"])
def test_cue_tags_do_not_move_the_text(
    monkeypatch: pytest.MonkeyPatch, layout: str, parlour: fse.Blocking
) -> None:
    def place(blocking: fse.Blocking) -> list[tuple[int, float, float]]:
        placed: list[tuple[int, float, float]] = []

        def after(doc: object, flowable: Flowable) -> None:
            if isinstance(flowable, Paragraph):
                frame = doc.frame  # ty: ignore[unresolved-attribute]
                placed.append(
                    (doc.page, frame._y, flowable.height)  # ty: ignore[unresolved-attribute]
                )

        template = (
            stageplay_pdf.StagePlayDocTemplate
            if layout == "stageplay"
            else pdf.DocTemplate
        )
        monkeypatch.setattr(template, "afterFlowable", after, raising=False)
        if layout == "stageplay":
            stageplay_pdf.to_pdf(
                to_stageplay(blocking.screenplay),
                io.BytesIO(),  # ty: ignore[invalid-argument-type]
                blocking=blocking,
            )
        else:
            pdf.to_pdf(blocking.screenplay, io.BytesIO(), blocking=blocking)  # ty: ignore[invalid-argument-type]
        return placed

    with_tags = place(parlour)
    monkeypatch.setattr(Cues, "place", classmethod(lambda cls, b, m: cls()))
    without_tags = place(parlour)
    assert with_tags == without_tags
    assert len(with_tags) > 10


@pytest.mark.parametrize(
    "settings",
    [
        pdf.with_blocking_margins(
            pdf.Settings(font_settings=pdf.get_standard_font_settings())
        ),
        stageplay_pdf.StagePlaySettings(
            font_settings=stageplay_pdf.get_standard_font_settings()
        ),
    ],
    ids=["screenplay", "stageplay"],
)
def test_margin_plans_fit_beside_the_text(settings: pdf.Settings) -> None:
    left = settings.left_margin + settings.frame_width + margin_plans.TEXT_GAP
    clear = settings.page_width - left - margin_plans.MARGIN_PLAN_WIDTH
    # About 5 mm clear of the unprintable edge.
    assert clear >= 5 * mm - 0.01
