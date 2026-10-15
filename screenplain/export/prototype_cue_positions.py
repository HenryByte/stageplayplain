"""PROTOTYPE, throwaway: answers "How can a ReportLab layout find where a cue
lands on the page?" (ticket #38, map #36). Not production code; delete me.

Run:  uv run python screenplain/export/prototype_cue_positions.py
Writes prototype-cues-screenplay.pdf and prototype-cues-stageplay.pdf into
the current directory and prints every cue position it captured.

Technique under test, one pass, no re-layout:
  * Inline cue: a zero-width `<onDraw name="cue" label="..."/>` tag spliced
    into the paragraph markup at the note's offset. ReportLab calls
    canvas.cue(canvas, kind, label) while drawing that line, with the line's
    cur_x/cur_y in canvas._curr_tx_info; canvas.absolutePosition() maps them
    to page coordinates. Survives paragraph splits and table cells.
  * Standalone cue (gap between paragraphs): two candidates compared:
      A. a zero-height CueMark flowable in the story;
      B. an onDraw tag at the very start of the NEXT paragraph.
  * Plans are drawn at page end (PageTemplate onPageEnd), when every cue on
    the page is known, in the margin, so the text never moves.
The red dot is the exact captured cue point; the box is a stand-in plan.
"""

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Paragraph,
    Table,
)

from screenplain.export import pdf, stageplay_pdf

PLAN_W, PLAN_H, GAP = 34 * mm, 30 * mm, 2 * mm


class CueLog:
    def __init__(self) -> None:
        self.by_page: dict[int, list[tuple[str, float, float]]] = {}

    def record(self, page: int, label: str, x: float, y: float) -> None:
        self.by_page.setdefault(page, []).append((label, x, y))
        print(f"  page {page:>2}  y={y:6.1f}  x={x:6.1f}  {label}")


def inline_cue(canvas, kind, label):  # called by Paragraph while drawing
    info = canvas._curr_tx_info
    # cur_y is the baseline; aim at the middle of the line's x-height.
    x, y = canvas.absolutePosition(info["cur_x"], info["cur_y"] + 3)
    canvas._doctemplate.cue_log.record(canvas.getPageNumber(), label, x, y)


class CueMark(Flowable):
    """Candidate A: zero-height flowable standing in a standalone note's gap."""

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    def wrap(self, availWidth, availHeight):
        return 0, 0

    def draw(self) -> None:
        x, y = self.canv.absolutePosition(0, 0)
        doc = self.canv._doctemplate
        doc.cue_log.record(self.canv.getPageNumber(), self.label, x, y)


def draw_plans(canvas, doc, margin_left: float) -> None:
    """Stack a stand-in plan per cue, top aligned to its cue where possible."""
    cues = sorted(
        doc.cue_log.by_page.get(canvas.getPageNumber(), []), key=lambda c: -c[2]
    )
    canvas.saveState()
    next_top = doc.pagesize[1]
    for label, x, y in cues:
        top = min(y + 4, next_top)
        canvas.setStrokeColor(colors.red)
        canvas.setFillColor(colors.red)
        canvas.circle(x, y, 1.5, fill=1, stroke=0)
        canvas.setLineWidth(0.3)
        canvas.line(x, y, margin_left - 1 * mm, y)  # marker to the plan
        canvas.line(margin_left - 1 * mm, y, margin_left, top - 2)
        canvas.setStrokeColor(colors.blue)
        canvas.rect(margin_left, top - PLAN_H, PLAN_W, PLAN_H)
        canvas.setFont("Helvetica", 6)
        canvas.setFillColor(colors.blue)
        canvas.drawString(margin_left + 1 * mm, top - 3 * mm, label[:28])
        if top - PLAN_H < doc.bottomMargin:
            canvas.drawString(margin_left + 1 * mm, top - 6 * mm, "OVERFLOWS PAGE")
        next_top = top - PLAN_H - GAP
    canvas.restoreState()


def install(doc, margin_left: float) -> None:
    doc.cue_log = CueLog()
    orig_before = doc.beforeDocument

    def before_document():
        doc.canv.cue = inline_cue
        orig_before()

    doc.beforeDocument = before_document
    for template in doc.pageTemplates:
        orig_end = template.onPageEnd

        def on_page_end(canvas, d, orig_end=orig_end):
            orig_end(canvas, d)
            draw_plans(canvas, d, margin_left)

        template.onPageEnd = on_page_end


def cue(label: str) -> str:
    return f'<onDraw name="cue" label="{label}"/>'


FILLER = (
    "The gravediggers work in silence, shovelling earth over the lip of the "
    "grave while the light fails behind the church."
)

LONG_SPEECH = " ".join(
    [
        "Alas, poor Yorick! I knew him, Horatio: a fellow of infinite jest, of most "
        "excellent fancy: he hath borne me on his back a thousand times;"
    ]
    * 5
)


def screenplay_story(s: pdf.Settings) -> list[Flowable]:
    story: list[Flowable] = [Paragraph("EXT. CHURCHYARD - DUSK", s.slug_style)]
    story.append(
        Paragraph(
            "Hamlet and Horatio pick their way between the stones until "
            f"Hamlet stops {cue('1 inline, mid wrapped line')}dead at the "
            "open grave and peers down into it, curious.",
            s.action_style,
        )
    )
    story.append(CueMark("2A standalone gap (CueMark)"))
    story.append(
        Paragraph(cue("2B standalone (next para start)") + FILLER, s.action_style)
    )
    # Character cue keepWithNext=1: does a CueMark between break the keep?
    story.append(Paragraph("HAMLET", s.character_style))
    story.append(CueMark("3A between character and dialogue"))
    story.append(Paragraph("Whose grave's this, sirrah?", s.dialog_style))
    for i in range(14):
        story.append(Paragraph(FILLER, s.action_style))
    # Long dialogue that splits across a page; cue late in it.
    story.append(Paragraph("HAMLET", s.character_style))
    words = LONG_SPEECH.split(" ")
    words.insert(len(words) - 12, cue("4 inline in dialogue after page split"))
    story.append(Paragraph(" ".join(words), s.dialog_style))
    story.append(CueMark("5A gap right after split dialogue"))
    # Dual dialogue with a cue in the right column.
    col = s.frame_width / 2
    left = pdf.ParagraphStyle("l", s.dialog_style, leftIndent=0, rightIndent=0)
    story.append(
        Table(
            [
                [
                    [
                        Paragraph("HAMLET", s.character_style),
                        Paragraph("Who is it?", left),
                    ],
                    [
                        Paragraph("GRAVEDIGGER", s.character_style),
                        Paragraph(
                            f"One that was {cue('6 inline in dual dialogue')}a woman, sir.",
                            left,
                        ),
                    ],
                ]
            ],
            colWidths=[col, col],
            style=s.dual_dialog_table_style,
            spaceBefore=s.line_height,
        )
    )
    # Push a CueMark to the very bottom of a page.
    for i in range(30):
        story.append(Paragraph(f"{i}. " + FILLER, s.action_style))
        story.append(CueMark(f"7A gap after filler {i}"))
    return story


def build_screenplay() -> None:
    print("screenplay layout")
    s = pdf.create_default_settings()
    doc = pdf.DocTemplate(
        "prototype-cues-screenplay.pdf",
        pagesize=(s.page_width, s.page_height),
        settings=s,
    )
    doc.handle_nextPageTemplate("standard")
    install(doc, s.left_margin + s.frame_width + 2 * mm)
    doc.build([pdf.NextPageTemplate("standard"), *screenplay_story(s)])


def build_stageplay() -> None:
    print("stage play layout")
    s = stageplay_pdf.StagePlaySettings()
    doc = stageplay_pdf.StagePlayDocTemplate(
        "prototype-cues-stageplay.pdf",
        pagesize=(s.page_width, s.page_height),
        settings=s,
    )
    install(doc, s.left_margin + s.frame_width + 1 * mm)
    story: list[Flowable] = [stageplay_pdf.BodyStart()]
    story.append(Paragraph("SCENE ONE", s.scene_style))
    story.append(
        Paragraph(
            f"<i>A churchyard. HAMLET and HORATIO {cue('1 inline in direction')}enter.</i>",
            s.direction_style,
        )
    )
    story.append(CueMark("2A standalone gap (CueMark)"))
    story.append(
        Paragraph(
            cue("2B standalone (next para start)") + "HAMLET. Whose grave's this?",
            s.speech_style,
        )
    )
    for i in range(18):
        story.append(Paragraph(f"FIRST CLOWN. {FILLER}", s.speech_style))
    words = ("HAMLET. " + LONG_SPEECH).split(" ")
    words.insert(len(words) - 12, cue("4 inline in speech after page split"))
    story.append(Paragraph(" ".join(words), s.speech_style))
    for i in range(40):
        story.append(Paragraph(f"{i}. {FILLER}", s.speech_style))
        story.append(CueMark(f"7A gap after speech {i}"))
    doc.build(story)


if __name__ == "__main__":
    build_screenplay()
    build_stageplay()
