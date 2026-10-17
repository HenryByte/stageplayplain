# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php

"""PDF output for stage plays, in the style of a published acting edition."""

import os
from html import escape
from io import TextIOWrapper
from typing import override

from reportlab import platypus
from reportlab.lib import pagesizes
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageTemplate,
    Paragraph,
)
from reportlab.platypus.flowables import PageBreakIfNotEmpty

from screenplain.export import plans
from screenplain.export.margin_plans import (
    Cues,
    FlushMargin,
    MarginLayout,
    MarginPlan,
    cue_tag,
    html_with_cues,
    margin_plans,
)
from screenplain.export.pdf import (
    FontSettings,
    Settings,
    get_title_page_story,
    pdf_metadata,
)
from screenplain.fse import Blocking
from screenplain.richstring import RichString
from screenplain.stageplay import split_cue
from screenplain.types import (
    Act,
    Action,
    CastGroup,
    CastList,
    CastMember,
    CharacterName,
    Dialog,
    DualDialog,
    FrontMatterSection,
    PageBreak,
    Scene,
    Section,
    StageDirection,
    StagePlay,
    Transition,
)

SMALL_CAPS_SCALE = 0.8


def get_eb_garamond_settings() -> FontSettings:
    """Get font settings for EB Garamond, which is bundled with Screenplain"""
    path = os.path.join(os.path.dirname(__file__), "eb_garamond")
    s = FontSettings("EB Garamond")
    s.file_normal = os.path.join(path, "EBGaramond-Regular.ttf")
    s.file_bold = os.path.join(path, "EBGaramond-Bold.ttf")
    s.file_italic = os.path.join(path, "EBGaramond-Italic.ttf")
    s.file_bold_italic = os.path.join(path, "EBGaramond-BoldItalic.ttf")
    s.register()
    return s


def get_standard_font_settings() -> FontSettings:
    """Get font settings for the Times font that's built into PDF."""
    return FontSettings("Times-Roman")


class StagePlaySettings(Settings):
    """Settings for an A4 acting edition."""

    regular_font: str
    italic_font: str

    def __init__(
        self,
        font_size: float = 12,
        font_settings: FontSettings | None = None,
    ) -> None:
        font_settings = font_settings or get_eb_garamond_settings()
        line_height = font_size * 1.25
        super().__init__(
            font_size=font_size,
            line_height=line_height,
            page_size=pagesizes.A4,
            font_settings=font_settings,
        )

        if font_settings.family_name == "Times-Roman":
            self.regular_font = "Times-Roman"
            self.italic_font = "Times-Italic"
        else:
            self.regular_font = font_settings.family_name
            self.italic_font = font_settings.family_name + " Italic"

        # Override the screenplay's Courier-based page geometry.
        self.left_margin = 35 * mm
        self.right_margin = 35 * mm
        self.top_margin = 25 * mm
        self.bottom_margin = 25 * mm
        self.frame_width = self.page_width - self.left_margin - self.right_margin
        self.frame_height = self.page_height - self.top_margin - self.bottom_margin
        self.title_frame_width = self.frame_width

        half_line = line_height / 2
        base = self.default_style

        self.act_style = ParagraphStyle(
            "act",
            base,
            fontSize=font_size * 1.25,
            leading=line_height * 1.25,
            alignment=TA_CENTER,
            spaceAfter=line_height * 2,
            keepWithNext=1,
        )
        self.scene_style = ParagraphStyle(
            "scene",
            base,
            alignment=TA_CENTER,
            spaceBefore=line_height * 2,
            spaceAfter=line_height,
            keepWithNext=1,
        )
        self.front_heading_style = self.scene_style
        self.front_subheading_style = ParagraphStyle(
            "front-subheading",
            base,
            fontName=self.italic_font,
            alignment=TA_CENTER,
            spaceBefore=line_height,
            spaceAfter=half_line,
            keepWithNext=1,
        )
        self.prose_style = ParagraphStyle("prose", base, spaceBefore=half_line)
        self.cast_member_style = ParagraphStyle(
            "cast-member", base, spaceBefore=half_line / 2
        )
        speech_indent = font_size * 1.5
        self.speech_style = ParagraphStyle(
            "speech",
            base,
            spaceBefore=half_line,
            leftIndent=speech_indent,
            firstLineIndent=-speech_indent,
        )
        self.direction_style = ParagraphStyle(
            "direction",
            base,
            fontName=self.italic_font,
            leftIndent=font_size * 2,
            spaceBefore=half_line,
            spaceAfter=half_line,
        )
        self.centered_action_style = ParagraphStyle(
            "centered-action", base, alignment=TA_CENTER, spaceBefore=line_height
        )
        self.transition_style = ParagraphStyle(
            "transition", base, alignment=TA_RIGHT, spaceBefore=line_height
        )


class StagePlayDocTemplate(BaseDocTemplate):
    """Numbers pages from the start of the play body."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        settings = kwargs.pop("settings")
        assert isinstance(settings, StagePlaySettings)
        self.settings = settings
        self.body_first_page: int | None = None
        frame = Frame(
            settings.left_margin,
            settings.bottom_margin,
            settings.frame_width,
            settings.frame_height,
            leftPadding=0,
            topPadding=0,
            rightPadding=0,
            bottomPadding=0,
        )
        # get_title_page_story switches to the "standard" template.
        page_templates = [
            PageTemplate(id=template_id, frames=[frame], onPageEnd=self._number_page)
            for template_id in ("title", "standard")
        ]
        BaseDocTemplate.__init__(self, *args, pageTemplates=page_templates, **kwargs)

    def _number_page(self, canvas: Canvas, doc: BaseDocTemplate) -> None:
        if self.body_first_page is None:
            return
        canvas.saveState()
        canvas.setFont(self.settings.regular_font, self.settings.font_size)
        canvas.drawRightString(
            self.settings.left_margin + self.settings.frame_width,
            self.settings.page_height - self.settings.top_margin / 2,
            str(self.page - self.body_first_page + 1),
        )
        canvas.restoreState()


class BodyStart(Flowable):
    """Zero-size marker recording the page where the play body starts."""

    @override
    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        return 0, 0

    def draw(self) -> None:
        doc = self.canv._doctemplate
        if doc.body_first_page is None:
            doc.body_first_page = doc.page


def small_caps(text: str, settings: StagePlaySettings) -> str:
    """Simulates small caps by drawing lowercase letters as smaller capitals.

    The result is in roman even inside italic paragraphs.
    """
    size = settings.font_size * SMALL_CAPS_SCALE
    html = []
    run = ""
    for char in text:
        if char.islower():
            run += char
            continue
        if run:
            html.append(f'<font size="{size}">{escape(run.upper())}</font>')
            run = ""
        html.append(escape(char))
    if run:
        html.append(f'<font size="{size}">{escape(run.upper())}</font>')
    return f'<font name="{settings.regular_font}">{"".join(html)}</font>'


def _lines_html(lines: list[RichString]) -> str:
    return "<br/>".join(line.to_html() for line in lines)


class SourceCues:
    """The margin-plan cues of the screenplay paragraph a stage-play body
    element came from.
    """

    def __init__(self, cues: Cues | None = None, index: int | None = None) -> None:
        self.cues, self.index = cues, index

    @property
    def start(self) -> str:
        if self.cues is None or self.index is None:
            return ""
        return self.cues.before(self.index)

    @property
    def end(self) -> str:
        if self.cues is None or self.index is None:
            return ""
        return self.cues.after(self.index)

    def part(self, side: int, part: int) -> list[tuple[int, str]]:
        if self.cues is None or self.index is None:
            return []
        return self.cues.part(self.index, side, part)


def _direction_line_html(
    line: list[RichString | CharacterName],
    settings: StagePlaySettings,
    cues: list[tuple[int, str]],
) -> str:
    """A stage direction line's HTML, with cues at offsets into the line
    as written. Each name was written with an `@` that is no longer in
    it; a cue inside a name goes before it.
    """
    html: list[str] = []
    start = 0
    pending = sorted(cues)
    for part in line:
        if isinstance(part, CharacterName):
            end = start + 1 + len(str(part.name))
            while pending and pending[0][0] < end:
                html.append(cue_tag(pending.pop(0)[1]))
            html.append(small_caps(str(part.name), settings))
        else:
            end = start + len(str(part))
            here = [
                (offset - start, plan_id) for offset, plan_id in pending if offset < end
            ]
            pending = pending[len(here) :]
            html.append(html_with_cues(part, here, inline=True))
        start = end
    html += [cue_tag(plan_id) for _, plan_id in pending]
    return "".join(html)


def _direction_html(
    direction: StageDirection,
    settings: StagePlaySettings,
    cues: SourceCues | None = None,
) -> str:
    cues = cues or SourceCues()
    html = "<br/>".join(
        _direction_line_html(line, settings, cues.part(0, part))
        for part, line in enumerate(direction.lines)
    )
    return cues.start + html + cues.end


def _speech_html(
    dialog: Dialog,
    settings: StagePlaySettings,
    cues: SourceCues | None = None,
    side: int = 0,
    first: bool = True,
    last: bool = True,
) -> str:
    cues = cues or SourceCues()
    name, extension = split_cue(dialog.character)
    html = (cues.start if first else "") + small_caps(name, settings)
    if extension:
        html += f" <i>{escape(extension)}</i>"
    if not name.endswith(".") or extension:
        html += "."

    previous_parenthetical = True  # The cue runs in to the first line.
    for part, (parenthetical, text) in enumerate(dialog.blocks):
        text_html = html_with_cues(text, cues.part(side, part))
        if parenthetical:
            html += f" <i>{text_html}</i>"
        elif previous_parenthetical:
            html += " " + text_html
        else:
            html += "<br/>" + text_html
        previous_parenthetical = parenthetical
    return html + (cues.end if last else "")


def _speech(
    dialog: Dialog,
    settings: StagePlaySettings,
    cues: SourceCues | None = None,
    side: int = 0,
    first: bool = True,
    last: bool = True,
) -> Paragraph:
    return Paragraph(
        _speech_html(dialog, settings, cues, side, first, last), settings.speech_style
    )


def _dual_speech(
    dual: DualDialog, settings: StagePlaySettings, cues: SourceCues | None = None
) -> Flowable:
    col_width = settings.frame_width / 2
    left = _speech(dual.left, settings, cues, 0, last=False)
    right = _speech(dual.right, settings, cues, 1, first=False)
    return platypus.Table(
        [[[left], [right]]],
        splitInRow=1,
        spaceBefore=settings.line_height / 2,
        colWidths=[col_width, col_width],
        style=settings.dual_dialog_table_style,
    )


def _cast_list_story(
    cast_list: CastList, settings: StagePlaySettings
) -> list[Flowable]:
    story: list[Flowable] = [
        Paragraph(small_caps(str(cast_list.title), settings), settings.scene_style)
    ]
    for entry in cast_list.entries:
        if isinstance(entry, CastGroup):
            story.append(
                Paragraph(entry.title.to_html(), settings.front_subheading_style)
            )
        elif isinstance(entry, CastMember):
            html = small_caps(str(entry.name), settings)
            if entry.description:
                html += ", <i>" + " ".join(d.to_html() for d in entry.description)
                html += "</i>"
            story.append(Paragraph(html, settings.cast_member_style))
        else:
            story.append(
                Paragraph(_direction_html(entry, settings), settings.prose_style)
            )
    return story


def _front_section_story(
    section: FrontMatterSection, settings: StagePlaySettings
) -> list[Flowable]:
    story: list[Flowable] = []
    if section.title is not None:
        story.append(
            Paragraph(
                small_caps(str(section.title), settings),
                settings.front_heading_style,
            )
        )
    for para in section.paragraphs:
        if isinstance(para, StageDirection):
            story.append(
                Paragraph(_direction_html(para, settings), settings.prose_style)
            )
        elif isinstance(para, Section):
            story.append(
                Paragraph(para.text.to_html(), settings.front_subheading_style)
            )
        elif isinstance(para, Dialog):
            story.append(_speech(para, settings))
        elif isinstance(para, DualDialog):
            story.append(_dual_speech(para, settings))
        elif isinstance(para, Action):
            story.append(
                Paragraph(_lines_html(para.lines), settings.centered_action_style)
            )
        elif isinstance(para, Transition):
            story.append(Paragraph(para.line.to_html(), settings.transition_style))
    return story


def _body_story(
    play: StagePlay,
    settings: StagePlaySettings,
    blocking: Blocking | None = None,
    cues: Cues | None = None,
) -> list[Flowable]:
    story: list[Flowable] = [PageBreakIfNotEmpty(), BodyStart()]
    scene_plans = plans.scene_plans(blocking) if blocking is not None else {}
    for index, para in enumerate(play.body):
        source = play.sources[index] if index < len(play.sources) else None
        at = SourceCues(cues, source)
        if isinstance(para, Act):
            # BodyStart counts as page content, so don't break straight after it.
            if not isinstance(story[-1], BodyStart):
                story.append(PageBreakIfNotEmpty())
            story.append(
                Paragraph(
                    at.start + escape(str(para.text).upper()) + at.end,
                    settings.act_style,
                )
            )
        elif isinstance(para, Scene):
            story.append(
                Paragraph(
                    at.start + small_caps(str(para.text), settings) + at.end,
                    settings.scene_style,
                )
            )
        elif isinstance(para, StageDirection):
            story.append(
                Paragraph(_direction_html(para, settings, at), settings.direction_style)
            )
        elif isinstance(para, Dialog):
            story.append(_speech(para, settings, at))
        elif isinstance(para, DualDialog):
            story.append(_dual_speech(para, settings, at))
        elif isinstance(para, Action):
            story.append(
                Paragraph(
                    at.start + _lines_html(para.lines) + at.end,
                    settings.centered_action_style,
                )
            )
        elif isinstance(para, Transition):
            story.append(
                Paragraph(
                    at.start + para.line.to_html() + at.end, settings.transition_style
                )
            )
        elif isinstance(para, PageBreak):
            story.append(platypus.PageBreak())
        if source in scene_plans:
            assert blocking is not None
            story.append(plans.ScenePlan(blocking, scene_plans[source]))
    return story


def to_pdf(
    play: StagePlay,
    output_filename: TextIOWrapper,
    settings: StagePlaySettings | None = None,
    blocking: Blocking | None = None,
) -> None:
    """Writes a stage play as PDF. With a `blocking`, each scene opens with
    its scene plan.
    """
    settings = settings or StagePlaySettings()
    story = get_title_page_story(play, settings)
    for section in play.front_matter:
        if isinstance(section, CastList):
            story += _cast_list_story(section, settings)
        else:
            story += _front_section_story(section, settings)
    margin: list[MarginPlan] = []
    cues = None
    if blocking is not None:
        margin = margin_plans(blocking)
        cues = Cues.place(blocking, margin)
    story += _body_story(play, settings, blocking, cues)

    doc = StagePlayDocTemplate(
        output_filename,
        pagesize=(settings.page_width, settings.page_height),
        settings=settings,
        **pdf_metadata(play),
    )
    if blocking is not None:
        layout = MarginLayout(
            blocking,
            margin,
            settings.left_margin + settings.frame_width,
            settings.page_height - settings.top_margin,
            settings.bottom_margin,
        )
        layout.install(doc)
        story.append(FlushMargin(layout))
    doc.build(story)
