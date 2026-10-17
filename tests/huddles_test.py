"""Crowded spots on a plan: symbols on top of each other become huddles."""

import io
import math
from pathlib import Path

import pytest
from reportlab.lib.units import mm

from screenplain import fse
from screenplain.export import plans
from screenplain.export.plans import CAST_RADIUS, Huddle, Symbol, crowd
from screenplain.parsers import fountain
from tests.recording_canvas import Recorder

HERE = Path(__file__).parent
SCENE_SIZE = (plans.SCENE_PLAN_WIDTH, plans.SCENE_PLAN_HEIGHT, plans.SCENE_PLAN_PAD)
MARGIN_SIZE = (27 * mm, 24 * mm, 4)


def load(path: Path) -> fse.Blocking:
    return fse.process(fountain.parse(io.StringIO(path.read_text(encoding="utf-8"))))


def cast(entity: str, x: float, y: float = 0, ink: bool = True) -> Symbol:
    return Symbol(entity, True, entity[:2].upper(), (x, y), ink, facing=0)


def prop(
    entity: str, number: int, x: float, y: float = 0, carrier: str | None = None
) -> Symbol:
    return Symbol(entity, False, str(number), (x, y), carrier=carrier)


def texts(items: list[Symbol | Huddle]) -> list[str]:
    return [item.text if isinstance(item, Huddle) else item.label for item in items]


# The rule


def test_a_cast_member_with_riders() -> None:
    items = crowd(
        [
            prop("skull", 2, 50, 50, carrier="hamlet"),
            prop("book", 5, 20, 20, carrier="hamlet"),
            cast("hamlet", 10),
        ]
    )
    assert ["HA · 2 5"] == texts(items)
    (huddle,) = items
    assert isinstance(huddle, Huddle)
    assert (10, 0) == huddle.at


def test_a_prop_table_with_its_load() -> None:
    items = crowd(
        [
            prop("table", 3, 0),
            prop("teapot", 4, 0, carrier="table"),
            prop("cup", 6, 0, carrier="saucer"),
            prop("saucer", 5, 0, carrier="table"),
        ]
    )
    assert ["3 4 5 6"] == texts(items)


def test_cap_is_one_cast_radius_from_the_seed() -> None:
    inside = crowd([cast("jack", 0), cast("cecily", CAST_RADIUS - 0.1)])
    outside = crowd([cast("jack", 0), cast("cecily", CAST_RADIUS + 0.1)])
    assert ["JA CE"] == texts(inside)
    assert ["JA", "CE"] == texts(outside)


def test_huddles_never_chain() -> None:
    step = CAST_RADIUS * 0.8
    items = crowd([cast("aa", 0), cast("bb", step), cast("cc", 2 * step)])
    assert ["AA BB", "CC"] == texts(items)


def test_cast_seed_before_props() -> None:
    items = crowd([prop("chair", 1, 0), cast("gwendolen", 3)])
    (huddle,) = items
    assert isinstance(huddle, Huddle)
    assert "GW · 1" == huddle.text
    assert (3, 0) == huddle.at


def test_inked_seed_before_grey() -> None:
    step = CAST_RADIUS * 0.8
    items = crowd(
        [cast("grey", 0, ink=False), cast("ink", step), cast("far", 2 * step)]
    )
    # The inked one seeds, so both neighbours join it.
    (huddle,) = items
    assert isinstance(huddle, Huddle)
    assert (step, 0) == huddle.at
    assert huddle.ink


def test_members_keep_their_own_ink() -> None:
    (huddle,) = crowd([cast("aa", 0), cast("bb", 1, ink=False)])
    assert isinstance(huddle, Huddle)
    assert [plans.Run("AA", plans.INK), plans.Run("BB", plans.GREY)] == (
        plans.huddle_runs(huddle)
    )
    (grey,) = crowd([cast("aa", 0, ink=False), cast("bb", 1, ink=False)])
    assert isinstance(grey, Huddle)
    assert not grey.ink


def test_props_are_listed_by_number() -> None:
    (huddle,) = crowd([prop("a", 10, 0), prop("b", 2, 0), prop("c", 8, 0)])
    assert isinstance(huddle, Huddle)
    assert "10 2 8" != huddle.text
    assert "2 8 10" == huddle.text


# On a plan


def draw(blocking: fse.Blocking, size: tuple[float, float, float]) -> Recorder:
    scene = blocking.scenes[0]
    key = plans.scene_key(blocking, scene)
    canvas = Recorder()
    plans.draw_plan(canvas, blocking, scene.preset, key.numbers, *size)  # ty: ignore[invalid-argument-type]
    return canvas


def huddle_labels(canvas: Recorder) -> list[str]:
    """The text of each drawn huddle: the runs drawn straight after it."""
    labels = []
    shapes = canvas.shapes
    for index, shape in enumerate(shapes):
        if shape.kind == "roundRect" and shape.filled:
            runs = []
            for run in shapes[index + 1 :]:
                if not run.text:
                    break
                runs.append(run.text)
            labels.append(" ".join(runs))
    return labels


def test_hamlet_churchyard() -> None:
    canvas = draw(load(HERE / "fse" / "hamlet.fountain"), SCENE_SIZE)
    # The gravedigger stands on the skull at the grave, holding the spade.
    assert ["FG · 1 2"] == huddle_labels(canvas)
    assert [] == plans_circles(canvas)


def plans_circles(canvas: Recorder) -> list[str]:
    """Initials drawn in a cast circle of their own."""
    return [
        s.text
        for s in canvas.shapes
        if s.kind == "centred" and s.font[1] == plans.SYMBOL_FONT_SIZE
    ]


def test_tea() -> None:
    canvas = draw(load(HERE / "blocking" / "crowded.fountain"), SCENE_SIZE)
    assert sorted(huddle_labels(canvas)) == sorted(
        [
            "JA · 1",  # on the settee
            "GW · 2 8",  # in the armchair with her diary
            "3 4 5 6",  # the tea table and its load
            "AL · 7",  # with his cigarette case
        ]
    )
    # Cecily beside Jack, and Lane beside Algernon, are near misses.
    assert ["CE", "LA"] == plans_circles(canvas)


def test_no_facing_tick_in_a_huddle() -> None:
    canvas = draw(load(HERE / "blocking" / "crowded.fountain"), SCENE_SIZE)
    ticks = [line for line in canvas.drawn("line") if line.stroke == 0]
    # Everyone faces somewhere, but only Cecily and Lane are drawn alone.
    assert 2 == len(ticks)
    circles = [c for c in canvas.drawn("circle") if c.filled]
    for tick, circle in zip(ticks, circles, strict=True):
        start = tick.args[:2]
        assert math.dist(start, circle.args[:2]) == pytest.approx(CAST_RADIUS)


def test_every_symbol_and_huddle_has_a_halo() -> None:
    canvas = draw(load(HERE / "blocking" / "crowded.fountain"), SCENE_SIZE)
    symbols = [
        s for s in canvas.shapes if s.filled and s.fill == 1 and s.kind != "path"
    ]
    halos = canvas.halos()
    assert len(symbols) == len(halos) == 6
    for halo, symbol in zip(halos, symbols, strict=True):
        assert halo.kind == symbol.kind
        assert halo.args[:2] == symbol.args[:2]
        assert halo.line_width > symbol.line_width
        assert canvas.shapes.index(halo) < canvas.shapes.index(symbol)


def test_draw_order_grey_props_grey_cast_then_ink() -> None:
    blocking = load(HERE / "blocking" / "crowded.fountain")
    scene = blocking.scenes[0]
    key = plans.scene_key(blocking, scene)
    canvas = Recorder()
    inked = {"lane", "settee"}
    plans.draw_plan(
        canvas,  # ty: ignore[invalid-argument-type]
        blocking,
        scene.preset,
        key.numbers,
        *SCENE_SIZE,
        ink=lambda entity: entity in inked,
    )
    drawn = [
        (s.kind, s.stroke)
        for s in canvas.shapes
        if s.filled and s.fill == 1 and s.kind != "path"
    ]
    assert [
        ("roundRect", plans.GREY),  # 3 4 5 6: props only
        ("circle", plans.GREY),  # Cecily
        ("roundRect", plans.GREY),  # GW · 2 8
        ("roundRect", plans.GREY),  # AL · 7
        ("circle", plans.INK),  # Lane
        ("roundRect", plans.INK),  # JA · 1: the settee is inked
    ] == drawn
    assert ["3 4 5 6", "GW · 2 8", "AL · 7", "JA · 1"] == huddle_labels(canvas)


def test_same_state_at_both_sizes() -> None:
    # Two cast 0.53 m apart: clear at scene size, a huddle at margin size.
    source = (
        "[[FSE STAGE type=proscenium width=10 depth=7]]\n"
        "[[FSE ENTITY jack type=cast]]\n"
        "[[FSE ENTITY cecily type=cast]]\n\n"
        "INT. HALL\n\n"
        "[[FSE PRESET jack pos=0,0; PRESET cecily pos=0.53,0]]\n\n"
        "Action.\n"
    )
    blocking = fse.process(fountain.parse(io.StringIO(source)))
    assert blocking.stage is not None
    apart = {
        size: 0.53 * plans.Geometry.fit(blocking.stage, [], *size).scale
        for size in (SCENE_SIZE, MARGIN_SIZE)
    }
    assert apart[MARGIN_SIZE] <= CAST_RADIUS < apart[SCENE_SIZE]
    scene = draw(blocking, SCENE_SIZE)
    assert ["JA", "CE"] == plans_circles(scene)
    assert [] == huddle_labels(scene)
    margin = draw(blocking, MARGIN_SIZE)
    assert [] == plans_circles(margin)
    assert ["JA CE"] == huddle_labels(margin)
