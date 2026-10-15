"""PROTOTYPE, throwaway: how does the scene-plan key fill the space left of the drawing?

The scene plan is a block in the text column under the scene heading, with the
drawing (variant D) at the right edge. Two key layouts:

    A  columns, newspaper-style: block is as tall as the drawing unless the key
       overflows every column that fits
    B  one column: block grows as tall as the key

    uv run python screenplain/export/prototype_plans/key_layout.py

Writes build/prototype_plans/key-<fixture>-<A|B>.pdf (stage-play layout, in
context) and key-crowd-screenplay-<A|B>.pdf (screenplay layout).
"""

import sys

from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Spacer

from screenplain import fse
from screenplain.export import stageplay_pdf
from screenplain.export.prototype_plans import run
from screenplain.export.prototype_plans.run import On, PlanD, With, initials, name
from screenplain.parsers import fountain
from screenplain.stageplay import to_stageplay

FONT, SIZE, LEAD = "Helvetica", 7, 3.4 * mm
COL_W, GUTTER, GAP = 30 * mm, 3 * mm, 5 * mm


class Drawing(PlanD):
    """Variant D's drawing alone: no key underneath."""

    def __init__(self, blocking, state):
        super().__init__(blocking, state)
        self.props_for_key, self.off_for_key = self.props, self.off
        self.off, self.key_lines = [], 0

    def draw(self):
        # PlanA.draw also writes its own key below the box; clip it away
        c = self.canv
        c.saveState()
        path = c.beginPath()
        path.rect(-1, -1, self.W + 2, self.H + 2)
        c.clipPath(path, stroke=0, fill=0)
        run.PlanA.draw(self)
        c.restoreState()


def key_entries(d):
    out = []
    for i, p in enumerate(d.props_for_key, 1):
        w = d.state.whereabouts(p.id)
        extra = ""
        if isinstance(w, On):
            extra = f" (on {name(d.b.entities[w.prop])})"
        elif isinstance(w, With):
            extra = f" (with {initials(d.b.entities[w.cast])})"
        out.append((f"{i} {name(p)}{extra}", 0))
    for j, e in enumerate(d.off_for_key):
        out.append((("Off: " if j == 0 else "") + name(e), 0.45))
    return out


class ScenePlan(Flowable):
    def __init__(self, blocking, state, columns):
        super().__init__()
        self.d = Drawing(blocking, state)
        self.entries = key_entries(self.d)
        self.columns = columns

    def _lines(self, canv_width):
        # wrap long entries with a hanging indent to COL_W
        from reportlab.pdfbase.pdfmetrics import stringWidth

        lines = []
        for text, grey in self.entries:
            words, cur, first = text.split(), "", True
            for w in words:
                trial = (cur + " " + w).strip()
                indent = 0 if first else 3 * mm
                if cur and stringWidth(trial, FONT, SIZE) > COL_W - indent:
                    lines.append((cur, grey, 0 if first else 3 * mm))
                    cur, first = w, False
                else:
                    cur = trial
            lines.append((cur, grey, 0 if first else 3 * mm))
        return lines

    def wrap(self, aw, ah):
        self.aw = aw
        self.lines = self._lines(aw)
        dw, dh = self.d.wrap(aw, ah)
        if self.columns:
            ncols = int((aw - dw - GAP + GUTTER) // (COL_W + GUTTER))
            per = max(int(dh // LEAD), -(-len(self.lines) // ncols))
        else:
            per = len(self.lines)
        self.per = per
        self.h = max(dh, per * LEAD)
        return aw, self.h

    def draw(self):
        c = self.canv
        dw, dh = self.d.wrap(self.aw, self.h)
        c.saveState()
        c.translate(self.aw - dw, self.h - dh)
        self.d.canv = c
        self.d.draw()
        c.restoreState()
        c.setFont(FONT, SIZE)
        key_x0 = (
            self.aw
            - dw
            - GAP
            - (COL_W + GUTTER)
            * (
                int((self.aw - dw - GAP + GUTTER) // (COL_W + GUTTER))
                if self.columns
                else 1
            )
            + GUTTER
        )
        for n, (text, grey, indent) in enumerate(self.lines):
            col, row = divmod(n, self.per)
            x = key_x0 + col * (COL_W + GUTTER) + indent
            y = self.h - (row + 1) * LEAD + 1
            c.setFillGray(grey)
            c.drawString(x, y, text)


def parse(path):
    with open(path) as fh:
        screenplay = fountain.parse(fh)
    return screenplay, fse.process(screenplay)


def inject(module, fn_name, style_attr, blocking, columns):
    scenes = iter(blocking.scenes)
    original = getattr(module, fn_name)

    def story(*args, **kw):
        out = []
        settings = args[1] if len(args) > 1 else kw.get("settings")
        for f in original(*args, **kw):
            out.append(f)
            if getattr(f, "style", None) is getattr(settings, style_attr, object()) or (
                style_attr is None and type(f).__name__ == "Slug"
            ):
                out.append(Spacer(1, 2 * mm))
                out.append(ScenePlan(blocking, next(scenes).preset, columns))
                out.append(Spacer(1, 4 * mm))
        return out

    setattr(module, fn_name, story)
    return lambda: setattr(module, fn_name, original)


def stageplay(path, tag, columns, out_dir):
    screenplay, blocking = parse(path)
    play = to_stageplay(screenplay)
    settings = stageplay_pdf.StagePlaySettings()
    restore = inject(stageplay_pdf, "_body_story", "scene_style", blocking, columns)
    try:
        with open(out_dir / f"key-{tag}-{'A' if columns else 'B'}.pdf", "wb") as fh:
            stageplay_pdf.to_pdf(play, fh, settings=settings)
    finally:
        restore()


if __name__ == "__main__":
    out_dir = run.OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    for fixture in [*run.FIXTURES, "crowd"]:
        for columns in (True, False):
            stageplay(run.HERE / f"{fixture}.fountain", fixture, columns, out_dir)
    print("\n".join(sorted(str(p) for p in out_dir.glob("key-*.pdf"))), file=sys.stderr)
