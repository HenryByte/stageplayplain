from reportlab.platypus import Paragraph

from screenplain.export import pdf, stageplay_pdf
from screenplain.export.prototype_cue_positions import LONG_SPEECH, cue

diff = 0
total = 0
for s, style in [
    (pdf.create_default_settings(), "dialog_style"),
    (stageplay_pdf.StagePlaySettings(), "speech_style"),
]:
    st = getattr(s, style)
    words = LONG_SPEECH.split(" ")
    for i in range(len(words) + 1):
        for glue in ("start", "end"):
            w = list(words)
            if i < len(w):
                w[i] = cue("x") + w[i] if glue == "start" else w[i]
            else:
                w[-1] += cue("x")
            a = Paragraph(LONG_SPEECH, st)
            b = Paragraph(" ".join(w), st)
            a.wrap(s.frame_width, 1e5)
            b.wrap(s.frame_width, 1e5)
            total += 1
            if a.height != b.height or len(a.blPara.lines) != len(b.blPara.lines):
                diff += 1
print(f"{diff} of {total} insertions changed the paragraph's height or line count")
