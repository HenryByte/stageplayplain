"""PROTOTYPE, throwaway. Answers issue #15:
"How do FSE notes survive the Fountain parser with their cue position?"

Approach under test: a *side channel*. `parse_body` keeps doing exactly what
it does (strip every note, classify the paragraph with the real
InputParagraph), but as it strips each FSE note it records where the note
was cut out: the paragraph's source lines, the offset in the note-stripped
text, and afterwards the element the paragraph turned into. The Screenplay
itself is untouched, so Script-mode output is byte-identical by
construction, and `compare` below checks that against every fixture.

Run:  uv run python -m screenplain.parsers.fse_extract_PROTOTYPE FILE...
"""

from __future__ import annotations

import itertools
import re
import sys
from dataclasses import dataclass, field
from io import StringIO
from itertools import takewhile

from screenplain.parsers import fountain
from screenplain.parsers.fountain import (
    InputParagraph,
    _is_blank,
    _preprocess_line,
    boneyard_re,
    linebreak_re,
    note_re,
    parse_title_page,
)
from screenplain.types import (
    Action,
    Dialog,
    DualDialog,
    PageBreak,
    Screenplay,
    Section,
    Slug,
    Transition,
)

fse_marker_re = re.compile(r"\[\[\s*FSE\s")  # §2: marker after leading ws


@dataclass
class FseNote:
    text: str  # raw note content between [[ and ]]
    line: int  # 1-based source line of the [[ (the cue line for reports)
    end_line: int
    placement: str  # standalone | glued | inline | title-page
    element: object | None = None  # Dialog / Action / Slug ... None if standalone
    element_kind: str = ""  # action, dialogue, parenthetical, lyrics, cue, ...
    element_line: int = 0  # line within the element (dialogue: block index)
    word: int = 0  # words before the note on that line: cue is before word N
    speaker: str | None = None  # dialogue/parenthetical only (§6.2)
    scene: int = 0  # scene index: count of scene boundaries before it
    preceded_by_content: bool = False  # §5.6 PRESET top-of-scene test


@dataclass
class Report:
    code: str
    line: int
    detail: str


@dataclass
class Extraction:
    notes: list[FseNote] = field(default_factory=list)
    reports: list[Report] = field(default_factory=list)
    # Ordered stream of ("element", obj) and ("note", FseNote): the timeline
    # input. Inline/glued notes appear right after their element.
    stream: list[tuple[str, object]] = field(default_factory=list)


# ---------------------------------------------------------------- lines


def _strip_boneyard_keep_lines(content: str) -> tuple[str, list[int]]:
    """fountain.parse's boneyard removal, plus the original 1-based line
    number of every line in the result (boneyard can swallow newlines)."""
    out: list[str] = []
    line_of: list[int] = [1]
    orig_line, pos = 1, 0
    for m in itertools.chain(boneyard_re.finditer(content), [None]):
        end = m.start() if m else len(content)
        chunk = content[pos:end]
        # walk the kept chunk, recording original line at each new line
        for i, _piece in enumerate(linebreak_re.split(chunk)):
            if i:
                orig_line += 1
                line_of.append(orig_line)
        out.append(chunk)
        if m:
            orig_line += len(linebreak_re.findall(m.group(0)))
            pos = m.end()
    return "".join(out), line_of


# ------------------------------------------------------------ paragraph


def _cut_notes(raw: str) -> tuple[str, list[tuple[re.Match[str], int]]]:
    """note_re.sub('', raw), also returning each note with its offset in
    the stripped text. Identical result to the real parser's sub."""
    kept, cuts, pos, removed = [], [], 0, 0
    for m in note_re.finditer(raw):
        kept.append(raw[pos : m.start()])
        cuts.append((m, m.start() - removed))
        removed += m.end() - m.start()
        pos = m.end()
    kept.append(raw[pos:])
    return "".join(kept), cuts


def _is_fse(note_text: str) -> bool:
    return fse_marker_re.match(note_text) is not None


def _note_only(raw: str, m: re.Match[str]) -> bool:
    """The note's start line has only whitespace/notes before it, and its
    end line only whitespace/notes after it."""
    ls = raw.rfind("\n", 0, m.start()) + 1
    le = raw.find("\n", m.end())
    le = len(raw) if le == -1 else le
    return (
        note_re.sub("", raw[ls : m.start()]).strip() == ""
        and note_re.sub("", raw[m.end() : le]).strip() == ""
    )


def _locate(elem: object, elem_line: int) -> tuple[str, str | None]:
    """Kind of the element line a note sits in, and the speaker if any."""
    if isinstance(elem, Dialog):
        if elem_line == 0:
            return "cue", None
        paren, _text = elem.blocks[elem_line - 1]
        return ("parenthetical" if paren else "dialogue"), str(elem.character)
    if isinstance(elem, Action):
        if elem.centered:
            return "centred", None
        line = str(elem.lines[elem_line]) if elem_line < len(elem.lines) else ""
        return ("lyrics" if line.startswith("~") else "action"), None
    return {
        Slug: "scene-heading",
        Section: "section",
        Transition: "transition",
        PageBreak: "page-break",
    }.get(type(elem), "unknown"), None


ALLOWED = {"action", "dialogue", "parenthetical", "lyrics"}
CONTENT = (Action, Dialog, DualDialog, Transition)  # centred is an Action


def extract(stream: StringIO) -> tuple[Screenplay, Extraction]:
    content = stream.read()
    content, line_of = _strip_boneyard_keep_lines(content)
    lines = linebreak_re.split(content)
    numbered = list(zip(line_of, lines, strict=True))
    ex = Extraction()

    numbered = list(itertools.dropwhile(lambda nl: nl[1].strip() == "", numbered))
    numbered = [(n, _preprocess_line(s)) for n, s in numbered]
    tp = list(takewhile(lambda nl: nl[1] != "", numbered))

    # Title page: §6.6 E12 for any FSE note, E21 for an unclosed one.
    # Checked before parse_title_page, which may raise ValueError on a
    # note-only line; the E12 then explains the failure instead.
    tp_raw = "\n".join(s for _, s in tp)
    try:
        title_page = parse_title_page([s for _, s in tp])
        title_error = None
    except ValueError as e:
        title_page, title_error = {}, e
    if title_page:
        for m in note_re.finditer(tp_raw):
            if _is_fse(m.group(0)):
                ln = tp[tp_raw.count("\n", 0, m.start())][0]
                ex.reports.append(Report("E12", ln, "FSE note in the title page"))
        body = numbered[len(tp) :]
    else:
        body = numbered
    if title_error is not None:
        # Real parser raises here; FSE turns it into E12 if a note caused it.
        if not ex.reports:
            for m in note_re.finditer(tp_raw):
                if _is_fse(m.group(0)):
                    ln = tp[tp_raw.count("\n", 0, m.start())][0]
                    ex.reports.append(Report("E12", ln, "FSE note in the title page"))
        if not ex.reports:
            raise title_error
        return Screenplay({}, []), ex

    paragraphs = _parse_body(body, ex)
    return Screenplay(title_page, paragraphs), ex


def _parse_body(body, ex: Extraction):
    paragraphs = []
    scene, has_content = 0, False

    for blank, group in itertools.groupby(body, lambda nl: _is_blank(nl[1])):
        if blank:
            continue
        group = list(group)
        raw = "\n".join(s for _, s in group)
        stripped, cuts = _cut_notes(raw)

        # E21: [[FSE with no ]] before the empty line that ended the paragraph
        for m in fse_marker_re.finditer(stripped):
            ln = group[raw.count("\n", 0, raw.find(m.group(0)))][0]
            ex.reports.append(Report("E21", ln, "unclosed FSE note"))

        fse = [(m, off) for m, off in cuts if _is_fse(m.group(0))]

        def mk(m, off, placement, raw=raw, group=group):
            first = raw.count("\n", 0, m.start())
            last = raw.count("\n", 0, m.end())
            return FseNote(
                text=m.group(0)[2:-2],
                line=group[first][0],
                end_line=group[last][0],
                placement=placement,
            )

        if _is_blank(stripped):  # the real parser skips it: standalone
            for m, off in fse:
                n = mk(m, off, "standalone")
                n.scene, n.preceded_by_content = scene, has_content
                has_content = True
                ex.notes.append(n)
                ex.stream.append(("note", n))
            continue

        all_note_only = bool(cuts) and stripped.strip() == ""
        before_len = len(paragraphs)
        before_last = paragraphs[-1] if paragraphs else None
        InputParagraph(stripped.split("\n")).update_list(paragraphs)

        # Which element did this paragraph become?
        if len(paragraphs) == before_len and paragraphs[-1] is before_last:
            elem, synopsis = before_last, True  # merged as a synopsis
        else:
            elem, synopsis = paragraphs[-1], False
            if isinstance(elem, DualDialog):
                elem = elem.right
        new = paragraphs[before_len:] or [paragraphs[-1]]

        # Scene boundaries reset the PRESET window before any note in them.
        if any(isinstance(p, (Slug, Section)) for p in new) and not synopsis:
            scene += 1
            has_content = False

        # all_note_only: stacked note-only lines the real parser does NOT
        # skip ("[[a]]\n[[b]]" leaves "\n"), so they become an empty Action.
        for m, off in fse:
            only = _note_only(raw, m)
            placement = "standalone" if all_note_only else "glued" if only else "inline"
            n = mk(m, off, placement)
            sline = stripped.count("\n", 0, off)
            col = off - (stripped.rfind("\n", 0, off) + 1)
            n.element, n.element_line = elem, sline
            n.word = len(stripped.split("\n")[sline][:col].split())
            if synopsis:
                n.element_kind = "synopsis"
            elif all_note_only:
                n.element_kind = "(empty action)"
            else:
                n.element_kind, n.speaker = _locate(elem, sline)
            if n.element_kind not in ALLOWED and not all_note_only:
                ex.reports.append(
                    Report("E12", n.line, f"FSE note in {n.element_kind}")
                )
            if placement == "glued":
                ex.reports.append(Report("W09", n.line, "glued FSE note"))
            # Content before it: anything earlier in the scene, or any text
            # earlier in this element (a dialogue cue counts as content).
            before = stripped[:off].strip()
            n.scene = scene
            n.preceded_by_content = has_content or bool(before)
            ex.notes.append(n)

        if not synopsis:
            for p in new:
                ex.stream.append(("element", p))
            if any(isinstance(p, CONTENT) for p in new) and not all_note_only:
                has_content = True
        ex.stream.extend(("note", n) for n in ex.notes[len(ex.notes) - len(fse) :])
        if fse:
            has_content = True

    return paragraphs


# --------------------------------------------------------------- checks


def _dump(sp: Screenplay) -> str:
    """Structural dump of a Screenplay, for byte-identity comparison."""

    def d(p):
        if isinstance(p, DualDialog):
            return ("Dual", d(p.left), d(p.right))
        if isinstance(p, Dialog):
            return ("Dialog", repr(p.character), [(a, repr(b)) for a, b in p.blocks])
        return (
            type(p).__name__,
            repr(getattr(p, "lines", None)),
            getattr(p, "synopsis", None),
            getattr(p, "level", None),
            getattr(p, "centered", None),
            repr(getattr(p, "scene_number", None)),
        )

    return repr((sp.title_page, [d(p) for p in sp.paragraphs]))


def compare(path: str) -> bool | str:
    text = open(path, encoding="utf-8").read()
    try:
        real = _dump(fountain.parse(StringIO(text)))
    except ValueError as e:
        real = f"ValueError {e}"
    try:
        sp, ex = extract(StringIO(text))
        proto = _dump(sp)
        if real.startswith("ValueError") and not sp.paragraphs and ex.reports:
            return "crash replaced by E12"
    except ValueError as e:
        proto = f"ValueError {e}"
    return real == proto


def show(path: str) -> None:
    _sp, ex = extract(StringIO(open(path, encoding="utf-8").read()))
    print(f"== {path}")
    print(f"   identical to fountain.parse: {compare(path)}")
    for n in ex.notes:
        where = (
            f"{n.element_kind} line {n.element_line} before word {n.word}"
            if n.element is not None
            else "between elements"
        )
        spk = f" speaker={n.speaker}" if n.speaker else ""
        pre = " after-content" if n.preceded_by_content else " TOP-OF-SCENE"
        lines = f"{n.line}" + (f"-{n.end_line}" if n.end_line != n.line else "")
        print(
            f"   L{lines:<6} scene {n.scene} {n.placement:<10} {where}{spk}{pre}"
            f"\n            [[{' '.join(n.text.split())}]]"
        )
    for r in ex.reports:
        print(f"   {r.code} line {r.line}: {r.detail}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        show(p)
