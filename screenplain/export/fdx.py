# Copyright (c) 2011 Martin Vilcans
# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php

from typing import TextIO
from xml.sax.saxutils import escape

from screenplain.richstring import Bold, Italic, RichString, Style, Underline
from screenplain.types import (
    Action,
    Dialog,
    DualDialog,
    Screenplay,
    Slug,
    Transition,
)

style_names: dict[type[Style], str] = {
    Bold: "Bold",
    Italic: "Italic",
    Underline: "Underline",
}


def _write_text_element(out: TextIO, styles: list[str], text: str) -> None:
    style_value = "+".join(str(s) for s in styles)
    if style_value == "":
        out.write(f"      <Text>{escape(text)}</Text>\n")
    else:
        out.write(f'      <Text Style="{style_value}">{escape(text)}</Text>\n')


def write_text(out: TextIO, rich: RichString, trailing_linebreak: bool) -> None:
    """Writes <Text Style="..."> elements."""
    for seg_no, segment in enumerate(rich.segments):
        fdx_styles = [style_names[n] for n in segment.get_ordered_styles()]
        if trailing_linebreak and seg_no == len(rich.segments) - 1:
            _write_text_element(out, fdx_styles, segment.text + "\n")
        else:
            _write_text_element(out, fdx_styles, segment.text)


def write_paragraph(
    out: TextIO,
    para_type: str,
    lines: list[RichString],
    centered: bool = False,
) -> None:
    if centered:
        out.write(f'    <Paragraph Alignment="Center" Type="{para_type}">\n')
    else:
        out.write(f'    <Paragraph Type="{para_type}">\n')

    last_line_no = len(lines) - 1
    for line_no, line in enumerate(lines):
        write_text(out, line, line_no != last_line_no)
    out.write("    </Paragraph>\n")


def write_dialog(out: TextIO, dialog: Dialog) -> None:
    write_paragraph(out, "Character", [dialog.character])
    for parenthetical, line in dialog.blocks:
        if parenthetical:
            write_paragraph(out, "Parenthetical", [line])
        else:
            write_paragraph(out, "Dialogue", [line])


def write_dual_dialog(out: TextIO, dual: DualDialog) -> None:
    out.write("    <Paragraph>\n      <DualDialogue>\n")
    write_dialog(out, dual.left)
    write_dialog(out, dual.right)
    out.write("      </DualDialogue>\n    </Paragraph>\n")


def to_fdx(screenplay: Screenplay, out: TextIO) -> None:
    out.write(
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'
        '<FinalDraft DocumentType="Script" Template="No" Version="1">\n'
        "\n"
        "  <Content>\n"
    )

    for para in screenplay:
        if isinstance(para, Dialog):
            write_dialog(out, para)
        elif isinstance(para, DualDialog):
            write_dual_dialog(out, para)
        elif isinstance(para, Action):
            write_paragraph(out, "Action", para.lines, centered=para.centered)
        elif isinstance(para, Slug):
            write_paragraph(out, "Scene Heading", para.lines)
        elif isinstance(para, Transition):
            write_paragraph(out, "Transition", para.lines)
        else:
            # Ignore unknown types
            pass

    out.write("  </Content>\n</FinalDraft>\n")
