"""PROTOTYPE, throwaway: what does a plan look like?

Three structurally different scene-plan variants (A, B, C), drawn from real
`Blocking` data and dropped under each scene heading of the real stage-play
PDF. Placement (in the text column, under the heading) is NOT the question
here; that is "Where do scene plans sit in each PDF layout?".

    uv run python screenplain/export/prototype_plans/run.py

Writes build/prototype_plans/compare.pdf (every scene, all variants, at real
size) and build/prototype_plans/<fixture>-<variant>.pdf (in context).
"""

import math
import sys
from pathlib import Path

from reportlab.lib.units import mm
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from screenplain import fse
from screenplain.export import stageplay_pdf
from screenplain.fse.model import (
    At,
    Bearing,
    Cast,
    Entrance,
    Mark,
    Moving,
    On,
    Point,
    Prop,
    Toward,
    With,
)
from screenplain.parsers import fountain
from screenplain.stageplay import to_stageplay

HERE = Path(__file__).parent
OUT = HERE.parents[2] / "build" / "prototype_plans"
FIXTURES = ["hamlet-round", "parlour-proscenium", "court-traverse"]
VARIANTS = {
    "A": "Numbered key (technical ground plan)",
    "B": "Small plan + cast/prop table",
    "C": "Labelled sketch, no key",
    "D": "A's drawing at B's size, right-hand side",
}


# --- data helpers ----------------------------------------------------------


def point_of(blocking, state, eid, seen=()):
    w = state.whereabouts(eid)
    if isinstance(w, At):
        return blocking.resolve(w.location)
    if isinstance(w, Moving):
        return blocking.resolve(w.move.origin)
    if isinstance(w, (On, With)) and eid not in seen:
        return point_of(
            blocking, state, w.prop if isinstance(w, On) else w.cast, (*seen, eid)
        )
    return None


def facing_angle(blocking, state, eid, at):
    f = state.facing(eid)
    if isinstance(f, Bearing):
        return math.radians(f.degrees)
    if isinstance(f, Toward):
        target = (
            blocking.resolve(f.location)
            if not isinstance(f.location, Point)
            else f.location
        )
        if hasattr(f.location, "id") and f.location.id in state:
            target = point_of(blocking, state, f.location.id) or target
        return math.atan2(target.x - at.x, target.y - at.y)
    return None


def name(entity):
    if isinstance(entity, Cast):
        return (entity.character_cue or entity.id.replace("-", " ")).title()
    return entity.label or entity.id.replace("-", " ")


def initials(entity):
    words = name(entity).split()
    return (
        "".join(w[0] for w in words[:2]).upper()
        if len(words) > 1
        else words[0][:2].upper()
    )


def entities(blocking, kind):
    return [e for e in blocking.entities.values() if isinstance(e, kind)]


# --- geometry ---------------------------------------------------------------


class Frame:
    """Maps stage coordinates into a w x h box, audience at the bottom."""

    def __init__(self, blocking, w, h, pad):
        st = blocking.stage
        hx = st.radius if st.radius is not None else st.width / 2
        hy = st.radius if st.radius is not None else st.depth / 2
        xs = [-hx, hx] + [e.point.x for e in entities(blocking, Entrance)]
        ys = [-hy, hy] + [e.point.y for e in entities(blocking, Entrance)]
        self.minx, self.maxx, self.miny, self.maxy = min(xs), max(xs), min(ys), max(ys)
        self.s = min(
            (w - 2 * pad) / (self.maxx - self.minx),
            (h - 2 * pad) / (self.maxy - self.miny),
        )
        self.ox = pad + (w - 2 * pad - self.s * (self.maxx - self.minx)) / 2
        self.oy = pad + (h - 2 * pad - self.s * (self.maxy - self.miny)) / 2
        self.hx, self.hy, self.stage = hx, hy, st

    def __call__(self, p):
        return self.ox + (p.x - self.minx) * self.s, self.oy + (
            p.y - self.miny
        ) * self.s


def draw_stage(c, f, fill=0.94, audience=True, font=("Helvetica", 5)):
    st = f.stage
    x0, y0 = f(Point(-f.hx, -f.hy))
    x1, y1 = f(Point(f.hx, f.hy))
    c.setFillGray(fill)
    c.setStrokeGray(0)
    c.setLineWidth(0.6)
    if st.type == "flexible":
        c.setDash(2, 2)
    if st.radius is not None:
        cx, cy = f(Point(0, 0))
        c.circle(cx, cy, st.radius * f.s, fill=1)
    else:
        c.rect(x0, y0, x1 - x0, y1 - y0, fill=1)
    c.setDash()
    if not audience:
        return
    c.setFillGray(0.45)
    c.setFont(*font)
    sides = {
        "proscenium": ["S"],
        "traverse": ["S", "N"],
        "round": ["S"],
        "flexible": [],
    }[st.type]
    for side in sides:
        y = y0 - 7 if side == "S" else y1 + 3
        if st.radius is not None:
            y = f(Point(0, -st.radius))[1] - 7
        c.drawCentredString(
            (x0 + x1) / 2, y, "AUDIENCE" if st.type != "round" else "FRONT"
        )


# --- variant A: numbered key ------------------------------------------------


class PlanA(Flowable):
    W, H = 60 * mm, 42 * mm
    PER_LINE, PAD, KEY_FONT = 3, 8, 5.5

    def __init__(self, blocking, state):
        super().__init__()
        self.b, self.state = blocking, state
        self.props = [p for p in entities(blocking, Prop) if state.onstage(p.id)]
        self.off = [
            e for e in entities(blocking, (Cast, Prop)) if not state.onstage(e.id)
        ]
        self.key_lines = -(-len(self.props) // self.PER_LINE) + (1 if self.off else 0)

    def wrap(self, aw, ah):
        return self.W, self.H + self.key_lines * 7

    def draw(self):
        c, b, st = self.canv, self.b, self.state
        kh = self.key_lines * 7
        c.saveState()
        c.translate(0, kh)
        f = Frame(b, self.W, self.H, self.PAD)
        c.setStrokeGray(0)
        c.setLineWidth(0.5)
        c.rect(0, 0, self.W, self.H)
        draw_stage(c, f)
        c.setFont("Helvetica", 4.5)
        for m in entities(b, Mark):
            x, y = f(m.point)
            c.setStrokeGray(0.5)
            c.line(x - 1.5, y - 1.5, x + 1.5, y + 1.5)
            c.line(x - 1.5, y + 1.5, x + 1.5, y - 1.5)
            c.setFillGray(0.5)
            c.drawString(x + 2, y - 4, m.id)
        for e in entities(b, Entrance):
            x, y = f(e.point)
            c.setFillGray(1)
            c.setStrokeGray(0)
            p = c.beginPath()
            p.moveTo(x - 2.5, y - 2.5)
            p.lineTo(x + 2.5, y - 2.5)
            p.lineTo(x, y + 2)
            p.close()
            c.drawPath(p, fill=1)
            c.setFillGray(0)
            c.drawCentredString(x, y - 7.5, e.id)
        # props: numbered squares; attached ones next to their carrier
        for i, p in enumerate(self.props, 1):
            pt = point_of(b, st, p.id)
            x, y = f(pt)
            if isinstance(st.whereabouts(p.id), (On, With)):
                x, y = x + 4 + 4 * (i % 2), y - 4
            c.setFillGray(1)
            c.setStrokeGray(0)
            c.rect(x - 2.5, y - 2.5, 5, 5, fill=1)
            c.setFillGray(0)
            c.setFont("Helvetica-Bold", 4)
            c.drawCentredString(x, y - 1.4, str(i))
        for cast in entities(b, Cast):
            pt = point_of(b, st, cast.id)
            if pt is None:
                continue
            x, y = f(pt)
            a = facing_angle(b, st, cast.id, pt)
            c.setFillGray(1)
            c.setStrokeGray(0)
            c.setLineWidth(0.7)
            c.circle(x, y, 4, fill=1)
            if a is not None:
                c.line(
                    x + 4 * math.sin(a),
                    y + 4 * math.cos(a),
                    x + 7 * math.sin(a),
                    y + 7 * math.cos(a),
                )
            c.setFillGray(0)
            c.setFont("Helvetica-Bold", 4)
            c.drawCentredString(x, y - 1.4, initials(cast))
        c.restoreState()
        # key under the box
        c.setFont("Helvetica", self.KEY_FONT)
        y = kh - 6
        line = []
        for i, p in enumerate(self.props, 1):
            w = st.whereabouts(p.id)
            extra = f" (on {self.b.entities[w.prop].id})" if isinstance(w, On) else ""
            extra = (
                f" (with {initials(self.b.entities[w.cast])})"
                if isinstance(w, With)
                else extra
            )
            line.append(f"{i} {name(p)}{extra}")
            if len(line) == self.PER_LINE:
                c.drawString(0, y, "   ".join(line))
                y, line = y - 7, []
        if line:
            c.drawString(0, y, "   ".join(line))
            y -= 7
        if self.off:
            c.setFillGray(0.4)
            c.drawString(0, y, "Off: " + ", ".join(name(e) for e in self.off))


class PlanD(PlanA):
    """A's drawing at B's plan size; key one per line; right-aligned."""

    W, H = 34 * mm, 30 * mm
    PER_LINE, PAD, KEY_FONT = 1, 6, 5

    def __init__(self, blocking, state):
        super().__init__(blocking, state)
        self.hAlign = "RIGHT"
        # one offstage name per line too, so the key fits the plan width
        self.key_lines += max(len(self.off) - 1, 0)

    def draw(self):
        off, self.off = self.off, []
        super().draw()
        self.off = off
        if off:
            c = self.canv
            c.setFillGray(0.4)
            c.setFont("Helvetica", self.KEY_FONT)
            y = len(off) * 7 - 6
            c.drawString(0, y, "Off: " + name(off[0]))
            for e in off[1:]:
                y -= 7
                c.drawString(13, y, name(e))


# --- variant B: small plan + table -----------------------------------------


class PlanB(Flowable):
    PW, H = 34 * mm, 30 * mm

    def __init__(self, blocking, state, width):
        super().__init__()
        self.b, self.state, self.W = blocking, state, width
        self.rows = [e for e in entities(blocking, Cast)] + [
            e for e in entities(blocking, Prop)
        ]
        self.Hh = max(self.H, len(self.rows) * 7 + 4)

    def wrap(self, aw, ah):
        return self.W, self.Hh

    def where(self, e):
        w = self.state.whereabouts(e.id)
        if isinstance(w, At):
            loc = w.location
            return loc.id if hasattr(loc, "id") else f"{loc.x:g},{loc.y:g}"
        if isinstance(w, On):
            return f"on {name(self.b.entities[w.prop])}"
        if isinstance(w, With):
            return f"with {name(self.b.entities[w.cast])}"
        return "off"

    def draw(self):
        c, b, st = self.canv, self.b, self.state
        f = Frame(b, self.PW, self.H, 4)
        c.saveState()
        c.translate(0, self.Hh - self.H)
        draw_stage(c, f, fill=1, audience=False)
        # entrances as gaps/ticks on the outline
        for e in entities(b, Entrance):
            x, y = f(e.point)
            c.setStrokeGray(1)
            c.setLineWidth(2.5)
            c.circle(x, y, 0.1)
            c.setStrokeGray(0)
            c.setLineWidth(0.4)
            c.line(x - 2, y, x + 2, y)
        # props: grey diamonds, letters
        letters = {}
        for i, p in enumerate([p for p in entities(b, Prop) if st.onstage(p.id)]):
            letters[p.id] = chr(ord("a") + i)
            pt = point_of(b, st, p.id)
            x, y = f(pt)
            if isinstance(st.whereabouts(p.id), (On, With)):
                x, y = x + 2.5, y + 2.5
            c.setFillGray(0.6)
            p_ = c.beginPath()
            p_.moveTo(x, y - 1.8)
            p_.lineTo(x + 1.8, y)
            p_.lineTo(x, y + 1.8)
            p_.lineTo(x - 1.8, y)
            p_.close()
            c.drawPath(p_, fill=1, stroke=0)
        for cast in entities(b, Cast):
            pt = point_of(b, st, cast.id)
            if pt is None:
                continue
            x, y = f(pt)
            c.setFillGray(0)
            c.circle(x, y, 1.6, fill=1)
            a = facing_angle(b, st, cast.id, pt)
            if a is not None:
                ex, ey = x + 4.5 * math.sin(a), y + 4.5 * math.cos(a)
                c.setLineWidth(0.5)
                c.line(x, y, ex, ey)
                c.circle(ex, ey, 0.5, fill=1)
            c.setFont("Helvetica-Bold", 4)
            c.drawString(x + 2.2, y + 1, initials(cast))
        c.restoreState()
        # table
        tx = self.PW + 4 * mm
        y = self.Hh - 6
        for e in self.rows:
            on = st.onstage(e.id)
            c.setFillGray(0 if on else 0.6)
            c.setFont("Helvetica-Bold" if isinstance(e, Cast) else "Helvetica", 6)
            tag = initials(e) if isinstance(e, Cast) else letters.get(e.id, "")
            c.drawString(tx, y, tag)
            c.setFont("Helvetica", 6)
            c.drawString(tx + 12, y, name(e))
            c.setFont("Helvetica-Oblique", 6)
            c.drawString(tx + 70, y, self.where(e))
            y -= 7


# --- variant C: labelled sketch --------------------------------------------


class PlanC(Flowable):
    W, H = 80 * mm, 55 * mm

    def __init__(self, blocking, state):
        super().__init__()
        self.b, self.state = blocking, state

    def wrap(self, aw, ah):
        return self.W, self.H

    def draw(self):
        c, b, st = self.canv, self.b, self.state
        f = Frame(b, self.W, self.H, 14)
        draw_stage(c, f, fill=0.97, font=("Helvetica-Oblique", 5.5))
        c.setFont("Helvetica", 5)
        for m in entities(b, Mark):
            x, y = f(m.point)
            c.setFillGray(0.7)
            c.circle(x, y, 0.8, fill=1, stroke=0)
            c.drawString(x + 2, y + 1.5, m.id)
        for e in entities(b, Entrance):
            x, y = f(e.point)
            cx, cy = f(Point(0, 0))
            d = math.hypot(cx - x, cy - y) or 1
            ux, uy = (cx - x) / d, (cy - y) / d
            c.setStrokeGray(0.3)
            c.setLineWidth(0.5)
            c.line(x - 5 * ux, y - 5 * uy, x + 3 * ux, y + 3 * uy)
            c.setFillGray(0.3)
            c.drawCentredString(x - 9 * ux, y - 9 * uy - 2, e.id)
        for p in entities(b, Prop):
            w = st.whereabouts(p.id)
            if not st.onstage(p.id) or not isinstance(w, At):
                continue
            x, y = f(point_of(b, st, p.id))
            c.setStrokeGray(0.2)
            c.setFillGray(1)
            c.roundRect(x - 4, y - 2.5, 8, 5, 1, fill=1)
            on = [b.entities[q] for q in st.carried(p.id)]
            c.setFillGray(0.2)
            c.setFont("Helvetica-Oblique", 5.5)
            label = name(p) + (" + " + ", ".join(name(q) for q in on) if on else "")
            c.drawString(x + 5, y - 6, label)
        for cast in entities(b, Cast):
            pt = point_of(b, st, cast.id)
            if pt is None:
                continue
            x, y = f(pt)
            a = facing_angle(b, st, cast.id, pt)
            c.setFillGray(0)
            if a is not None:
                p_ = c.beginPath()
                p_.moveTo(x + 6 * math.sin(a), y + 6 * math.cos(a))
                p_.lineTo(x + 2.5 * math.sin(a + 1.9), y + 2.5 * math.cos(a + 1.9))
                p_.lineTo(x + 2.5 * math.sin(a - 1.9), y + 2.5 * math.cos(a - 1.9))
                p_.close()
                c.drawPath(p_, fill=1, stroke=0)
            c.circle(x, y, 2.4, fill=1)
            c.setFont("Helvetica-Bold", 6)
            c.drawString(x + 4, y + 2, name(cast).upper())
            held = [b.entities[q] for q in st.carried(cast.id)]
            if held:
                c.setFont("Helvetica-Oblique", 5.5)
                c.drawString(x + 4, y - 4.5, "+ " + ", ".join(name(q) for q in held))


def make_plan(variant, blocking, state, width):
    if variant == "A":
        return PlanA(blocking, state)
    if variant == "D":
        return PlanD(blocking, state)
    if variant == "B":
        return PlanB(blocking, state, width)
    return PlanC(blocking, state)


# --- wiring -----------------------------------------------------------------


def load(fixture):
    with open(HERE / f"{fixture}.fountain") as fh:
        screenplay = fountain.parse(fh)
    return screenplay, fse.process(screenplay)


def heading(scene):
    bd = scene.boundary
    return str(bd.line if hasattr(bd, "line") else bd.text)


def in_context(fixture, variant):
    screenplay, blocking = load(fixture)
    play = to_stageplay(screenplay)
    settings = stageplay_pdf.StagePlaySettings()
    scenes = iter(blocking.scenes)
    original = stageplay_pdf._body_story

    def body_story(play, settings):
        story = []
        for flowable in original(play, settings):
            story.append(flowable)
            if getattr(flowable, "style", None) is settings.scene_style:
                story.append(
                    make_plan(
                        variant, blocking, next(scenes).preset, settings.frame_width
                    )
                )
                story.append(Spacer(1, 4 * mm))
        return story

    stageplay_pdf._body_story = body_story
    try:
        with open(OUT / f"{fixture}-{variant}.pdf", "wb") as out:
            stageplay_pdf.to_pdf(play, out, settings=settings)
    finally:
        stageplay_pdf._body_story = original


def compare():
    settings = stageplay_pdf.StagePlaySettings()
    style = settings.scene_style
    story = []
    for fixture in FIXTURES:
        _, blocking = load(fixture)
        for scene in blocking.scenes:
            story.append(Paragraph(f"{fixture}: {heading(scene)}", style))
            for v, label in VARIANTS.items():
                story.append(Paragraph(f"<b>{v}</b>: {label}", settings.prose_style))
                story.append(Spacer(1, 2 * mm))
                story.append(make_plan(v, blocking, scene.preset, settings.frame_width))
                story.append(Spacer(1, 3 * mm))
            story.append(PageBreak())
    doc = SimpleDocTemplate(
        str(OUT / "compare.pdf"),
        pagesize=(settings.page_width, settings.page_height),
        leftMargin=settings.left_margin,
        rightMargin=settings.right_margin,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    doc.build(story)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    compare()
    for fixture in FIXTURES:
        for v in VARIANTS:
            in_context(fixture, v)
    print("\n".join(sorted(str(p) for p in OUT.glob("*.pdf"))), file=sys.stderr)
