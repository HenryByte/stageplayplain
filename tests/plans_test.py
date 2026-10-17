"""Drawing a plan from a stage state, checked by its drawn primitives."""

import io
import math

import pytest
from reportlab.lib.units import mm

from screenplain import fse
from screenplain.export import plans
from screenplain.export.plans import CAST_RADIUS, FACING_TICK, PROP_HALF
from screenplain.fse.model import Point, State
from screenplain.parsers import fountain
from tests.recording_canvas import Recorder, Shape

W, H, PAD = plans.SCENE_PLAN_WIDTH, plans.SCENE_PLAN_HEIGHT, plans.SCENE_PLAN_PAD
MARGIN_W, MARGIN_H, MARGIN_PAD = 27 * mm, 24 * mm, 4


def blocking_for(declarations: str, preset: str = "") -> fse.Blocking:
    source = declarations + "\n\nINT. HALL\n\n"
    if preset:
        source += f"[[FSE {preset}]]\n\n"
    source += "Action.\n"
    return fse.process(fountain.parse(io.StringIO(source)))


def draw(
    blocking: fse.Blocking,
    state: State | None = None,
    numbers: dict[str, int] | None = None,
    size: tuple[float, float, float] = (W, H, PAD),
) -> Recorder:
    canvas = Recorder()
    state = state if state is not None else blocking.scenes[0].preset
    plans.draw_plan(canvas, blocking, state, numbers or {}, *size)  # ty: ignore[invalid-argument-type]
    return canvas


def stage_outline(canvas: Recorder) -> Shape:
    """The stage: the filled shape drawn in the stage's grey."""
    (outline,) = [s for s in canvas.shapes if s.fill == plans.STAGE_FILL and s.filled]
    return outline


def centre(shape: Shape) -> tuple[float, float]:
    if shape.kind == "circle":
        return shape.args[0], shape.args[1]
    x, y, w, h = shape.args[:4]
    return x + w / 2, y + h / 2


def casts(canvas: Recorder) -> list[Shape]:
    return [s for s in canvas.drawn("circle") if s.args[2] == CAST_RADIUS]


def props(canvas: Recorder) -> list[Shape]:
    return [s for s in canvas.drawn("rect") if s.args[2] == 2 * PROP_HALF]


# Frame and stage outline


def test_frame_is_the_whole_box() -> None:
    canvas = draw(blocking_for("[[FSE STAGE type=proscenium width=10 depth=8]]"))
    frame = canvas.shapes[0]
    assert ("rect", (0, 0, W, H)) == (frame.kind, frame.args)


def test_proscenium() -> None:
    canvas = draw(blocking_for("[[FSE STAGE type=proscenium width=10 depth=8]]"))
    outline = stage_outline(canvas)
    assert "rect" == outline.kind
    assert not outline.dashed
    (audience,) = [s for s in canvas.shapes if s.text == "AUDIENCE"]
    assert audience.args[1] < outline.args[1]
    assert audience.args[1] > 0


def test_traverse_has_audience_on_both_sides() -> None:
    canvas = draw(blocking_for("[[FSE STAGE type=traverse width=12 depth=4]]"))
    outline = stage_outline(canvas)
    assert "rect" == outline.kind
    below, above = sorted(
        (s for s in canvas.shapes if s.text == "AUDIENCE"), key=lambda s: s.args[1]
    )
    assert below.args[1] < outline.args[1]
    assert above.args[1] > outline.args[1] + outline.args[3]
    assert above.args[1] + plans.AUDIENCE_FONT_SIZE < H


def test_round_is_a_circle_with_its_front_labelled() -> None:
    canvas = draw(blocking_for("[[FSE STAGE type=round radius=6]]"))
    outline = stage_outline(canvas)
    assert "circle" == outline.kind
    (front,) = [s for s in canvas.shapes if s.text == "FRONT"]
    assert front.args[1] < outline.args[1] - outline.args[2]
    assert "AUDIENCE" not in canvas.texts()


def test_round_declared_by_width_and_depth_is_a_rectangle() -> None:
    canvas = draw(blocking_for("[[FSE STAGE type=round width=10 depth=8]]"))
    assert "rect" == stage_outline(canvas).kind
    assert "FRONT" in canvas.texts()


def test_flexible_is_dashed_with_no_audience() -> None:
    canvas = draw(blocking_for("[[FSE STAGE type=flexible width=10 depth=8]]"))
    assert stage_outline(canvas).dashed
    assert not {"AUDIENCE", "FRONT"} & set(canvas.texts())


def test_stage_fits_the_box_and_keeps_its_proportions() -> None:
    canvas = draw(blocking_for("[[FSE STAGE type=proscenium width=10 depth=8]]"))
    x, y, w, h = stage_outline(canvas).args[:4]
    assert w / h == pytest.approx(10 / 8)
    assert x == pytest.approx(PAD) or y == pytest.approx(PAD + plans.AUDIENCE_BAND)
    assert x + w <= W - PAD + 1e-6
    assert y + h <= H - PAD + 1e-6


def test_bounds_include_entrances_beyond_the_edge() -> None:
    canvas = draw(
        blocking_for(
            "[[FSE STAGE type=proscenium width=10 depth=8]]\n"
            "[[FSE ENTITY door type=entrance pos=8,0]]"
        )
    )
    x, _, w, _ = stage_outline(canvas).args[:4]
    (triangle,) = canvas.drawn("path")
    tip_x = max(px for px, _ in triangle.points)
    assert tip_x <= W - PAD + plans.ENTRANCE_HALF
    # The stage is 10 wide, the bounds 13: the stage takes 10/13 of them.
    scale = w / 10
    assert (triangle.points[2][0] - x) / scale == pytest.approx(13)


# Marks and entrances


def test_marks_are_grey_crosses_with_their_id() -> None:
    canvas = draw(
        blocking_for(
            "[[FSE STAGE type=proscenium width=10 depth=8]]\n"
            "[[FSE ENTITY dsc type=mark pos=0,-3]]"
        )
    )
    cross = canvas.drawn("line")
    assert 2 == len(cross)
    assert all(line.stroke == plans.MARK_GREY for line in cross)
    label = canvas.text("dsc")
    assert plans.MARK_GREY == label.fill
    outline = stage_outline(canvas)
    mid_x = (cross[0].args[0] + cross[0].args[2]) / 2
    assert mid_x == pytest.approx(centre(outline)[0])


def test_entrances_are_open_triangles_with_their_id() -> None:
    canvas = draw(
        blocking_for(
            "[[FSE STAGE type=proscenium width=10 depth=8]]\n"
            "[[FSE ENTITY door-sl type=entrance pos=5,1]]\n"
            "[[FSE ENTITY door-sr type=entrance pos=-5,1]]"
        )
    )
    triangles = canvas.drawn("path")
    assert 2 == len(triangles)
    assert all(3 == len(t.points) and t.fill == 1 and t.filled for t in triangles)
    # Each id sits on the side towards the middle.
    assert "right" == canvas.text("door-sl").kind
    assert "text" == canvas.text("door-sr").kind


# Cast and props


HALL = (
    "[[FSE STAGE type=proscenium width=10 depth=8]]\n"
    "[[FSE ENTITY dsc type=mark pos=0,-3]]\n"
    "[[FSE ENTITY hamlet type=cast]]\n"
    '[[FSE ENTITY gertrude type=cast cue="QUEEN GERTRUDE"]]\n'
    "[[FSE ENTITY ghost type=cast]]\n"
    "[[FSE ENTITY throne type=prop pos=-3,2]]\n"
    "[[FSE ENTITY cup type=prop]]"
)


def test_cast_are_circles_with_initials_at_their_scaled_spot() -> None:
    blocking = blocking_for(
        HALL, "PRESET hamlet pos=0,0; PRESET gertrude pos=2,1 facing=dsc"
    )
    canvas = draw(blocking, numbers={"throne": 1})
    outline = stage_outline(canvas)
    scale = outline.args[2] / 10
    origin = centre(outline)
    hamlet = canvas.text("HA")
    gertrude = canvas.text("QG")
    assert "centred" == hamlet.kind
    assert hamlet.args[0] == pytest.approx(origin[0])
    assert gertrude.args[0] - hamlet.args[0] == pytest.approx(2 * scale)
    assert gertrude.args[1] - hamlet.args[1] == pytest.approx(1 * scale)
    circles = casts(canvas)
    assert 2 == len(circles)
    assert all(c.filled and c.fill == 1 and c.stroke == 0 for c in circles)


def test_offstage_entities_are_not_drawn() -> None:
    canvas = draw(blocking_for(HALL, "PRESET hamlet pos=0,0"), numbers={"throne": 1})
    assert 1 == len(casts(canvas))
    assert 1 == len(props(canvas))
    assert "GH" not in canvas.texts()


def test_facing_tick_points_where_the_cast_member_faces() -> None:
    blocking = blocking_for(
        HALL,
        "PRESET hamlet pos=0,0 facing=90; PRESET gertrude pos=2,1 facing=dsc; "
        "PRESET ghost pos=-2,-1",
    )
    canvas = draw(blocking, numbers={"throne": 1})
    ticks = [line for line in canvas.drawn("line") if line.stroke == 0]
    assert 2 == len(ticks)

    def tick_from(initials: str) -> Shape:
        label = canvas.text(initials)
        return min(ticks, key=lambda t: math.dist(t.args[:2], label.args[:2]))

    hamlet = tick_from("HA")
    x1, y1, x2, y2 = hamlet.args
    # 90 degrees is +x; the tick runs from the rim outwards.
    assert y1 == pytest.approx(y2)
    assert x2 - x1 == pytest.approx(FACING_TICK)
    gertrude = tick_from("QG")
    x1, y1, x2, y2 = gertrude.args
    # dsc is down and to the left of her.
    assert x2 < x1
    assert y2 < y1
    assert math.dist((x1, y1), (x2, y2)) == pytest.approx(FACING_TICK)


def test_facing_a_cast_member_follows_them() -> None:
    blocking = blocking_for(
        HALL,
        "PRESET hamlet pos=0,0 facing=gertrude; PRESET gertrude pos=3,0",
    )
    hamlet = plans.facing_angle(
        blocking, blocking.scenes[0].preset, "hamlet", Point(0, 0)
    )
    assert hamlet == pytest.approx(math.pi / 2)
    # She crosses upstage of him; he keeps facing her.
    source = (
        HALL
        + "\n\nINT. HALL\n\n"
        + "[[FSE PRESET hamlet pos=0,0 facing=gertrude; PRESET gertrude pos=3,0]]\n\n"
        + "Action.\n\n[[FSE MOVE gertrude pos=0,3]]\n\nShe crosses.\n"
    )
    blocking = fse.process(fountain.parse(io.StringIO(source)))
    after = blocking.timeline.steps[-1].state
    hamlet = plans.facing_angle(blocking, after, "hamlet", Point(0, 0))
    assert hamlet == pytest.approx(0)


def test_props_are_squares_numbered_by_the_caller() -> None:
    blocking = blocking_for(HALL, "PRESET hamlet pos=0,0; PRESET cup pos=3,0")
    canvas = draw(blocking, numbers={"throne": 4, "cup": 7})
    assert 2 == len(props(canvas))
    assert {"4", "7"} <= set(canvas.texts())
    cup, hamlet = canvas.text("7"), canvas.text("HA")
    outline = stage_outline(canvas)
    assert cup.args[0] - hamlet.args[0] == pytest.approx(3 * outline.args[2] / 10)


def test_symbol_font_size_does_not_scale_with_the_plan() -> None:
    blocking = blocking_for(HALL, "PRESET hamlet pos=0,0")
    big = draw(blocking, numbers={"throne": 1})
    small = draw(blocking, numbers={"throne": 1}, size=(MARGIN_W, MARGIN_H, MARGIN_PAD))
    for canvas in (big, small):
        assert ("Helvetica-Bold", plans.SYMBOL_FONT_SIZE) == canvas.text("HA").font
        assert ("Helvetica-Bold", plans.SYMBOL_FONT_SIZE) == canvas.text("1").font
        assert CAST_RADIUS == casts(canvas)[0].args[2]
    assert stage_outline(small).args[2] < stage_outline(big).args[2]


def test_plan_drawing_is_a_flowable_of_its_size() -> None:
    blocking = blocking_for(HALL, "PRESET hamlet pos=0,0")
    drawing = plans.PlanDrawing(
        blocking, blocking.scenes[0].preset, {"throne": 1}, MARGIN_W, MARGIN_H, 4
    )
    assert (MARGIN_W, MARGIN_H) == drawing.wrap(500, 500)
    canvas = Recorder()
    drawing.drawOn(canvas, 10, 20)
    assert (10, 20, MARGIN_W, MARGIN_H) == canvas.shapes[0].args


def test_initials_and_names() -> None:
    blocking = blocking_for(HALL)
    gertrude = blocking.entities["gertrude"]
    assert isinstance(gertrude, fse.blocking.Cast)
    assert "QG" == plans.initials(gertrude)
    assert "Queen Gertrude" == plans.key_name(gertrude)
