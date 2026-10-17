# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php

"""Margin plans: a small plan beside the script for each step group with a
picture change, tied to its cue by a plan marker.

The exporters splice a zero-width `<onDraw>` tag into the text at each
group's cue (`Cues`). While a page is drawn, ReportLab reports where each
tag lands; at the end of the page `MarginLayout` stacks that page's plans
down the right margin, without moving the text.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import override

from reportlab import platypus
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import BaseDocTemplate, Flowable, Spacer

from screenplain.export import plans
from screenplain.export.plans import Geometry
from screenplain.fse import Blocking, Scene, StepGroup, picture_changes, step_groups
from screenplain.fse.directives import Enter, Exit, Move
from screenplain.fse.directives import Note as NoteDirective
from screenplain.fse.model import Cast, Cue, Moving, Place, Point, carrier
from screenplain.richstring import RichString, Segment
from screenplain.types import Note, PageBreak

MARGIN_PLAN_WIDTH = 27 * mm
MARGIN_PLAN_HEIGHT = 24 * mm
MARGIN_PLAN_PAD = 4
# Between the text column and the plans; the plan markers sit in it.
TEXT_GAP = 3 * mm
STACK_GAP = 2 * mm

MARKER_FONT_SIZE = 6
NUMBER_FONT_SIZE = 6
CARRIED_SIZE = 2.2

# A NOTE for a cast member, in a box the width of a plan.
NOTE_LABEL = "*"
NOTE_FONT_SIZE = 6
NOTE_LEADING = 7
NOTE_PAD = 2

PATH_DASH = (0.6, 1.2)
PATH_WIDTH = 0.8
REMAINDER_DASH = (1.5, 1.2)
REMAINDER_GREY = 0.3
ARROW_HEAD = 3
# A turn in place: an arc this far outside the cast circle.
TURN_GAP = 2
TURN_HEAD = 1.8
TURN_WIDTH = 0.5
LEADER_WIDTH = 0.25
LEADER_GREY = 0.45

CUE_CALLBACK = "fse_cue"


# What moved


@dataclass
class Movement:
    """How a step group changes the stage picture.

    `movers` are inked. `paths` run from where a mover was to where it is
    (or, for an exit, from its ghost to the entrance it leaves by);
    `remainders` run on to the destination of a move still open.
    `turns` are the facings, from and to, of movers who turn in place.
    """

    movers: set[str] = field(default_factory=set)
    paths: dict[str, list[Point]] = field(default_factory=dict)
    remainders: dict[str, list[Point]] = field(default_factory=dict)
    ghosts: dict[str, Point] = field(default_factory=dict)
    turns: dict[str, tuple[float, float]] = field(default_factory=dict)


def movement(blocking: Blocking, group: StepGroup) -> Movement:
    before, after = group.before, group.after
    result = Movement()
    directives = [d for step in group.steps for d in step.directives]
    enters = {d.subject: d for d in directives if isinstance(d, Enter)}
    exits = {d.subject: d for d in directives if isinstance(d, Exit)}
    for entity in sorted(picture_changes(blocking, before, after)):
        was = blocking.point_in(before, entity, group.previous or group.cue)
        now = blocking.point_in(after, entity, group.last_cue)
        rides_before = carrier(before.whereabouts(entity)) is not None
        rides_after = carrier(after.whereabouts(entity)) is not None
        if now is not None:
            result.movers.add(entity)
        if was is None and now is not None:
            enter = enters.get(entity)
            if enter is not None and enter.from_ and not rides_after:
                result.paths[entity] = _route(
                    blocking, group, entity, blocking.resolve(Place(enter.from_)), now
                )
        elif was is not None and now is None:
            # A struck prop is simply gone; only cast leave a ghost.
            if not rides_before and isinstance(blocking.entities[entity], Cast):
                result.ghosts[entity] = was
                exit_ = exits.get(entity) or exits.get("all")
                if exit_ is not None and exit_.via:
                    result.paths[entity] = _route(
                        blocking, group, entity, was, blocking.resolve(Place(exit_.via))
                    )
        elif was is not None and now is not None:
            if not (rides_before and rides_after) and was.distance(now) > 1e-9:
                result.paths[entity] = _route(blocking, group, entity, was, now)
            else:
                start = plans.facing_angle(blocking, before, entity, was)
                end = plans.facing_angle(blocking, after, entity, now)
                if start is not None and end is not None and turn(start, end):
                    result.turns[entity] = (start, end)
        whereabouts = after.whereabouts(entity)
        if isinstance(whereabouts, Moving) and now is not None:
            destination = blocking.resolve(whereabouts.move.destination)
            result.remainders[entity] = [now, destination]
    return result


def turn(start: float, end: float) -> float:
    """The angle swept turning from one facing to another, clockwise
    positive. A turn never sweeps past facing upstage, back to the
    audience, so it can be the long way round.
    """
    sweep = (end - start) % math.tau
    if sweep < 1e-9 or math.tau - sweep < 1e-9:
        return 0
    upstage = -start % math.tau
    if upstage < 1e-9 or abs(upstage - sweep) < 1e-9:
        # From or to upstage: the short way.
        return sweep if sweep <= math.pi else sweep - math.tau
    return sweep - math.tau if upstage < sweep else sweep


def _route(
    blocking: Blocking, group: StepGroup, entity: str, start: Point, end: Point
) -> list[Point]:
    """A mover's path from start to end through a `MOVE`'s `via` points
    and where it stands after each step of the group but the last, so a
    `VIA` in the same group bends it too.
    """
    route = [start]

    def add(point: Point | None) -> None:
        if point is not None and point.distance(route[-1]) > 1e-9:
            route.append(point)

    for index, step in enumerate(group.steps):
        for directive in step.directives:
            if isinstance(directive, Move) and directive.subject == entity:
                for location in directive.via:
                    add(blocking.resolve(location))
        if index < len(group.steps) - 1:
            add(blocking.point_in(step.state, entity, step.cue))
    if end.distance(route[-1]) > 1e-9 or len(route) == 1:
        route.append(end)
    return route


# Drawing


def _arrow(
    canvas: Canvas,
    points: list[tuple[float, float]],
    gap_start: float,
    gap_end: float,
    dash: tuple[float, float],
    gray: float = plans.INK,
    width: float = PATH_WIDTH,
) -> None:
    """A dashed polyline with an arrowhead, trimmed at both ends. Too
    short a line is not drawn: the ink alone marks the change.
    """
    if len(points) < 2:
        return
    points = list(points)
    (x0, y0), (x1, y1) = points[0], points[1]
    length = math.hypot(x1 - x0, y1 - y0)
    if length <= gap_start:
        return
    points[0] = (
        x0 + (x1 - x0) * gap_start / length,
        y0 + (y1 - y0) * gap_start / length,
    )
    (xa, ya), (xb, yb) = points[-2], points[-1]
    length = math.hypot(xb - xa, yb - ya)
    if length <= gap_end + ARROW_HEAD:
        return
    tip = (xb - (xb - xa) * gap_end / length, yb - (yb - ya) * gap_end / length)
    points[-1] = tip
    canvas.saveState()
    canvas.setStrokeGray(gray)
    canvas.setFillGray(gray)
    canvas.setLineWidth(width)
    canvas.setDash(*dash)
    path = canvas.beginPath()
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    canvas.drawPath(path, stroke=1, fill=0)
    canvas.setDash()
    _head(canvas, tip, math.atan2(tip[1] - ya, tip[0] - xa), ARROW_HEAD)
    canvas.restoreState()


def _head(canvas: Canvas, tip: tuple[float, float], angle: float, size: float) -> None:
    """A filled arrowhead pointing along `angle`, in the current fill."""
    head = canvas.beginPath()
    head.moveTo(*tip)
    for side in (-0.45, 0.45):
        head.lineTo(
            tip[0] - size * math.cos(angle + side),
            tip[1] - size * math.sin(angle + side),
        )
    head.close()
    canvas.drawPath(head, stroke=0, fill=1)


def _turn(
    canvas: Canvas, centre: tuple[float, float], start: float, end: float
) -> None:
    """An arc around a cast circle from one facing to another, the way
    `turn` sweeps, its arrowhead stopping just short of the new facing tick.
    """
    radius = plans.CAST_RADIUS + TURN_GAP
    sweep = turn(start, end)
    stop = math.copysign(0.8 / radius, sweep)
    if abs(sweep - stop) * radius <= TURN_HEAD + 0.5:
        return
    steps = max(2, math.ceil(abs(sweep) / (math.pi / 24)))
    x, y = centre

    def at(bearing: float) -> tuple[float, float]:
        return (x + radius * math.sin(bearing), y + radius * math.cos(bearing))

    points = [at(start + (sweep - stop) * i / steps) for i in range(steps + 1)]
    canvas.saveState()
    canvas.setStrokeGray(plans.INK)
    canvas.setFillGray(plans.INK)
    canvas.setLineWidth(TURN_WIDTH)
    path = canvas.beginPath()
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    canvas.drawPath(path, stroke=1, fill=0)
    # The tangent at the tip, in canvas angles: bearings run clockwise
    # from +y, canvas angles counterclockwise from +x.
    bearing = start + sweep - stop
    _head(
        canvas,
        points[-1],
        math.pi / 2 - bearing - math.copysign(math.pi / 2, sweep),
        TURN_HEAD,
    )
    canvas.restoreState()


def draw_margin_plan(
    canvas: Canvas,
    blocking: Blocking,
    group: StepGroup,
    numbers: dict[str, int],
    label: str,
) -> None:
    """Draws a group's margin plan at the origin, its plan number (e.g.
    `3`, or `▸3` when carried) in the top-left corner.
    """
    moved = movement(blocking, group)
    radius = plans.CAST_RADIUS

    def draw_paths(
        canvas: Canvas,
        geometry: Geometry,
        drawn: dict[str, tuple[float, float]],
        ghosts: dict[str, tuple[float, float]],
    ) -> None:
        for entity, route in moved.paths.items():
            points = [geometry(point) for point in route]
            if entity in moved.ghosts:
                # An exit: from the ghost to the entrance.
                points[0] = ghosts.get(entity, points[0])
                _arrow(canvas, points, radius + 0.5, ARROW_HEAD, PATH_DASH)
            else:
                points[-1] = drawn.get(entity, points[-1])
                _arrow(canvas, points, 0, radius + 1, PATH_DASH)
        for entity, route in moved.remainders.items():
            points = [geometry(point) for point in route]
            points[0] = drawn.get(entity, points[0])
            _arrow(
                canvas,
                points,
                radius + 1,
                ARROW_HEAD,
                REMAINDER_DASH,
                REMAINDER_GREY,
                0.6,
            )
        for entity, (start, end) in moved.turns.items():
            if entity in drawn:
                _turn(canvas, drawn[entity], start, end)

    plans.draw_plan(
        canvas,
        blocking,
        group.after,
        numbers,
        MARGIN_PLAN_WIDTH,
        MARGIN_PLAN_HEIGHT,
        MARGIN_PLAN_PAD,
        ink=lambda entity: entity in moved.movers,
        cue=group.last_cue,
        ghosts=moved.ghosts,
        paths=draw_paths,
        labels=False,
    )
    _draw_label(canvas, label, 1.5, MARGIN_PLAN_HEIGHT - NUMBER_FONT_SIZE - 1)


def draw_margin_note(canvas: Canvas, note: MarginNote, label: str) -> None:
    """Draws a note at the origin: a box with its marker (e.g. `*`, or
    `▸*` when carried) and the cast member's initials on the first line,
    and the note in italic below.
    """
    height = note.height
    canvas.saveState()
    canvas.setStrokeGray(plans.INK)
    canvas.setLineWidth(0.5)
    canvas.rect(0, 0, MARGIN_PLAN_WIDTH, height)
    baseline = height - NOTE_PAD - NUMBER_FONT_SIZE
    _draw_label(canvas, label, NOTE_PAD, baseline)
    canvas.setFillGray(plans.INK)
    canvas.setFont(plans.BOLD, NUMBER_FONT_SIZE)
    canvas.drawString(NOTE_PAD + label_width(label) + 2, baseline, note.cast)
    canvas.setFont(plans.ITALIC, NOTE_FONT_SIZE)
    for line in note.lines:
        baseline -= NOTE_LEADING
        canvas.drawString(NOTE_PAD, baseline, line)
    canvas.restoreState()


def _draw_label(canvas: Canvas, label: str, x: float, y: float) -> None:
    """Draws a plan number or marker, where `▸` stands for a carried plan.
    The standard fonts have no `▸`, so it is drawn as a small triangle.
    """
    canvas.saveState()
    canvas.setFillGray(plans.INK)
    canvas.setFont(plans.BOLD, NUMBER_FONT_SIZE)
    for piece in label.replace("▸", "\0▸\0").split("\0"):
        if piece == "▸":
            size = CARRIED_SIZE
            mid = y + NUMBER_FONT_SIZE * 0.35
            path = canvas.beginPath()
            path.moveTo(x + 0.3, mid - size)
            path.lineTo(x + 0.3 + size * 1.4, mid)
            path.lineTo(x + 0.3, mid + size)
            path.close()
            canvas.drawPath(path, stroke=0, fill=1)
            x += size * 1.4 + 0.8
        elif piece:
            canvas.drawString(x, y, piece)
            x += stringWidth(piece, plans.BOLD, NUMBER_FONT_SIZE)
    canvas.restoreState()


def label_width(label: str) -> float:
    carried = label.count("▸") * (CARRIED_SIZE * 1.4 + 0.8)
    return stringWidth(label.replace("▸", ""), plans.BOLD, NUMBER_FONT_SIZE) + carried


# Which plans


@dataclass(frozen=True)
class MarginPlan:
    """A step group's plan: its number in the scene, and the scene's prop
    numbers to read it against.
    """

    id: str
    number: int
    group: StepGroup
    numbers: dict[str, int]

    @property
    def cue(self) -> Cue:
        return self.group.cue

    @property
    def scene(self) -> Scene:
        return self.group.scene

    @property
    def label(self) -> str:
        return str(self.number)

    @property
    def height(self) -> float:
        return MARGIN_PLAN_HEIGHT


@dataclass(frozen=True)
class MarginNote:
    """A `NOTE` for a cast member: their initials and the note."""

    id: str
    cue: Cue
    scene: Scene
    cast: str
    text: str

    @property
    def label(self) -> str:
        return NOTE_LABEL

    @property
    def lines(self) -> list[str]:
        return simpleSplit(
            self.text, plans.ITALIC, NOTE_FONT_SIZE, MARGIN_PLAN_WIDTH - 2 * NOTE_PAD
        )

    @property
    def height(self) -> float:
        return NOTE_PAD * 2 + NUMBER_FONT_SIZE + 1 + len(self.lines) * NOTE_LEADING


# What goes in the margin: plans and notes.
type MarginItem = MarginPlan | MarginNote


def margin_plans(blocking: Blocking) -> list[MarginPlan]:
    """Every margin plan, in script order, numbered from 1 in each scene."""
    result: list[MarginPlan] = []
    keys = {}
    counts: dict[int, int] = {}
    for group in step_groups(blocking):
        scene = id(group.scene)
        if scene not in keys:
            keys[scene] = plans.scene_key(blocking, group.scene).numbers
        counts[scene] = counts.get(scene, 0) + 1
        result.append(MarginPlan(f"p{len(result)}", counts[scene], group, keys[scene]))
    return result


def margin_notes(blocking: Blocking) -> list[MarginNote]:
    """Every scene's `NOTE`s, in script order."""
    result: list[MarginNote] = []
    for scene in blocking.scenes:
        for step in scene.steps:
            for directive in step.directives:
                if isinstance(directive, NoteDirective):
                    cast = blocking.entities[directive.subject]
                    assert isinstance(cast, Cast)
                    result.append(
                        MarginNote(
                            f"n{len(result)}",
                            directive.cue,
                            scene,
                            plans.initials(cast),
                            directive.note,
                        )
                    )
    return result


def margin_items(blocking: Blocking) -> list[MarginItem]:
    """The margin plans and notes in script order, a plan before a note at
    the same cue.
    """
    items: list[MarginItem] = [*margin_plans(blocking), *margin_notes(blocking)]
    return sorted(items, key=lambda item: (item.cue, isinstance(item, MarginNote)))


# Where cues go in the text


def cue_tag(plan_id: str) -> str:
    """A zero-width tag that reports where it lands when drawn."""
    return f'<onDraw name="{CUE_CALLBACK}" label="{plan_id}"/>'


def split_rich(text: RichString, offset: int) -> tuple[RichString, RichString]:
    """Splits a rich string at a character offset of its plain text."""
    before: list[Segment] = []
    after: list[Segment] = []
    remaining = offset
    for segment in text.segments:
        if remaining >= len(segment.text):
            before.append(segment)
            remaining -= len(segment.text)
        elif remaining <= 0:
            after.append(segment)
        else:
            before.append(Segment(segment.text[:remaining], segment.styles))
            after.append(Segment(segment.text[remaining:], segment.styles))
            remaining = 0
    return RichString(*before), RichString(*after)


def html_with_cues(
    text: RichString, cues: Iterable[tuple[int, str]], inline: bool = False
) -> str:
    """A rich string's HTML with a cue tag at each (offset, plan id).
    `inline` keeps a leading space, as `RichString.to_inline_html`.
    """
    html: list[str] = []
    rest, done = text, 0
    for offset, plan_id in sorted(cues, key=lambda cue: cue[0]):
        head, rest = split_rich(rest, offset - done)
        done = offset
        html.append(head.to_inline_html() if html or inline else head.to_html())
        html.append(cue_tag(plan_id))
    html.append(rest.to_inline_html() if html or inline else rest.to_html())
    return "".join(html)


@dataclass
class Cues:
    """Where each margin plan's cue tag goes, by screenplay paragraph.

    An inline cue goes at its offset in a part of its paragraph. A
    standalone note's cue goes at the end of the element before it in its
    scene, or else at the start of the element after it, or else at the
    end of the scene's heading.
    """

    inline: dict[tuple[int, int, int], list[tuple[int, str]]] = field(
        default_factory=dict
    )
    start: dict[int, list[str]] = field(default_factory=dict)
    end: dict[int, list[str]] = field(default_factory=dict)

    @classmethod
    def place(cls, blocking: Blocking, margin: Sequence[MarginItem]) -> Cues:
        cues = cls()
        paragraphs = blocking.screenplay.paragraphs
        index_of = {id(para): index for index, para in enumerate(paragraphs)}

        def is_element(index: int) -> bool:
            return not isinstance(paragraphs[index], (Note, PageBreak))

        for plan in margin:
            cue = plan.cue
            if cue.part >= 0:
                key = (cue.paragraph, cue.side, cue.part)
                cues.inline.setdefault(key, []).append((cue.offset, plan.id))
                continue
            boundary = index_of[id(plan.scene.boundary)]
            previous = next(
                (
                    index
                    for index in range(cue.paragraph - 1, boundary, -1)
                    if is_element(index)
                ),
                None,
            )
            if previous is not None:
                cues.end.setdefault(previous, []).append(plan.id)
                continue
            following = next(
                (
                    index
                    for index in range(cue.paragraph + 1, len(paragraphs))
                    if is_element(index)
                ),
                None,
            )
            if following is not None:
                cues.start.setdefault(following, []).append(plan.id)
            else:
                # Nothing after it either: the scene's heading.
                cues.end.setdefault(boundary, []).append(plan.id)
        return cues

    def part(self, paragraph: int, side: int, part: int) -> list[tuple[int, str]]:
        return self.inline.get((paragraph, side, part), [])

    def before(self, paragraph: int) -> str:
        return "".join(cue_tag(plan_id) for plan_id in self.start.get(paragraph, []))

    def after(self, paragraph: int) -> str:
        return "".join(cue_tag(plan_id) for plan_id in self.end.get(paragraph, []))


class CueSpacer(Spacer):
    """An empty line of a speech that holds cues (a glued note)."""

    def __init__(self, width: float, height: float, plan_ids: list[str]) -> None:
        Spacer.__init__(self, width, height)
        self.plan_ids = plan_ids

    @override
    def draw(self) -> None:
        canvas = self.canv
        for plan_id in self.plan_ids:
            getattr(canvas, CUE_CALLBACK)(canvas, "onDraw", plan_id, at=(0, 0))


# Laying out the margin


@dataclass
class PageLayout:
    """One page's margin: each plan with its top, number and the baseline
    of the cue its leader starts from (None when level with its cue); the
    plan markers by baseline; and the plans carried to the next page.
    """

    plans: list[tuple[MarginItem, float, str, float | None]] = field(
        default_factory=list
    )
    markers: dict[float, list[str]] = field(default_factory=dict)
    carry: list[MarginItem] = field(default_factory=list)


class FlushMargin(Flowable):
    """Ends the story: adds pages while margin plans are still carried, so
    none is lost after the last page of text.
    """

    def __init__(self, layout: MarginLayout) -> None:
        Flowable.__init__(self)
        self.layout = layout

    @override
    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        # Every cue on this page has been drawn by now.
        if self.layout.layout().carry:
            return availWidth, availHeight + 1
        return 0, 0

    @override
    def split(self, availWidth: float, availheight: float) -> list[Flowable]:
        return [platypus.PageBreak(), FlushMargin(self.layout)]

    def draw(self) -> None:
        pass


@dataclass
class Placed:
    """A cue as drawn: its page, line baseline and plan."""

    plan: MarginItem
    page: int
    x: float
    y: float


class MarginLayout:
    """Collects where cues land while a page is drawn, and at the end of
    the page stacks its margin plans down the right margin: each level
    with its cue's line or pushed down below the plan above, and carried
    to the top of the next page's margin when it runs off the bottom.
    """

    def __init__(
        self,
        blocking: Blocking,
        margin: Sequence[MarginItem],
        text_right: float,
        top: float,
        bottom: float,
    ) -> None:
        self.blocking = blocking
        self.plans = {plan.id: plan for plan in margin}
        self.text_right = text_right
        self.top = top
        self.bottom = bottom
        self.page: list[Placed] = []
        self.carried: list[MarginItem] = []
        self.drawn: set[str] = set()

    @property
    def plan_x(self) -> float:
        return self.text_right + TEXT_GAP

    def install(self, doc: BaseDocTemplate) -> None:
        """Hooks the layout into a document before it is built."""
        for template in doc.pageTemplates:
            on_page = template.onPage
            on_page_end = template.onPageEnd

            def begin_page(
                canvas: Canvas, doc: BaseDocTemplate, on_page: object = on_page
            ) -> None:
                # ReportLab 5 looks callbacks up with getNamedCB; 4 uses
                # canvas attributes.
                set_named_cb = getattr(canvas, "setNamedCB", None)
                if set_named_cb is not None:
                    set_named_cb(CUE_CALLBACK, self.record)
                else:
                    setattr(canvas, CUE_CALLBACK, self.record)
                on_page(canvas, doc)  # ty: ignore[call-non-callable]

            template.onPage = begin_page

            def end_page(
                canvas: Canvas,
                doc: BaseDocTemplate,
                on_page_end: object = on_page_end,
            ) -> None:
                on_page_end(canvas, doc)  # ty: ignore[call-non-callable]
                self.draw_page(canvas)

            template.onPageEnd = end_page

    def record(
        self,
        canvas: Canvas,
        kind: str,
        plan_id: str,
        at: tuple[float, float] | None = None,
    ) -> None:
        """The `<onDraw>` callback: notes where a cue's line is drawn."""
        if plan_id in self.drawn or any(p.plan.id == plan_id for p in self.page):
            return
        if at is None:
            info = canvas._curr_tx_info  # ty: ignore[unresolved-attribute]
            at = (info["cur_x"], info["cur_y"])
        x, y = canvas.absolutePosition(*at)
        self.page.append(Placed(self.plans[plan_id], canvas.getPageNumber(), x, y))

    def layout(self) -> PageLayout:
        """Stacks the plans of the page so far: those carried from the page
        before at the top, then each cue's plan level with its line or
        pushed down, carrying any that run off the bottom.
        """
        result = PageLayout()
        next_top = self.top
        for plan in self.carried:
            fits = next_top - plan.height >= self.bottom
            # A page takes at least one carried plan, so carrying ends.
            if result.carry or not (fits or next_top == self.top):
                result.carry.append(plan)
                continue
            result.plans.append((plan, next_top, f"▸{plan.label}", None))
            next_top -= plan.height + STACK_GAP
        for placed in sorted(self.page, key=lambda placed: -placed.y):
            line_top = placed.y + MARKER_FONT_SIZE
            top = min(line_top, next_top)
            label = placed.plan.label
            if result.carry or top - placed.plan.height < self.bottom:
                result.carry.append(placed.plan)
                label += "▸"
            else:
                leader = placed.y if top < line_top - 0.5 else None
                result.plans.append((placed.plan, top, label, leader))
                next_top = top - placed.plan.height - STACK_GAP
            result.markers.setdefault(round(placed.y, 1), []).append(label)
        return result

    def draw_page(self, canvas: Canvas) -> None:
        page = self.layout()
        for plan, top, label, leader in page.plans:
            self._draw_plan(canvas, plan, top, label)
            if leader is not None:
                self._leader(canvas, leader, top)
        for y, labels in page.markers.items():
            text = ",".join(labels)
            x = self.text_right + (TEXT_GAP - label_width(text)) / 2
            _draw_label(canvas, text, max(x, self.text_right + 0.3), y)
        self.page = []
        self.carried = page.carry

    def _draw_plan(
        self, canvas: Canvas, plan: MarginItem, top: float, label: str
    ) -> None:
        self.drawn.add(plan.id)
        canvas.saveState()
        canvas.translate(self.plan_x, top - plan.height)
        if isinstance(plan, MarginNote):
            draw_margin_note(canvas, plan, label)
        else:
            draw_margin_plan(canvas, self.blocking, plan.group, plan.numbers, label)
        canvas.restoreState()

    def _leader(self, canvas: Canvas, y: float, top: float) -> None:
        """A hairline from a cue's marker down to its pushed-down plan."""
        canvas.saveState()
        canvas.setStrokeGray(LEADER_GREY)
        canvas.setLineWidth(LEADER_WIDTH)
        x = self.text_right + TEXT_GAP / 2
        path = canvas.beginPath()
        path.moveTo(x, y - 1)
        path.lineTo(x, top - NUMBER_FONT_SIZE / 2)
        path.lineTo(self.plan_x, top - NUMBER_FONT_SIZE / 2)
        canvas.drawPath(path, stroke=1, fill=0)
        canvas.restoreState()
