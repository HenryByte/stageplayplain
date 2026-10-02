# Copyright (c) 2011 Martin Vilcans
# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php

from __future__ import annotations

import os
import os.path
from collections.abc import Callable
from html import escape
from typing import TextIO

from screenplain.richstring import RichString, plain
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
    Screenplay,
    Section,
    Slug,
    StageDirection,
    StagePlay,
    Transition,
)


class tag:
    """Handler for automatically opening and closing a tag.

    E.g.

    >>> import sys
    >>> with tag(sys.stdout, 'div'):
    ...     print('hello')
    ...
    <div>hello
    </div>

    Adding classes to the element is possible:

    >>> with tag(sys.stdout, 'div', classes=['action']):
    ...     print('hello')
    <div class="action">hello
    </div>

    >>> with tag(sys.stdout, 'div', classes=['action', 'centered']):
    ...     print('hello')
    <div class="action centered">hello
    </div>

    """

    def __init__(
        self, out: TextIO, tag: str, classes: list[str] | set[str] | None = None
    ) -> None:
        self.out = out
        self.tag = tag
        self.classes = classes

    def __enter__(self) -> tag:
        if self.classes:
            self.out.write(f'<{self.tag} class="{" ".join(self.classes)}">')
        else:
            self.out.write(f"<{self.tag}>")
        return self

    def __exit__(
        self, exception_type: object, value: object, traceback: object
    ) -> bool:
        if not exception_type:
            self.out.write(f"</{self.tag}>")
        return False


def to_html(text: RichString) -> str:
    html = text.to_html()
    if html == "":
        return "&nbsp;"
    else:
        return html


class Formatter:
    """Class for converting paragraphs into HTML."""

    def __init__(self, out: TextIO) -> None:
        """Initializes the formatter.

        `out` is a file-like object to write to.
        After initializing, call the convert function to convert
        any number of paragraphs.

        """
        self.out = out
        self._format_functions: dict[type, Callable[..., None]] = {
            Slug: self.format_slug,
            Action: self.format_action,
            Dialog: self.format_dialog,
            DualDialog: self.format_dual,
            Transition: self.format_transition,
            Section: self.format_section,
            PageBreak: self.format_page_break,
        }

    def convert(self, screenplay: Screenplay) -> None:
        """Converts a number of paragraphs into HTML and writes
        it to the output stream.
        `screenplay` is a sequence of paragraphs.

        """
        self.page_break_before_next = False
        for para in screenplay:
            format_function = self._format_functions.get(type(para), None)
            if format_function:
                format_function(para)
                self.out.write("\n")

    def format_dialog(self, dialog: Dialog) -> None:
        with self._tag("div", classes=["dialog"]):
            self._write_dialog_block(dialog)

    def format_dual(self, dual: DualDialog) -> None:
        with self._tag("div", classes=["dual"]):
            with self._tag("div", classes=["left"]):
                self._write_dialog_block(dual.left)
            with self._tag("div", classes=["right"]):
                self._write_dialog_block(dual.right)
            self.out.write("<br />")

    def _write_dialog_block(self, dialog: Dialog) -> None:
        with self._tag("p", classes=["character"]):
            self.out.write(to_html(dialog.character))

        for parenthetical, text in dialog.blocks:
            classes = ["parenthetical"] if parenthetical else None
            with self._tag("p", classes=classes):
                self.out.write(to_html(text))

    def format_slug(self, slug: Slug) -> None:
        num = slug.scene_number
        with self._tag("h6"):
            if num:
                with self._tag("span", classes=["scnuml"]):
                    self.out.write(to_html(num))
            self.out.write(to_html(slug.line))
            if num:
                with self._tag("span", classes=["scnumr"]):
                    self.out.write(to_html(num))
        if slug.synopsis:
            with self._tag("span", classes=["h6-synopsis"]):
                self.out.write(to_html(plain(slug.synopsis)))

    def format_section(self, section: Section) -> None:
        with self._tag(f"h{section.level}"):
            self.out.write(to_html(section.text))
        if section.synopsis:
            with self._tag("span", classes=[f"h{section.level}-synopsis"]):
                self.out.write(to_html(plain(section.synopsis)))

    def format_action(self, para: Action) -> None:
        classes = ["action"]
        if para.centered:
            classes.append("centered")
        with self._tag("div", classes=classes):
            with self._tag("p"):
                for number, line in enumerate(para.lines):
                    if number != 0:
                        self.out.write("<br/>")
                    self.out.write(to_html(line))

    def format_transition(self, para: Transition) -> None:
        with self._tag("div", classes=["transition"]):
            self.out.write(to_html(para.line))

    def format_page_break(self, para: PageBreak) -> None:
        self.page_break_before_next = True

    def _tag(self, tag_name: str, classes: list[str] | None = None) -> tag:
        tag_classes: list[str] | set[str] = classes if classes is not None else []
        if self.page_break_before_next:
            self.page_break_before_next = False
            tag_classes = set(tag_classes).union(("page-break",))
        return tag(self.out, tag_name, tag_classes)


def convert(
    screenplay: Screenplay,
    out: TextIO,
    css_file: str | None = None,
    bare: bool = False,
) -> None:
    """Convert the screenplay into HTML, written to the file-like object `out`.

    The output will be a complete HTML document unless `bare` is true.

    """
    if bare:
        convert_bare(screenplay, out)
    else:
        convert_full(
            screenplay,
            out,
            css_file or os.path.join(os.path.dirname(__file__), "default.css"),
        )


def convert_full(screenplay: Screenplay, out: TextIO, css_file: str) -> None:
    """Convert the screenplay into a complete HTML document,
    written to the file-like object `out`.

    """
    with open(css_file, encoding="utf-8") as stream:
        css = stream.read()
    out.write(
        '<!DOCTYPE html>\n<html><head><title>Screenplay</title><style type="text/css">'
    )
    out.write(css)
    out.write('</style></head><body><div id="wrapper" class="screenplay">\n')
    convert_bare(screenplay, out)
    out.write("</div></body></html>\n")


def convert_bare(screenplay: Screenplay, out: TextIO) -> None:
    """Convert the screenplay into HTML, written to the file-like object `out`.
    Does not create a complete HTML document, as it doesn't include
    <html>, <body>, etc.

    """
    formatter = Formatter(out)
    formatter.convert(screenplay)


class StagePlayFormatter:
    """Class for converting a stage play into HTML."""

    def __init__(self, out: TextIO) -> None:
        self.out = out

    def convert(self, play: StagePlay) -> None:
        self.format_title_page(play)
        if play.front_matter:
            with tag(self.out, "div", classes=["front-matter"]):
                for section in play.front_matter:
                    if isinstance(section, CastList):
                        self.format_cast_list(section)
                    else:
                        self.format_front_section(section)
            self.out.write("\n")
        with tag(self.out, "div", classes=["play"]):
            self.out.write("\n")
            page_break = False
            for para in play.body:
                if isinstance(para, PageBreak):
                    page_break = True
                    continue
                self.format_paragraph(para, ["page-break"] if page_break else [])
                page_break = False
                self.out.write("\n")
        self.out.write("\n")

    def format_title_page(self, play: StagePlay) -> None:
        lines = [
            (key, line)
            for key in ("Title", "Credit", "Author", "Authors", "Source")
            for line in play.get_rich_attribute(key)
        ]
        if not lines:
            return
        with tag(self.out, "div", classes=["title-page"]):
            for key, line in lines:
                with tag(self.out, "p", classes=[key.lower()]):
                    self.out.write(to_html(line))
        self.out.write("\n")

    def format_cast_list(self, cast_list: CastList) -> None:
        with tag(self.out, "div", classes=["cast-list"]):
            with tag(self.out, "h2"):
                self.out.write(to_html(cast_list.title))
            for entry in cast_list.entries:
                if isinstance(entry, CastGroup):
                    with tag(self.out, "h3", classes=["cast-group"]):
                        self.out.write(to_html(entry.title))
                elif isinstance(entry, CastMember):
                    self.format_cast_member(entry)
                else:
                    self.format_direction(entry, ["prose"])

    def format_cast_member(self, member: CastMember) -> None:
        with tag(self.out, "p", classes=["cast-member"]):
            self._write_character(member.name)
            if member.description:
                self.out.write(", ")
                with tag(self.out, "em", classes=["description"]):
                    self.out.write(
                        " ".join(to_html(line) for line in member.description)
                    )

    def format_front_section(self, section: FrontMatterSection) -> None:
        with tag(self.out, "div", classes=["front-section"]):
            if section.title is not None:
                with tag(self.out, "h2"):
                    self.out.write(to_html(section.title))
            for para in section.paragraphs:
                if isinstance(para, StageDirection):
                    self.format_direction(para, ["prose"])
                elif isinstance(para, Section):
                    with tag(self.out, "h3"):
                        self.out.write(to_html(para.text))
                elif not isinstance(para, (Slug, PageBreak)):
                    self.format_paragraph(para, [])

    def format_paragraph(
        self,
        para: Act | Scene | StageDirection | Dialog | DualDialog | Action | Transition,
        classes: list[str],
    ) -> None:
        if isinstance(para, Act):
            with tag(self.out, "h1", classes=["act", *classes]):
                self.out.write(to_html(para.text))
        elif isinstance(para, Scene):
            with tag(self.out, "h2", classes=["scene", *classes]):
                self.out.write(to_html(para.text))
        elif isinstance(para, StageDirection):
            self.format_direction(para, ["direction", *classes])
        elif isinstance(para, Dialog):
            self.format_speech(para, classes)
        elif isinstance(para, DualDialog):
            with tag(self.out, "div", classes=["dual", *classes]):
                with tag(self.out, "div", classes=["left"]):
                    self.format_speech(para.left, [])
                with tag(self.out, "div", classes=["right"]):
                    self.format_speech(para.right, [])
        elif isinstance(para, Action):
            with tag(self.out, "p", classes=["centered", *classes]):
                self.out.write("<br/>".join(to_html(line) for line in para.lines))
        else:
            with tag(self.out, "p", classes=["transition", *classes]):
                self.out.write(to_html(para.line))

    def format_direction(self, direction: StageDirection, classes: list[str]) -> None:
        with tag(self.out, "p", classes=classes):
            for number, line in enumerate(direction.lines):
                if number != 0:
                    self.out.write("<br/>")
                for part in line:
                    if isinstance(part, CharacterName):
                        self._write_character(part.name)
                    else:
                        self.out.write(part.to_inline_html())

    def format_speech(self, dialog: Dialog, classes: list[str]) -> None:
        name, extension = split_cue(dialog.character)
        with tag(self.out, "p", classes=["speech", *classes]):
            with tag(self.out, "span", classes=["cue"]):
                self.out.write(escape(name, quote=False))
            if extension:
                self.out.write(" ")
                with tag(self.out, "em", classes=["extension"]):
                    self.out.write(escape(extension, quote=False))
            if not name.endswith(".") or extension:
                self.out.write(".")
            previous_parenthetical = True  # The cue runs in to the first line.
            for parenthetical, text in dialog.blocks:
                if parenthetical:
                    self.out.write(" ")
                    with tag(self.out, "em", classes=["parenthetical"]):
                        self.out.write(text.to_html())
                elif previous_parenthetical:
                    self.out.write(" " + text.to_html())
                else:
                    self.out.write("<br/>" + text.to_html())
                previous_parenthetical = parenthetical

    def _write_character(self, name: RichString) -> None:
        with tag(self.out, "span", classes=["character"]):
            self.out.write(to_html(name))


def convert_stageplay(
    play: StagePlay,
    out: TextIO,
    css_file: str | None = None,
    bare: bool = False,
) -> None:
    """Convert the stage play into HTML, written to the file-like object `out`.

    The output will be a complete HTML document unless `bare` is true.

    """
    if bare:
        StagePlayFormatter(out).convert(play)
        return
    css_file = css_file or os.path.join(os.path.dirname(__file__), "stageplay.css")
    with open(css_file, encoding="utf-8") as stream:
        css = stream.read()
    out.write(
        '<!DOCTYPE html>\n<html><head><title>Stage Play</title><style type="text/css">'
    )
    out.write(css)
    out.write('</style></head><body><div id="wrapper" class="stageplay">\n')
    StagePlayFormatter(out).convert(play)
    out.write("</div></body></html>\n")
