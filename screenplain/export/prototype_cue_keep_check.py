import io

from reportlab.platypus import Paragraph

from screenplain.export import pdf
from screenplain.export.prototype_cue_positions import CueMark, install

s = pdf.create_default_settings()


def run(mark, n):
    doc = pdf.DocTemplate(
        io.BytesIO(), pagesize=(s.page_width, s.page_height), settings=s
    )
    install(doc, 500)

    story = [pdf.NextPageTemplate("standard")]
    story += [Paragraph("x", s.action_style) for _ in range(n)]
    story.append(Paragraph("HAMLET", s.character_style))
    if mark:
        story.append(CueMark("m"))
    story.append(Paragraph("Speech", s.dialog_style))
    pages = {}

    orig = Paragraph.draw

    def d(self):
        t = self.getPlainText()
        if t in ("HAMLET", "Speech"):
            pages[t] = self.canv.getPageNumber()
        orig(self)

    Paragraph.draw = d
    doc.build(story)
    Paragraph.draw = orig
    return pages


for n in range(25, 30):
    print(n, "no mark", run(False, n), "| CueMark", run(True, n))
