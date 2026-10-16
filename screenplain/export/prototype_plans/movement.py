"""PROTOTYPE, throwaway: how is movement drawn on a margin plan?

Margin plans are ~27 x 24 mm, drawing-only, read against the scene key. Each
plan shows its step group's end state with movement drawn from the state
before the group. Two questions, two axes:

Look (how movers stand out, what else is drawn):
    A  Movers filled: full state; movers black with white initials, a dashed
       ghost where they started, solid arrow.
    B  Movers only: stage, marks, entrances, and only what moved (plus what
       rides with it); ghost + arrow.
    C  Others greyed: full state; everything that did not move in light grey;
       movers in black ink; dotted path with an arrowhead, no ghost.
    D  Plain + arrows: full state, nobody emphasised; an arrow only (a ghost
       only for exits, else nothing would show who left).

Open moves (MOVE until=arrive ... VIA ... ARRIVE), shown in every look:
    P1 Each event: a plan at the start, at each VIA and at ARRIVE; the part
       still to come is dashed to the destination.
    P2 Arrive only: no plan at start or VIA; ARRIVE draws the whole route.
    P3 Start only: the start plan draws the whole planned route (VIAs
       included, read ahead); no plan at VIA or ARRIVE.

    uv run python screenplain/export/prototype_plans/movement.py

Writes build/prototype_plans/movement.pdf: one page per case (real size row,
then 2x), then one page per look for the open-move policies.
"""

import math
import sys
from pathlib import Path

from reportlab.lib.units import mm
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
from screenplain.export.prototype_plans.run import (
    Cast,
    Entrance,
    Frame,
    Mark,
    Moving,
    On,
    Prop,
    With,
    draw_stage,
    entities,
    facing_angle,
    initials,
)
from screenplain.fse.directives import Enter, Exit
from screenplain.parsers import fountain

HERE = Path(__file__).parent
OUT = HERE.parents[2] / "build" / "prototype_plans"
W, H, PAD = 27 * mm, 24 * mm, 4
R = 4  # circle radius, pt (fixed font size, as the scene plan)
LOOKS = {
    "A": "Movers filled",
    "B": "Movers only",
    "C": "Others greyed",
    "D": "Plain + arrows",
}
POLICIES = {
    "P1": "Each event (start, VIA, ARRIVE)",
    "P2": "Arrive only, whole route",
    "P3": "Start only, whole planned route",
}


# --- movement data ----------------------------------------------------------


class Group:
    """One step group's movement: who moved, along which path."""

    def __init__(self, blocking, index, policy="P1"):
        tl = blocking.timeline
        self.b = blocking
        self.step = tl.steps[index]
        self.before = tl.steps[index - 1].state if index else tl.initial
        self.after = self.step.state
        prev_cue = tl.steps[index - 1].cue if index else None
        self.text = "; ".join(d.text for d in self.step.directives)
        self.paths = {}  # entity -> (solid points, dashed points)
        self.ghosts = {}  # entity -> point where it started
        self.exits = set()
        self.empty = False  # under this policy, no plan at all

        def pt_before(e):
            if not self.before.onstage(e):
                return None
            return blocking.point_at(e, prev_cue) if prev_cue else None

        def pt_after(e):
            return blocking.point_at(e, self.step.cue)

        enters = {d.subject: d for d in self.step.directives if isinstance(d, Enter)}
        exits = {d.subject: d for d in self.step.directives if isinstance(d, Exit)}
        open_events = []
        for e in self.after:
            bp, ap = pt_before(e), pt_after(e)
            rides = isinstance(self.after.whereabouts(e), (On, With))
            wa, wb = self.after.whereabouts(e), self.before.whereabouts(e)
            if wa == wb:
                continue  # unchanged (riders and those mid-cross included)
            if bp is None and ap is not None:
                d = enters.get(e)
                if d and d.from_ and not rides:
                    self.paths[e] = ([blocking.resolve(_place(d.from_)), ap], [])
                else:
                    self.paths[e] = ([], [])  # appears / rides in
            elif bp is not None and ap is None:
                d = exits.get(e)
                self.exits.add(e)
                self.ghosts[e] = bp
                if d and d.via:
                    self.paths[e] = ([bp, blocking.resolve(_place(d.via))], [])
                else:
                    self.paths[e] = ([], [])
            elif bp is not None and ap is not None and _far(bp, ap):
                if rides and isinstance(self.before.whereabouts(e), (On, With)):
                    self.paths[e] = ([], [])  # rides with its carrier
                    continue
                self.ghosts[e] = bp
                self.paths[e] = ([bp, ap], [])
                if isinstance(wa, Moving) or isinstance(wb, Moving):
                    open_events.append((e, wa, wb))
            elif isinstance(wa, Moving) and not isinstance(wb, Moving):
                open_events.append((e, wa, wb))  # starts, still at origin
                self.paths[e] = ([], [])
        self._open_moves(open_events, policy, index)

    def _open_moves(self, events, policy, index):
        b = self.b
        for e, wa, wb in events:
            start = isinstance(wa, Moving) and not isinstance(wb, Moving)
            arrive = isinstance(wb, Moving) and not isinstance(wa, Moving)
            move = (wa if isinstance(wa, Moving) else wb).move
            whole = [b.resolve(move.origin)]
            whole += [b.resolve(v.location) for v in _future_vias(b, e, index)]
            whole.append(b.resolve(move.destination))
            here = b.point_at(e, self.step.cue)
            if policy == "P1":
                solid = self.paths[e][0]
                if isinstance(wa, Moving):
                    self.paths[e] = (solid, [here, b.resolve(move.destination)])
            elif policy == "P2":
                if not arrive:
                    self._drop(e)
                else:
                    route = [b.resolve(move.origin)]
                    route += [b.resolve(v.location) for v in move.vias]
                    route.append(here)
                    self.paths[e] = (route, [])
                    self.ghosts[e] = route[0]
            elif policy == "P3":
                if not start:
                    self._drop(e)
                else:
                    self.paths[e] = ([], whole)
                    self.ghosts.pop(e, None)

    def _drop(self, e):
        self.paths.pop(e, None)
        self.ghosts.pop(e, None)
        if not self.paths:
            self.empty = True

    @property
    def movers(self):
        moved = set(self.paths)
        for e in list(moved):
            moved |= set(self.after.carried(e)) if self.after.onstage(e) else set()
        return moved


def _future_vias(b, e, index):
    """VIAs of the open move `e` is on (or starts) at step `index`, read ahead."""
    vias = []
    for step in b.timeline.steps[index:]:
        w = step.state.whereabouts(e)
        if not isinstance(w, Moving):
            break
        vias = list(w.move.vias)
    return vias


def _place(eid):
    from screenplain.fse.model import Place

    return Place(eid)


def _far(p, q):
    return math.hypot(p.x - q.x, p.y - q.y) > 1e-6


# --- drawing ----------------------------------------------------------------


def arrow(c, pts, gap_end=R + 1, gap_start=0, dash=None, head=True, gray=0, lw=0.6):
    if len(pts) < 2:
        return
    pts = list(pts)
    (x0, y0), (x1, y1) = pts[0], pts[1]
    d = math.hypot(x1 - x0, y1 - y0) or 1
    pts[0] = (x0 + (x1 - x0) * gap_start / d, y0 + (y1 - y0) * gap_start / d)
    (xa, ya), (xb, yb) = pts[-2], pts[-1]
    d = math.hypot(xb - xa, yb - ya) or 1
    if d <= gap_end + 1:
        return
    tip = (xb - (xb - xa) * gap_end / d, yb - (yb - ya) * gap_end / d)
    pts[-1] = tip
    c.saveState()
    c.setStrokeGray(gray)
    c.setFillGray(gray)
    c.setLineWidth(lw)
    if dash:
        c.setDash(*dash)
    p = c.beginPath()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    c.drawPath(p, stroke=1, fill=0)
    c.setDash()
    if head:
        a = math.atan2(tip[1] - ya, tip[0] - xa)
        h = c.beginPath()
        h.moveTo(*tip)
        h.lineTo(tip[0] - 3 * math.cos(a - 0.45), tip[1] - 3 * math.sin(a - 0.45))
        h.lineTo(tip[0] - 3 * math.cos(a + 0.45), tip[1] - 3 * math.sin(a + 0.45))
        h.close()
        c.drawPath(h, stroke=0, fill=1)
    c.restoreState()


class MarginPlan(Flowable):
    def __init__(self, blocking, group, look, scale=1.0):
        super().__init__()
        self.b, self.g, self.look, self.k = blocking, group, look, scale
        self.numbers = {p.id: i for i, p in enumerate(entities(blocking, Prop), 1)}

    def wrap(self, aw, ah):
        return W * self.k, H * self.k

    def draw(self):
        c, b, g, look = self.canv, self.b, self.g, self.look
        c.saveState()
        c.scale(self.k, self.k)
        c.setStrokeGray(0)
        c.setLineWidth(0.5)
        c.rect(0, 0, W, H)
        if g.empty:
            c.setFont("Helvetica-Oblique", 5)
            c.setFillGray(0.5)
            c.drawCentredString(W / 2, H / 2, "(no plan)")
            c.restoreState()
            return
        f = Frame(b, W, H, PAD)
        draw_stage(c, f, audience=False)
        self._fixtures(c, f)
        movers = g.movers
        st = g.after
        show = lambda e: look != "B" or e in movers
        ink = lambda e: 0 if look != "C" or e in movers else 0.68
        # ghosts
        for e, p in g.ghosts.items():
            if look == "C" and e not in g.exits:
                continue
            if look == "D" and e not in g.exits:
                continue
            x, y = f(p)
            c.setDash(1, 1)
            c.setStrokeGray(0.35)
            c.setLineWidth(0.5)
            if isinstance(b.entities[e], Cast):
                c.circle(x, y, R, fill=0)
                c.setDash()
                c.setFillGray(0.35)
                c.setFont("Helvetica", 3.5)
                c.drawCentredString(x, y - 1.2, initials(b.entities[e]))
            else:
                c.rect(x - 2.5, y - 2.5, 5, 5)
            c.setDash()
        # paths
        for e, (solid, dashed) in g.paths.items():
            sp = [f(p) for p in solid]
            dp = [f(p) for p in dashed]
            start_gap = (
                R + 0.5 if (look in "AB" or e in g.exits) and e in g.ghosts else 0
            )
            end_gap = R + 1 if e not in g.exits else 3
            if look == "C":
                arrow(c, sp, end_gap, start_gap, dash=(0.6, 1.2), lw=0.8)
            else:
                arrow(c, sp, end_gap, start_gap, head=not dp or True)
            if dp:
                arrow(
                    c,
                    dp,
                    3 if look != "B" else R + 1,
                    R + 1 if not sp else 0,
                    dash=(1.5, 1.2),
                    gray=0.3,
                )
        # props
        for p in entities(b, Prop):
            pt = b.point_at(p.id, g.step.cue)
            if pt is None or not show(p.id):
                continue
            x, y = f(pt)
            if isinstance(st.whereabouts(p.id), (On, With)):
                x, y = x + 4.5, y - 4.5
            filled = look == "A" and p.id in movers
            gray = ink(p.id)
            c.setStrokeGray(gray)
            c.setFillGray(0 if filled else 1)
            c.setLineWidth(0.5)
            c.rect(x - 2.5, y - 2.5, 5, 5, fill=1)
            c.setFillGray(1 if filled else gray)
            c.setFont("Helvetica-Bold", 4)
            c.drawCentredString(x, y - 1.4, str(self.numbers[p.id]))
        # cast
        for cast in entities(b, Cast):
            pt = b.point_at(cast.id, g.step.cue)
            if pt is None or not show(cast.id):
                continue
            x, y = f(pt)
            filled = look == "A" and cast.id in movers
            gray = ink(cast.id)
            a = facing_angle(b, st, cast.id, pt)
            c.setStrokeGray(gray)
            c.setFillGray(0 if filled else 1)
            c.setLineWidth(0.7)
            c.circle(x, y, R, fill=1)
            if a is not None:
                c.line(
                    x + R * math.sin(a),
                    y + R * math.cos(a),
                    x + (R + 3) * math.sin(a),
                    y + (R + 3) * math.cos(a),
                )
            c.setFillGray(1 if filled else gray)
            c.setFont("Helvetica-Bold", 4)
            c.drawCentredString(x, y - 1.4, initials(cast))
        c.restoreState()

    def _fixtures(self, c, f):
        b = self.b
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


# --- wiring -----------------------------------------------------------------


def load():
    with open(HERE / "movement.fountain") as fh:
        screenplay = fountain.parse(fh)
    return fse.process(screenplay)


def case_pages(b, styles):
    story = []
    steps = b.timeline.steps
    for i in range(1, len(steps)):
        g = Group(b, i)
        story.append(
            Paragraph(f"Case {i}: <font face='Courier'>{g.text}</font>", styles[0])
        )
        story.append(Spacer(1, 2 * mm))
        labels = [Paragraph(f"<b>{k}</b> {v}", styles[1]) for k, v in LOOKS.items()]
        real = [MarginPlan(b, g, k) for k in LOOKS]
        t = Table([labels, real], colWidths=[40 * mm] * 4)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(Paragraph("Real size (27 x 24 mm):", styles[1]))
        story.append(t)
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("2x:", styles[1]))
        big = [MarginPlan(b, g, k, 2) for k in LOOKS]
        t = Table(
            [[labels[0], labels[1]], big[:2], [labels[2], labels[3]], big[2:]],
            colWidths=[62 * mm] * 2,
        )
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)
        story.append(PageBreak())
    return story


def open_move_pages(b, styles):
    steps = b.timeline.steps
    idx = [
        i
        for i, s in enumerate(steps)
        if any(
            isinstance(s.state.whereabouts("mary"), Moving)
            or isinstance(steps[i - 1].state.whereabouts("mary"), Moving)
            for _ in [0]
        )
        and i
    ]
    story = []
    for look, lname in LOOKS.items():
        story.append(Paragraph(f"Open move, look {look} ({lname})", styles[0]))
        story.append(
            Paragraph(
                "Mary's cross to the table: MOVE until=arrive, then Arthur's move "
                "(a separate group, Mary in transit), then VIA, then ARRIVE. "
                "Rows: policy; columns: the step groups in order. Real size, then 2x.",
                styles[1],
            )
        )
        story.append(Spacer(1, 2 * mm))
        for scale in (1, 1.6):
            head = [Paragraph("", styles[1])] + [
                Paragraph(
                    f"<font face='Courier' size=6>{steps[i].directives[0].text}</font>",
                    styles[1],
                )
                for i in idx
            ]
            rows = [head]
            for p, pname in POLICIES.items():
                rows.append(
                    [Paragraph(f"<b>{p}</b> {pname}", styles[1])]
                    + [MarginPlan(b, Group(b, i, p), look, scale) for i in idx]
                )
            cw = (W * scale) + 3 * mm
            t = Table(rows, colWidths=[26 * mm] + [cw] * len(idx))
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(t)
            story.append(Spacer(1, 4 * mm))
        story.append(PageBreak())
    return story


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b = load()
    settings = stageplay_pdf.StagePlaySettings()
    styles = (settings.scene_style, settings.prose_style)
    story = case_pages(b, styles) + open_move_pages(b, styles)
    doc = SimpleDocTemplate(
        str(OUT / "movement.pdf"),
        pagesize=(settings.page_width, settings.page_height),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    doc.build(story)
    print(OUT / "movement.pdf", file=sys.stderr)


if __name__ == "__main__":
    main()
