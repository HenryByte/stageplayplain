"""PROTOTYPE, throwaway: how are crowded spots drawn on a plan?

At plan size a 4 pt circle covers ~1-1.5 m of stage, so a seated actor, two
people side by side or three props on a table collide. Three structurally
different answers, each drawn at scene-plan size (34 x 30 mm, everything in
ink) and margin-plan size (27 x 24 mm, look C of the movement prototype):

    A  Spread: symbols are pushed apart until nothing overlaps (props give way
       before cast, grey before ink); a displaced symbol gets a hairline to a
       dot at its true spot. Riders sit around their carrier.
    B  Merge: symbols that would overlap merge into one pill at their spot,
       listing members (cast initials, then prop numbers); facing ticks are
       dropped inside a pill. Riders join their carrier's pill.
    C  Layer: nothing moves. Fixed z-order (props under cast, grey under
       arrows and ghosts under ink) and a white halo round every symbol, so
       an overlap reads as one thing standing on another. Riders become small
       tabs on their carrier's rim.

In every variant arrows and ghosts are drawn above grey entities and below
ink ones.

    uv run python screenplain/export/prototype_plans/crowded.py

Writes build/prototype_plans/crowded.pdf: one page per case, real size row
then 2.5x.
"""

import math
import sys
from pathlib import Path

from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from screenplain import fse
from screenplain.export import stageplay_pdf
from screenplain.export.prototype_plans.movement import Group, arrow
from screenplain.export.prototype_plans.run import (
    Cast,
    Entrance,
    Frame,
    Mark,
    On,
    Prop,
    With,
    draw_stage,
    entities,
    facing_angle,
    initials,
)
from screenplain.parsers import fountain

HERE = Path(__file__).parent
OUT = HERE.parents[2] / "build" / "prototype_plans"
R, S = 4, 2.5  # cast radius, prop half-side (pt)
GREY = 0.68
VARIANTS = {  # round 1 was {"A": "Spread + leaders", "B": ..., "C": "Layer, no moving"}
    "B": "Merge, uncapped",
    "B1": "Merge capped + layer",
    "B2": "Merge capped + spread",
}
CAP = R  # merge only when centres are within this of the seed (pt)
SIZES = {"scene": (34 * mm, 30 * mm, 6), "margin": (27 * mm, 24 * mm, 4)}


class Sym:
    def __init__(self, eid, kind, at, gray, label, angle=None, carrier=None):
        self.id, self.kind, self.true, self.gray = eid, kind, at, gray
        self.pos, self.label, self.angle, self.carrier = at, label, angle, carrier
        self.ghost = False

    @property
    def r(self):
        return R if self.kind == "cast" else S * 1.3

    @property
    def weight(self):  # how readily it gives way when spreading
        w = 0.25 if self.kind == "cast" else 0.75
        return w * (0.4 if self.gray == 0 else 1)


# --- what to draw -------------------------------------------------------------


def symbols(b, f, state, cue, ink, ghosts=()):
    nums = {p.id: i for i, p in enumerate(entities(b, Prop), 1)}
    out = []
    for e in entities(b, Prop) + entities(b, Cast):
        pt = b.point_at(e.id, cue)
        if pt is None:
            continue
        w = state.whereabouts(e.id)
        carrier = (
            w.prop if isinstance(w, On) else w.cast if isinstance(w, With) else None
        )
        is_cast = isinstance(e, Cast)
        out.append(
            Sym(
                e.id,
                "cast" if is_cast else "prop",
                f(pt),
                0 if ink(e.id) else GREY,
                initials(e) if is_cast else str(nums[e.id]),
                facing_angle(b, state, e.id, pt) if is_cast else None,
                carrier,
            )
        )
    for eid, pt in ghosts:
        e = b.entities[eid]
        s = Sym(
            eid,
            "cast" if isinstance(e, Cast) else "prop",
            f(pt),
            0.35,
            initials(e) if isinstance(e, Cast) else str(nums[eid]),
        )
        s.ghost = True
        out.append(s)
    return out


def riders_beside(syms, ring):
    """Place riders around their carrier at successive clock positions."""
    by_id = {s.id: s for s in syms if not s.ghost}
    count = {}
    for s in syms:
        if s.carrier and s.carrier in by_id:
            c = by_id[s.carrier]
            n = count.get(c.id, 0)
            count[c.id] = n + 1
            a = math.radians(135 + 50 * n)  # lower right, then round clockwise
            d = ring(c, s)
            s.pos = (c.pos[0] + d * math.sin(a), c.pos[1] + d * math.cos(a))


# --- the three variants -------------------------------------------------------


def spread(syms, box):
    riders_beside(syms, lambda c, s: c.r + s.r + 0.3)
    for s in syms:
        s.anchor = s.pos
    for it in range(600):
        moved = False
        for i, a in enumerate(syms):
            for b_ in syms[i + 1 :]:
                dx, dy = b_.pos[0] - a.pos[0], b_.pos[1] - a.pos[1]
                d = math.hypot(dx, dy)
                need = a.r + b_.r + 0.6
                if d >= need:
                    continue
                if d < 1e-3:
                    ang = math.radians(60 + 97 * i)
                    dx, dy, d = math.cos(ang), math.sin(ang), 1
                push = (need - d) * 1.05 / d
                wa, wb = a.weight, b_.weight
                t = wa + wb
                a.pos = (a.pos[0] - dx * push * wa / t, a.pos[1] - dy * push * wa / t)
                b_.pos = (
                    b_.pos[0] + dx * push * wb / t,
                    b_.pos[1] + dy * push * wb / t,
                )
                moved = True
        for s in syms:  # stay in the box
            s.pos = (
                min(max(s.pos[0], s.r + 1), box[0] - s.r - 1),
                min(max(s.pos[1], s.r + 1), box[1] - s.r - 1),
            )
        if not moved:
            break


class Pill:
    def __init__(self, members):
        self.members = sorted(members, key=lambda s: (s.kind != "cast", s.label))
        casts = [m for m in self.members if m.kind == "cast"] or self.members
        self.pos = (
            sum(m.true[0] for m in casts) / len(casts),
            sum(m.true[1] for m in casts) / len(casts),
        )
        self.w = sum(stringWidth(m.label, "Helvetica-Bold", 4) for m in self.members)
        self.w += 2.2 * (len(self.members) - 1) + 3

    @property
    def half(self):
        return self.w / 2, 3.2


def merge(syms):
    """Union symbols whose footprints overlap; repeat with pill extents."""
    groups = [[s] for s in syms if not s.carrier or s.ghost]
    by_id = {s.id: s for s in syms}
    for s in syms:  # riders join their carrier
        if s.carrier and not s.ghost:
            root = s.carrier
            while by_id.get(root) and by_id[root].carrier:
                root = by_id[root].carrier
            for g in groups:
                if any(m.id == root for m in g):
                    g.append(s)
    for _ in range(4):
        shapes = [Pill(g) if len(g) > 1 else g[0] for g in groups]
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if groups[i] and groups[j] and _hit(shapes[i], shapes[j]):
                    groups[i] += groups[j]
                    groups[j] = []
                    merged = True
        groups = [g for g in groups if g]
        if not merged:
            break
    return [Pill(g) if len(g) > 1 else g[0] for g in groups]


def merge_capped(syms):
    """Pills only for near-coincident symbols and riders; never chained.

    Seeds are cast (ink first), then props. A symbol joins the first seed
    whose true centre is within CAP of its own; it never seeds-through.
    """
    by_id = {s.id: s for s in syms}

    def root(s):
        while s.carrier and not s.ghost and s.carrier in by_id:
            s = by_id[s.carrier]
        return s

    order = sorted(
        (s for s in syms if not (s.carrier and not s.ghost)),
        key=lambda s: (s.kind != "cast", s.gray != 0, s.ghost),
    )
    groups, home = [], {}
    for s in order:
        for g in groups:
            seed = g[0]
            if math.hypot(seed.true[0] - s.true[0], seed.true[1] - s.true[1]) < CAP:
                g.append(s)
                home[s.id] = g
                break
        else:
            groups.append([s])
            home[s.id] = groups[-1]
    for s in syms:
        if s.carrier and not s.ghost:
            home[root(s).id].append(s)
    out = []
    for g in groups:
        if len(g) == 1:
            out.append(g[0])
        else:
            p = Pill(g)
            p.pos = g[0].true  # sits on its seed, not a centroid
            out.append(p)
    return out


def spread_boxes(items, box):
    """Push items (symbols or pills) apart as boxes; ink gives way least."""
    for x in items:
        x.anchor = x.pos if isinstance(x, Pill) else x.true
        if not isinstance(x, Pill):
            x.pos = x.true

    def half(x):
        return x.half if isinstance(x, Pill) else (x.r, x.r)

    def weight(x):
        ink = _inked(x)
        cast = isinstance(x, Pill) or x.kind == "cast"
        return (0.25 if cast else 0.75) * (0.4 if ink else 1)

    for _ in range(600):
        moved = False
        for i, a in enumerate(items):
            for b_ in items[i + 1 :]:
                (ha, va), (hb, vb) = half(a), half(b_)
                dx, dy = b_.pos[0] - a.pos[0], b_.pos[1] - a.pos[1]
                ox = ha + hb + 0.6 - abs(dx)
                oy = va + vb + 0.6 - abs(dy)
                if ox <= 0 or oy <= 0:
                    continue
                wa, wb = weight(a), weight(b_)
                t = wa + wb
                if ox < oy:
                    sgn = 1 if dx >= 0 else -1
                    a.pos = (a.pos[0] - sgn * ox * wa / t, a.pos[1])
                    b_.pos = (b_.pos[0] + sgn * ox * wb / t, b_.pos[1])
                else:
                    sgn = 1 if dy >= 0 else -1
                    a.pos = (a.pos[0], a.pos[1] - sgn * oy * wa / t)
                    b_.pos = (b_.pos[0], b_.pos[1] + sgn * oy * wb / t)
                moved = True
        for x in items:
            h, v = half(x)
            x.pos = (
                min(max(x.pos[0], h + 1), box[0] - h - 1),
                min(max(x.pos[1], v + 1), box[1] - v - 1),
            )
        if not moved:
            break


def _ext(x):
    if isinstance(x, Pill):
        return x.pos, x.half
    return x.true, (x.r, x.r)


def _hit(a, b):
    (pa, ha), (pb, hb) = _ext(a), _ext(b)
    return (
        abs(pa[0] - pb[0]) < ha[0] + hb[0] + 0.4
        and abs(pa[1] - pb[1]) < ha[1] + hb[1] + 0.4
    )


def layer(syms):
    riders_beside(syms, lambda c, s: c.r + 0.6)
    for s in syms:
        if s.carrier and not s.ghost:
            s.tab = True
    # exactly coincident cast: coin-stack them a little
    seen = []
    for s in syms:
        if s.kind != "cast" or s.ghost:
            continue
        n = sum(
            1
            for t in seen
            if math.hypot(t.pos[0] - s.pos[0], t.pos[1] - s.pos[1]) < 1.5
        )
        s.pos = (s.pos[0] + 2 * n, s.pos[1] + 2 * n)
        seen.append(s)


# --- drawing ------------------------------------------------------------------


def draw_cast(c, s, halo):
    x, y = s.pos
    if halo:
        c.setStrokeGray(1)
        c.setLineWidth(1.6)
        c.circle(x, y, R, fill=0)
    c.setStrokeGray(s.gray)
    c.setFillGray(1)
    c.setLineWidth(0.5 if s.ghost else 0.7)
    if s.ghost:
        c.setDash(1, 1)
    c.circle(x, y, R, fill=1)
    c.setDash()
    if s.angle is not None:
        c.line(
            x + R * math.sin(s.angle),
            y + R * math.cos(s.angle),
            x + (R + 3) * math.sin(s.angle),
            y + (R + 3) * math.cos(s.angle),
        )
    c.setFillGray(s.gray)
    c.setFont("Helvetica" if s.ghost else "Helvetica-Bold", 4)
    c.drawCentredString(x, y - 1.4, s.label)


def draw_prop(c, s, halo):
    x, y = s.pos
    h = 2.0 if getattr(s, "tab", False) else S
    if halo:
        c.setStrokeGray(1)
        c.setLineWidth(1.6)
        c.rect(x - h, y - h, 2 * h, 2 * h)
    c.setStrokeGray(s.gray)
    c.setFillGray(1)
    c.setLineWidth(0.5)
    if s.ghost:
        c.setDash(1, 1)
    c.rect(x - h, y - h, 2 * h, 2 * h, fill=1)
    c.setDash()
    c.setFillGray(s.gray)
    c.setFont("Helvetica-Bold", 3.4 if h < S else 4)
    c.drawCentredString(x, y - (1.2 if h < S else 1.4), s.label)


def draw_leader(c, s):
    tx, ty = s.anchor
    x, y = s.pos
    d = math.hypot(x - tx, y - ty)
    if d < s.r + 0.8:
        return
    c.setStrokeGray(0.45 if s.gray == 0 else 0.75)
    c.setFillGray(0.45 if s.gray == 0 else 0.75)
    c.setLineWidth(0.25)
    c.line(tx, ty, x - (x - tx) * s.r / d, y - (y - ty) * s.r / d)
    c.circle(tx, ty, 0.55, stroke=0, fill=1)


def draw_pill(c, p, halo=False):
    (x, y), (hw, hh) = p.pos, p.half
    if halo:
        c.setStrokeGray(1)
        c.setLineWidth(1.6)
        c.roundRect(x - hw, y - hh, 2 * hw, 2 * hh, hh)
    c.setStrokeGray(0 if any(m.gray == 0 for m in p.members) else GREY)
    c.setFillGray(1)
    c.setLineWidth(0.6)
    c.roundRect(x - hw, y - hh, 2 * hw, 2 * hh, hh, fill=1)
    cx = x - hw + 1.5
    for i, m in enumerate(p.members):
        if i and m.kind == "prop" and p.members[i - 1].kind == "cast":
            c.setFillGray(0.5)
            c.setFont("Helvetica", 4)
            c.drawCentredString(cx - 1.1, y - 1.4, "·")
        c.setFillGray(m.gray if not m.ghost else 0.5)
        c.setFont("Helvetica-Oblique" if m.ghost else "Helvetica-Bold", 4)
        c.drawString(cx, y - 1.4, m.label)
        cx += stringWidth(m.label, "Helvetica-Bold", 4) + 2.2


class Plan(Flowable):
    def __init__(self, b, case, variant, k=1.0):
        super().__init__()
        self.b, self.case, self.v, self.k = b, case, variant, k
        self.W, self.H, self.pad = SIZES[case["size"]]

    def wrap(self, aw, ah):
        return self.W * self.k, self.H * self.k

    def draw(self):
        c, b, case = self.canv, self.b, self.case
        c.saveState()
        c.scale(self.k, self.k)
        c.setLineWidth(0.5)
        c.rect(0, 0, self.W, self.H)
        f = Frame(b, self.W, self.H, self.pad)
        draw_stage(c, f, audience=False)
        fixtures(c, b, f)
        step = b.timeline.steps[case["step"]]
        if case["size"] == "scene":
            g, ink, ghosts = None, lambda e: True, ()
        else:
            g = Group(b, case["step"])
            movers = g.movers | {  # picture changes with no path (picked up in place)
                e
                for e in g.after
                if g.after.onstage(e)
                and g.before.whereabouts(e) != g.after.whereabouts(e)
            }
            ink = lambda e: e in movers
            ghosts = [(e, p) for e, p in g.ghosts.items() if e in g.exits]
        syms = symbols(b, f, step.state, step.cue, ink, ghosts)
        layer_ = lambda s: (s.gray == 0 and not s.ghost, s.kind == "cast")

        def arrows():
            if not g:
                return
            for e, (solid, dashed) in g.paths.items():
                sp = [f(p) for p in solid]
                mover = next((s for s in syms if s.id == e and not s.ghost), None)
                ghost = next((s for s in syms if s.id == e and s.ghost), None)
                if sp and mover is not None and self.v != "C":
                    sp[-1] = mover.pos  # aim at where the symbol is drawn
                if sp and ghost is not None and self.v != "C":
                    sp[0] = ghost.pos
                arrow(
                    c,
                    sp,
                    R + 1 if e not in g.exits else 3,
                    R + 0.5 if ghost else 0,
                    dash=(0.6, 1.2),
                    lw=0.8,
                )
                if dashed:
                    arrow(
                        c,
                        [f(p) for p in dashed],
                        3,
                        R + 1 if not sp else 0,
                        dash=(1.5, 1.2),
                        gray=0.3,
                    )

        if self.v.startswith("B"):
            if self.v == "B":
                shapes = merge(syms)
            else:
                shapes = merge_capped(syms)
                if self.v == "B2":
                    spread_boxes(shapes, (self.W, self.H))
                    for x in shapes:
                        draw_leader(c, _as_leader(x))
                for x in shapes:
                    if not isinstance(x, Pill) and not x.ghost:
                        x.true = x.pos  # arrows aim at the drawn symbol
            halo = self.v == "B1"

            def place(e):
                for x in shapes:
                    ms = x.members if isinstance(x, Pill) else [x]
                    if any(m.id == e and not m.ghost for m in ms):
                        return x.pos

            for s_ in syms:
                s_.pos = place(s_.id) or s_.pos
            shapes.sort(key=lambda x: _inked(x))
            grey = [x for x in shapes if not _inked(x)]
            inked = [x for x in shapes if _inked(x)]
            for x in grey:
                _draw_one(c, x, halo)
            arrows()
            for x in inked:
                _draw_one(c, x, halo)
        else:
            if self.v == "A":
                spread(syms, (self.W, self.H))
            else:
                layer(syms)
            syms.sort(key=layer_)
            drew_arrows = False
            for s in syms:
                if not drew_arrows and layer_(s)[0]:
                    arrows()
                    drew_arrows = True
                if self.v == "A":
                    draw_leader(c, s)
                (draw_cast if s.kind == "cast" else draw_prop)(c, s, self.v == "C")
            if not drew_arrows:
                arrows()
        c.restoreState()


class _as_leader:
    def __init__(self, x):
        self.anchor, self.pos = x.anchor, x.pos
        self.r = x.half[0] if isinstance(x, Pill) else x.r
        self.gray = 0 if _inked(x) else GREY


def _inked(x):
    ms = x.members if isinstance(x, Pill) else [x]
    return any(m.gray == 0 and not m.ghost for m in ms)


def _draw_one(c, x, halo):
    if isinstance(x, Pill):
        draw_pill(c, x, halo)
    elif x.kind == "cast":
        draw_cast(c, x, halo)
    else:
        draw_prop(c, x, halo)


def fixtures(c, b, f):
    for m in entities(b, Mark):
        x, y = f(m.point)
        c.setStrokeGray(0.6)
        c.setLineWidth(0.4)
        c.line(x - 1.2, y - 1.2, x + 1.2, y + 1.2)
        c.line(x - 1.2, y + 1.2, x + 1.2, y - 1.2)
    for e in entities(b, Entrance):
        x, y = f(e.point)
        c.setFillGray(1)
        c.setStrokeGray(0)
        c.setLineWidth(0.5)
        p = c.beginPath()
        p.moveTo(x - 2, y - 2)
        p.lineTo(x + 2, y - 2)
        p.lineTo(x, y + 1.6)
        p.close()
        c.drawPath(p, fill=1)


# --- wiring -------------------------------------------------------------------


def load(name):
    with open(HERE / name) as fh:
        return fse.process(fountain.parse(fh))


def find(b, text):
    for i, s in enumerate(b.timeline.steps):
        if any(text in d.text for d in s.directives):
            return i
    raise KeyError(text)


def cases():
    tea, ham = load("crowded.fountain"), load("hamlet-round.fountain")
    return [
        (
            tea,
            dict(
                size="scene",
                step=find(tea, "PRESET jack"),
                title="Tea, scene plan: Gwendolen in the armchair (3) with her "
                "diary; Jack and Cecily on the settee (1); three things on the "
                "tea table; Algernon at the table with his cigarette case; Lane "
                "beside him.",
            ),
        ),
        (
            ham,
            dict(
                size="scene",
                step=find(ham, "PRESET first-gravedigger pos"),
                title="Churchyard, scene plan: the skull at grave under the "
                "gravedigger, who holds the spade.",
            ),
        ),
        (
            tea,
            dict(
                size="margin",
                step=find(tea, "MOVE algernon"),
                title="Margin: Algernon crosses to stand behind the settee pair.",
            ),
        ),
        (
            tea,
            dict(
                size="margin",
                step=find(tea, "EXIT lane"),
                title="Margin: Lane exits; his ghost is beside Algernon's old spot "
                "and the tea table.",
            ),
        ),
        (
            tea,
            dict(
                size="margin",
                step=find(tea, "MOVE jack"),
                title="Margin: Jack crosses into Gwendolen and the armchair; his "
                "arrow runs under Cecily's neighbourhood.",
            ),
        ),
        (
            tea,
            dict(
                size="margin",
                step=find(tea, "SET muffins"),
                title="Margin: muffins handed from the table to Jack (rider "
                "changes carrier) in the armchair crowd.",
            ),
        ),
        (
            ham,
            dict(
                size="margin",
                step=find(ham, "MOVE pos=graveside"),
                title="Margin: Hamlet moves to graveside, onto the skull.",
            ),
        ),
        (
            ham,
            dict(
                size="margin",
                step=find(ham, "SET skull with=hamlet"),
                title="Margin: Hamlet picks up the skull.",
            ),
        ),
    ]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    settings = stageplay_pdf.StagePlaySettings()
    h1, p = settings.scene_style, settings.prose_style
    story = [
        Paragraph("Crowded spots, round 2: capped merge", h1),
        Paragraph(
            "B: round-1 merge, uncapped (pills chain). B1: pills only for symbols "
            "whose centres are within one cast radius (4 pt) of a seed, plus riders "
            "with their carrier; never chained; the pill sits on its seed; "
            "remaining overlaps layered with a white halo. B2: the same pills; "
            "remaining overlaps pushed apart as boxes, hairline to the true spot. "
            "Round 1 (A spread, C layer): set VARIANTS to A, B, C. Prop numbers: Tea 1 settee, 2 armchair, "
            "3 tea table, 4 teapot, 5 sandwiches, 6 muffins, 7 cigarette case, "
            "8 diary. Churchyard: 1 spade, 2 skull, 3 lantern.",
            p,
        ),
        PageBreak(),
    ]
    for b, case in cases():
        story.append(Paragraph(case["title"], p))
        story.append(Spacer(1, 2 * mm))
        labels = [Paragraph(f"<b>{k}</b> {v}", p) for k, v in VARIANTS.items()]
        t = Table(
            [labels, [Plan(b, case, v) for v in VARIANTS]], colWidths=[45 * mm] * 3
        )
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story += [Paragraph("Real size:", p), t, Spacer(1, 3 * mm)]
        k = 2.5
        big = [Plan(b, case, v, k) for v in VARIANTS]
        cw = SIZES[case["size"]][0] * k + 4 * mm
        t = Table([labels[:2], big[:2], labels[2:], big[2:]], colWidths=[cw] * 2)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story += [Paragraph(f"{k}x:", p), t, PageBreak()]
    doc = SimpleDocTemplate(
        str(OUT / "crowded.pdf"),
        pagesize=(settings.page_width, settings.page_height),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    doc.build(story)
    print(OUT / "crowded.pdf", file=sys.stderr)


if __name__ == "__main__":
    main()
