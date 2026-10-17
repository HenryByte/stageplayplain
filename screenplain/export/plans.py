# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php

"""Plans: small ground-plan drawings of the stage, drawn from the blocking.

`draw_plan` draws the stage at one moment into a box; `PlanDrawing` wraps
it as a flowable. A `ScenePlan` is the block at the top of a scene: the
plan of its preset state at the right, its key in columns to the left.

Symbols on top of each other are drawn as one huddle (`crowd`).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import override

from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Flowable

from screenplain.fse import Blocking, Scene
from screenplain.fse.directives import Stage
from screenplain.fse.model import (
    At,
    Bearing,
    Cast,
    Entrance,
    Mark,
    Moving,
    Place,
    Point,
    Prop,
    State,
    Toward,
    carrier,
)
from screenplain.types import Note, PageBreak

SCENE_PLAN_WIDTH = 34 * mm
SCENE_PLAN_HEIGHT = 30 * mm
SCENE_PLAN_PAD = 6

FONT = "Helvetica"
BOLD = "Helvetica-Bold"
# Initials and prop numbers are this size whatever the size of the plan.
SYMBOL_FONT_SIZE = 4
LABEL_FONT_SIZE = 4.5
AUDIENCE_FONT_SIZE = 5
# Room under (or over) the stage for its audience label.
AUDIENCE_BAND = 8

CAST_RADIUS = 4
PROP_HALF = 2.5
FACING_TICK = 3
MARK_HALF = 1.5
ENTRANCE_HALF = 2.5
HUDDLE_HALF_HEIGHT = 3.2
HUDDLE_GAP = 2.2
HALO_WIDTH = 1.6

INK = 0
GREY = 0.68
MARK_GREY = 0.5
LABEL_GREY = 0.45
STAGE_FILL = 0.94

KEY_FONT_SIZE = 7
KEY_LEADING = 3.4 * mm
KEY_COLUMN_WIDTH = 30 * mm
KEY_GUTTER = 3 * mm
KEY_GAP = 5 * mm
KEY_GREY = 0.55


# What is where


def floor_point(blocking: Blocking, state: State, entity: str) -> Point | None:
    """Where an entity stands in a state, following `on` and `with` down
    to the floor; None when it is offstage.

    A moving entity is drawn where its current segment starts; a scene
    plan's state has no open moves.
    """
    seen: set[str] = set()
    while entity not in seen:
        seen.add(entity)
        whereabouts = state.whereabouts(entity)
        if isinstance(whereabouts, At):
            return blocking.resolve(whereabouts.location)
        if isinstance(whereabouts, Moving):
            move = whereabouts.move
            start = move.vias[-1].location if move.vias else move.origin
            return blocking.resolve(start)
        parent = carrier(whereabouts)
        if parent is None:
            return None
        entity = parent
    return None


def facing_angle(
    blocking: Blocking, state: State, entity: str, at: Point
) -> float | None:
    """A cast member's facing in radians, clockwise from +y; None when
    unset.
    """
    facing = state.facing(entity)
    if isinstance(facing, Bearing):
        return math.radians(facing.degrees)
    if isinstance(facing, Toward):
        location = facing.location
        if isinstance(location, Place) and location.id in state:
            target = floor_point(blocking, state, location.id)
        else:
            target = blocking.resolve(location)
        if target is None or target == at:
            return None
        return math.atan2(target.x - at.x, target.y - at.y)
    return None


def _words(entity: Cast | Prop) -> list[str]:
    name = entity.character_cue if isinstance(entity, Cast) else None
    return (name or entity.id).replace("-", " ").replace("_", " ").split()


def initials(cast: Cast) -> str:
    """Two-letter initials from a cast member's `cue=`, or else their id.

    >>> initials(Cast("hamlet", None, 1))
    'HA'
    >>> initials(Cast("lady-b", None, 1, "LADY BRACKNELL"))
    'LB'
    """
    words = _words(cast)
    if len(words) > 1:
        return (words[0][0] + words[1][0]).upper()
    return words[0][:2].upper()


def key_name(entity: Cast | Prop) -> str:
    """The name a key gives an entity: its label, or else its `cue=` or id.

    >>> key_name(Cast("first-gravedigger", None, 1, "FIRST GRAVEDIGGER"))
    'First Gravedigger'
    >>> key_name(Prop("tea-table", None, 1))
    'Tea table'
    >>> key_name(Prop("piano", "Grand piano", 1))
    'Grand piano'
    """
    if entity.label:
        return entity.label
    text = " ".join(_words(entity))
    if isinstance(entity, Cast):
        return text.title()
    return text[:1].upper() + text[1:]


# Stage geometry


@dataclass(frozen=True)
class Geometry:
    """Maps stage coordinates into a box, audience at the bottom. The
    stage and every entrance fit inside it.
    """

    stage: Stage
    scale: float
    min_x: float
    min_y: float
    max_y: float
    origin_x: float
    origin_y: float

    @classmethod
    def fit(
        cls,
        stage: Stage,
        entrances: list[Point],
        width: float,
        height: float,
        pad: float,
    ) -> Geometry:
        half_x, half_y = half_extents(stage)
        xs = [-half_x, half_x, *(point.x for point in entrances)]
        ys = [-half_y, half_y, *(point.y for point in entrances)]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        bottom = pad + (AUDIENCE_BAND if audience_sides(stage) else 0)
        top = pad + (AUDIENCE_BAND if len(audience_sides(stage)) > 1 else 0)
        inner_width, inner_height = width - 2 * pad, height - bottom - top
        scale = min(inner_width / (max_x - min_x), inner_height / (max_y - min_y))
        return cls(
            stage,
            scale,
            min_x,
            min_y,
            max_y,
            pad + (inner_width - scale * (max_x - min_x)) / 2,
            bottom + (inner_height - scale * (max_y - min_y)) / 2,
        )

    def __call__(self, point: Point) -> tuple[float, float]:
        return (
            self.origin_x + (point.x - self.min_x) * self.scale,
            self.origin_y + (point.y - self.min_y) * self.scale,
        )


def half_extents(stage: Stage) -> tuple[float, float]:
    if stage.radius is not None:
        return stage.radius, stage.radius
    assert stage.width is not None and stage.depth is not None
    return stage.width / 2, stage.depth / 2


def audience_sides(stage: Stage) -> list[str]:
    """Where the audience label goes: "front" (-y) and "back" (+y)."""
    if stage.type == "traverse":
        return ["front", "back"]
    if stage.type in ("proscenium", "round"):
        return ["front"]
    return []


# Symbols and huddles


@dataclass
class Symbol:
    """A cast member's circle or a prop's square, at its drawn centre."""

    entity: str
    is_cast: bool
    label: str
    at: tuple[float, float]
    ink: bool = True
    facing: float | None = None
    # The entity it is `on` or `with`, if any.
    carrier: str | None = None


@dataclass
class Huddle:
    """Symbols drawn as one rounded label, sitting on its seed's spot."""

    members: list[Symbol]

    @property
    def seed(self) -> Symbol:
        return self.members[0]

    @property
    def at(self) -> tuple[float, float]:
        return self.seed.at

    @property
    def ink(self) -> bool:
        return any(member.ink for member in self.members)

    @property
    def is_cast(self) -> bool:
        return any(member.is_cast for member in self.members)

    @property
    def cast(self) -> list[Symbol]:
        return [member for member in self.members if member.is_cast]

    @property
    def props(self) -> list[Symbol]:
        props = [member for member in self.members if not member.is_cast]
        return sorted(props, key=lambda member: int(member.label))

    @property
    def text(self) -> str:
        """The label as text, e.g. `GW · 2 8`."""
        cast = " ".join(member.label for member in self.cast)
        props = " ".join(member.label for member in self.props)
        return " · ".join(part for part in (cast, props) if part)


def crowd(symbols: list[Symbol], cap: float = CAST_RADIUS) -> list[Symbol | Huddle]:
    """Merges symbols on top of each other into huddles.

    A symbol joins the first huddle whose seed's drawn centre is within
    `cap` of its own; seeds are taken cast first, inked first. Huddles
    never chain through a member that is not the seed. Every prop `on` or
    `with` something joins its carrier's huddle, whatever the distance.
    """
    by_id = {symbol.entity: symbol for symbol in symbols}

    def is_rider(symbol: Symbol) -> bool:
        return symbol.carrier in by_id

    def base(symbol: Symbol) -> Symbol:
        seen: set[str] = set()
        while is_rider(symbol) and symbol.entity not in seen:
            seen.add(symbol.entity)
            assert symbol.carrier is not None
            symbol = by_id[symbol.carrier]
        return symbol

    candidates = sorted(
        (symbol for symbol in symbols if not is_rider(symbol)),
        key=lambda symbol: (not symbol.is_cast, not symbol.ink),
    )
    groups: list[list[Symbol]] = []
    home: dict[str, list[Symbol]] = {}
    for symbol in candidates:
        group = next((g for g in groups if math.dist(g[0].at, symbol.at) <= cap), None)
        if group is None:
            group = []
            groups.append(group)
        group.append(symbol)
        home[symbol.entity] = group
    for symbol in symbols:
        if is_rider(symbol):
            home[base(symbol).entity].append(symbol)
    return [group[0] if len(group) == 1 else Huddle(group) for group in groups]


def plan_symbols(
    blocking: Blocking,
    state: State,
    numbers: dict[str, int],
    geometry: Geometry,
    ink: Callable[[str], bool],
) -> list[Symbol]:
    """A symbol for every onstage cast member and prop, props first."""
    symbols: list[Symbol] = []
    entities = [e for e in blocking.entities.values() if isinstance(e, Prop)] + [
        e for e in blocking.entities.values() if isinstance(e, Cast)
    ]
    for entity in entities:
        point = floor_point(blocking, state, entity.id)
        if point is None:
            continue
        is_cast = isinstance(entity, Cast)
        symbols.append(
            Symbol(
                entity.id,
                is_cast,
                initials(entity)
                if isinstance(entity, Cast)
                else str(numbers[entity.id]),
                geometry(point),
                ink(entity.id),
                facing_angle(blocking, state, entity.id, point) if is_cast else None,
                carrier(state.whereabouts(entity.id)),
            )
        )
    return symbols


# Drawing


def draw_plan(
    canvas: Canvas,
    blocking: Blocking,
    state: State,
    numbers: dict[str, int],
    width: float,
    height: float,
    pad: float,
    ink: Callable[[str], bool] = lambda entity: True,
) -> None:
    """Draws the stage in a state into a `width` by `height` box at the
    origin. `numbers` gives each prop its number from the scene's key;
    `ink` says which entities are drawn in ink rather than grey.
    """
    stage = blocking.stage
    assert stage is not None
    entrances = [e for e in blocking.entities.values() if isinstance(e, Entrance)]
    marks = [e for e in blocking.entities.values() if isinstance(e, Mark)]
    geometry = Geometry.fit(
        stage, [entrance.point for entrance in entrances], width, height, pad
    )
    canvas.saveState()
    canvas.setStrokeGray(INK)
    canvas.setLineWidth(0.5)
    canvas.rect(0, 0, width, height)
    _draw_stage(canvas, geometry)
    _draw_audience(canvas, geometry, width)
    for mark in marks:
        _draw_mark(canvas, geometry, mark)
    for entrance in entrances:
        _draw_entrance(canvas, geometry, entrance)
    items = crowd(plan_symbols(blocking, state, numbers, geometry, ink))
    # Grey props, grey cast, then inked symbols on top.
    for item in sorted(items, key=lambda item: (item.ink, item.is_cast)):
        if isinstance(item, Huddle):
            _draw_huddle(canvas, item)
        elif item.is_cast:
            _draw_cast(canvas, item)
        else:
            _draw_prop(canvas, item)
    canvas.restoreState()


def _draw_stage(canvas: Canvas, geometry: Geometry) -> None:
    stage = geometry.stage
    canvas.setFillGray(STAGE_FILL)
    canvas.setStrokeGray(INK)
    canvas.setLineWidth(0.6)
    if stage.type == "flexible":
        canvas.setDash(2, 2)
    if stage.radius is not None:
        x, y = geometry(Point(0, 0))
        canvas.circle(x, y, stage.radius * geometry.scale, fill=1)
    else:
        half_x, half_y = half_extents(stage)
        x0, y0 = geometry(Point(-half_x, -half_y))
        x1, y1 = geometry(Point(half_x, half_y))
        canvas.rect(x0, y0, x1 - x0, y1 - y0, fill=1)
    canvas.setDash()


def _draw_audience(canvas: Canvas, geometry: Geometry, width: float) -> None:
    """Labels the audience side below everything drawn (and above, for a
    traverse), clear of entrances on the edge.
    """
    stage = geometry.stage
    text = "FRONT" if stage.type == "round" else "AUDIENCE"
    canvas.setFillGray(LABEL_GREY)
    canvas.setFont(FONT, AUDIENCE_FONT_SIZE)
    for side in audience_sides(stage):
        if side == "front":
            y = geometry.origin_y - AUDIENCE_BAND + 1
        else:
            top = geometry(Point(0, geometry.max_y))[1]
            y = top + AUDIENCE_BAND - AUDIENCE_FONT_SIZE - 1
        canvas.drawCentredString(width / 2, y, text)


def _draw_mark(canvas: Canvas, geometry: Geometry, mark: Mark) -> None:
    x, y = geometry(mark.point)
    canvas.setStrokeGray(MARK_GREY)
    canvas.setLineWidth(0.4)
    canvas.line(x - MARK_HALF, y - MARK_HALF, x + MARK_HALF, y + MARK_HALF)
    canvas.line(x - MARK_HALF, y + MARK_HALF, x + MARK_HALF, y - MARK_HALF)
    canvas.setFillGray(MARK_GREY)
    canvas.setFont(FONT, LABEL_FONT_SIZE)
    canvas.drawString(x + 2, y - 4, mark.id)


def _draw_entrance(canvas: Canvas, geometry: Geometry, entrance: Entrance) -> None:
    x, y = geometry(entrance.point)
    canvas.setFillGray(1)
    canvas.setStrokeGray(INK)
    canvas.setLineWidth(0.5)
    path = canvas.beginPath()
    path.moveTo(x - ENTRANCE_HALF, y - ENTRANCE_HALF)
    path.lineTo(x + ENTRANCE_HALF, y - ENTRANCE_HALF)
    path.lineTo(x, y + ENTRANCE_HALF * 0.8)
    path.close()
    canvas.drawPath(path, fill=1)
    # The id goes on the side towards the middle of the stage.
    canvas.setFillGray(INK)
    canvas.setFont(FONT, LABEL_FONT_SIZE)
    centre_x = geometry(Point(0, 0))[0]
    label_y = y - LABEL_FONT_SIZE / 2 + 0.3
    if x > centre_x + 0.5:
        canvas.drawRightString(x - ENTRANCE_HALF - 1, label_y, entrance.id)
    else:
        canvas.drawString(x + ENTRANCE_HALF + 1, label_y, entrance.id)


def _gray(ink: bool) -> float:
    return INK if ink else GREY


def _draw_cast(canvas: Canvas, symbol: Symbol) -> None:
    x, y = symbol.at
    canvas.setStrokeGray(1)
    canvas.setLineWidth(HALO_WIDTH)
    canvas.circle(x, y, CAST_RADIUS)
    canvas.setStrokeGray(_gray(symbol.ink))
    canvas.setFillGray(1)
    canvas.setLineWidth(0.7)
    canvas.circle(x, y, CAST_RADIUS, fill=1)
    if symbol.facing is not None:
        dx, dy = math.sin(symbol.facing), math.cos(symbol.facing)
        tip = CAST_RADIUS + FACING_TICK
        canvas.line(
            x + CAST_RADIUS * dx, y + CAST_RADIUS * dy, x + tip * dx, y + tip * dy
        )
    canvas.setFillGray(_gray(symbol.ink))
    canvas.setFont(BOLD, SYMBOL_FONT_SIZE)
    canvas.drawCentredString(x, y - SYMBOL_FONT_SIZE * 0.35, symbol.label)


def _draw_prop(canvas: Canvas, symbol: Symbol) -> None:
    x, y = symbol.at
    side = 2 * PROP_HALF
    canvas.setStrokeGray(1)
    canvas.setLineWidth(HALO_WIDTH)
    canvas.rect(x - PROP_HALF, y - PROP_HALF, side, side)
    canvas.setStrokeGray(_gray(symbol.ink))
    canvas.setFillGray(1)
    canvas.setLineWidth(0.5)
    canvas.rect(x - PROP_HALF, y - PROP_HALF, side, side, fill=1)
    canvas.setFillGray(_gray(symbol.ink))
    canvas.setFont(BOLD, SYMBOL_FONT_SIZE)
    canvas.drawCentredString(x, y - SYMBOL_FONT_SIZE * 0.35, symbol.label)


def huddle_runs(huddle: Huddle) -> list[tuple[str, bool]]:
    """The pieces of a huddle's label, each with whether it is inked: the
    cast's initials, a separator, then the props' numbers.
    """
    runs = [(member.label, member.ink) for member in huddle.cast]
    if huddle.cast and huddle.props:
        runs.append(("·", huddle.ink))
    runs += [(member.label, member.ink) for member in huddle.props]
    return runs


def huddle_half_width(huddle: Huddle) -> float:
    runs = huddle_runs(huddle)
    text = sum(stringWidth(run, BOLD, SYMBOL_FONT_SIZE) for run, _ in runs)
    return (text + HUDDLE_GAP * (len(runs) - 1) + 3) / 2


def _draw_huddle(canvas: Canvas, huddle: Huddle) -> None:
    x, y = huddle.at
    half_w, half_h = huddle_half_width(huddle), HUDDLE_HALF_HEIGHT
    canvas.setStrokeGray(1)
    canvas.setLineWidth(HALO_WIDTH)
    canvas.roundRect(x - half_w, y - half_h, 2 * half_w, 2 * half_h, half_h)
    canvas.setStrokeGray(_gray(huddle.ink))
    canvas.setFillGray(1)
    canvas.setLineWidth(0.6)
    canvas.roundRect(x - half_w, y - half_h, 2 * half_w, 2 * half_h, half_h, fill=1)
    canvas.setFont(BOLD, SYMBOL_FONT_SIZE)
    run_x = x - half_w + 1.5
    for text, ink in huddle_runs(huddle):
        canvas.setFillGray(_gray(ink))
        canvas.drawString(run_x, y - SYMBOL_FONT_SIZE * 0.35, text)
        run_x += stringWidth(text, BOLD, SYMBOL_FONT_SIZE) + HUDDLE_GAP


class PlanDrawing(Flowable):
    """A plan of the stage in one state, as a flowable."""

    def __init__(
        self,
        blocking: Blocking,
        state: State,
        numbers: dict[str, int],
        width: float = SCENE_PLAN_WIDTH,
        height: float = SCENE_PLAN_HEIGHT,
        pad: float = SCENE_PLAN_PAD,
    ) -> None:
        Flowable.__init__(self)
        self.blocking = blocking
        self.state = state
        self.numbers = numbers
        self.width = width
        self.height = height
        self.pad = pad

    @override
    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        return self.width, self.height

    def draw(self) -> None:
        draw_plan(
            self.canv,
            self.blocking,
            self.state,
            self.numbers,
            self.width,
            self.height,
            self.pad,
        )


# Scene plans


@dataclass(frozen=True)
class Key:
    """Every cast member, then every prop, that appears anywhere in a
    scene. Props are numbered from 1 for the whole scene; `off` holds
    those off at the top of the scene.
    """

    cast: list[Cast]
    props: list[Prop]
    off: set[str] = field(default_factory=set)

    @property
    def numbers(self) -> dict[str, int]:
        return {prop.id: number for number, prop in enumerate(self.props, 1)}


def scene_key(blocking: Blocking, scene: Scene) -> Key:
    states = [scene.preset, *(step.state for step in scene.steps)]
    appearing = {
        entity for state in states for entity in state if state.onstage(entity)
    }
    entities = [e for e in blocking.entities.values() if e.id in appearing]
    return Key(
        [e for e in entities if isinstance(e, Cast)],
        [e for e in entities if isinstance(e, Prop)],
        {e.id for e in entities if not scene.preset.onstage(e.id)},
    )


def scene_plans(blocking: Blocking) -> dict[int, Scene]:
    """The scenes that get a scene plan, by the index of their boundary in
    the screenplay's paragraphs: those with content before the next
    boundary.
    """
    paragraphs = blocking.screenplay.paragraphs
    index_of = {id(para): index for index, para in enumerate(paragraphs)}
    starts = [index_of[id(scene.boundary)] for scene in blocking.scenes]
    ends = [*starts[1:], len(paragraphs)][: len(starts)]
    return {
        start: scene
        for scene, start, end in zip(blocking.scenes, starts, ends, strict=True)
        if any(
            not isinstance(para, (Note, PageBreak))
            for para in paragraphs[start + 1 : end]
        )
    }


@dataclass(frozen=True)
class KeyEntry:
    tag: str
    name: str
    grey: bool


@dataclass(frozen=True)
class KeyLine:
    tag: str
    text: str
    indent: float
    grey: bool


def key_entries(key: Key) -> list[KeyEntry]:
    return [
        KeyEntry(initials(cast), key_name(cast), cast.id in key.off)
        for cast in key.cast
    ] + [
        KeyEntry(str(number), key_name(prop), prop.id in key.off)
        for number, prop in enumerate(key.props, 1)
    ]


def entry_lines(entry: KeyEntry, width: float) -> list[KeyLine]:
    """An entry's lines in a column `width` wide, continuation lines
    indented under the start of the name.
    """
    indent = stringWidth(entry.tag + " ", BOLD, KEY_FONT_SIZE)
    lines: list[KeyLine] = []
    current = ""
    for word in entry.name.split():
        trial = f"{current} {word}".strip()
        if current and stringWidth(trial, FONT, KEY_FONT_SIZE) > width - indent:
            lines.append(
                KeyLine("" if lines else entry.tag, current, indent, entry.grey)
            )
            current = word
        else:
            current = trial
    lines.append(KeyLine("" if lines else entry.tag, current, indent, entry.grey))
    return lines


def layout_columns(
    entries: list[list[KeyLine]], columns: int, rows: int
) -> list[list[KeyLine]] | None:
    """Fills columns of `rows` lines, down then across, without splitting
    an entry; None when the entries do not fit.
    """
    filled: list[list[KeyLine]] = [[]]
    for lines in entries:
        if filled[-1] and len(filled[-1]) + len(lines) > rows:
            filled.append([])
        filled[-1] += lines
    if len(filled) > columns or any(len(column) > rows for column in filled):
        return None
    return filled


class ScenePlan(Flowable):
    """The block at the top of a scene: its plan at the right edge of the
    text column, its key in columns to the left. Never splits; it keeps
    with the scene's first element.
    """

    def __init__(self, blocking: Blocking, scene: Scene) -> None:
        Flowable.__init__(self)
        self.key = scene_key(blocking, scene)
        self.drawing = PlanDrawing(blocking, scene.preset, self.key.numbers)
        self.keepWithNext = 1
        self.columns: list[list[KeyLine]] = []
        self.width = 0.0
        self.height = 0.0

    @override
    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        drawing_width, drawing_height = self.drawing.wrap(availWidth, availHeight)
        space = availWidth - drawing_width - KEY_GAP
        count = max(1, int((space + KEY_GUTTER) // (KEY_COLUMN_WIDTH + KEY_GUTTER)))
        entries = [
            entry_lines(entry, KEY_COLUMN_WIDTH) for entry in key_entries(self.key)
        ]
        rows = max(1, int(drawing_height // KEY_LEADING))
        while (columns := layout_columns(entries, count, rows)) is None:
            rows += 1
        self.columns = columns
        self.width = availWidth
        self.height = max(drawing_height, rows * KEY_LEADING)
        return self.width, self.height

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        canvas.translate(
            self.width - self.drawing.width, self.height - self.drawing.height
        )
        self.drawing.drawOn(canvas, 0, 0)
        canvas.restoreState()
        canvas.saveState()
        for number, column in enumerate(self.columns):
            x = number * (KEY_COLUMN_WIDTH + KEY_GUTTER)
            for row, line in enumerate(column):
                y = self.height - (row + 1) * KEY_LEADING + 1
                canvas.setFillGray(KEY_GREY if line.grey else INK)
                if line.tag:
                    canvas.setFont(BOLD, KEY_FONT_SIZE)
                    canvas.drawString(x, y, line.tag)
                canvas.setFont(FONT, KEY_FONT_SIZE)
                canvas.drawString(x + line.indent, y, line.text)
        canvas.restoreState()
