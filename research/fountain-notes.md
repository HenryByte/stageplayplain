# Fountain `[[notes]]`: placement and parsing edge cases

Research for issue #12. Context: the Fountain Stage Extension (FSE, `stagecraft.md`) puts machine-readable directives inside Fountain notes. In particular, §6.2 relies on how a note on its own line directly under dialogue attaches. This file records what the Fountain spec and the reference tools actually do.

Researched 2026-10-14. All source links are pinned to the commit that was read.

## Sources

| Short name | What | Pinned source |
| --- | --- | --- |
| **Spec** | fountain.io syntax page (Fountain 1.1) | https://fountain.io/syntax/#notes |
| **ObjC** | Original Fountain parser (Nima Yousefi / Stu Maschwitz) | https://github.com/nyousefi/Fountain/tree/c09b65e9d4bf6cb1c672501f793b9b3f2becd452 |
| **aw-parser** | afterwriting's parser (`aw-parser` 0.1.1, used by afterwriting-labs) | https://github.com/afterwriting/aw-parser/tree/090e911c49599e0dbe41229e4f6a2c0f9639df8c |
| **BetterFountain** | VS Code extension, a TypeScript fork of the afterwriting parser | https://github.com/piersdeseilligny/betterfountain/tree/4f109ec1575c6ceb508a82310969f256cb41a0f7 |
| **fountain-js** | jonnygreenwald/fountain-js | https://github.com/jonnygreenwald/fountain-js/tree/a0e57b77344c4fc333bd3ca2a653a58a9d62e0c1 |
| **Jouvence** | Python parser and renderer | https://github.com/ludovicchabant/Jouvence/tree/5f7d2b346cff34eff26087a2241b3238d9a31d76 |
| **fountain-mode** | Emacs major mode | https://github.com/rnkn/fountain-mode/tree/74ddc5a783e8204beeda3343ea6725a3c198f4bc |
| **Beat** | macOS/iOS editor | https://github.com/lmparppei/Beat/tree/ef3e27a3f5beca7f8cb1a8ff65c79e5639dd3e14 |
| **obsidian-fountain** | Obsidian plugin with a PEG grammar | https://github.com/bgrundmann/obsidian-fountain/tree/9ce172b90e5ae9625f08306be097a5126ddea69a |
| **upstream screenplain** | vilcans/screenplain | https://github.com/vilcans/screenplain/tree/abf0d0800ab0b9dfd5bbe780137641e746afbad4 |
| **this repo** | `screenplain/parsers/fountain.py` on `master` (4a4810d) | local, behaviour checked by running it |

Highland and Betty are closed source, so they could not be checked at the source level. The only Highland note convention found comes from a secondary source (see §5).

---

## 1. What the spec says

The full text of the [Notes section](https://fountain.io/syntax/#notes):

> A Note is created by enclosing some text with double brackets. Notes can be inserted between lines, or in the middle of a line.
>
> *(example: an inline note at the end of an action sentence, then `[[It was supposed to be Vietnamese, right?]]` on its own line, with a blank line above and below, before `JACK`)*
>
> The empty lines around the Note on its own line would be removed in parsing.
>
> Notes can contain carriage returns, but if you wish a note to contain an empty line, you must place two spaces there to "connect" the element into one.
>
> Notes are designed to be compatible with the types of inserted annotation common in screenwriting software, e.g. Final Draft's Scriptnotes. To hide, or "comment out" sections of text, use the boneyard syntax.

Other spec text that applies to notes:

- [Error handling](https://fountain.io/syntax/#error-handling): "it won't look past a double line break for a closing syntactical element, preventing you from turning half your screenplay into a comment, or italics. The exception to this rule is the /* boneyard */ wrapper."
- [Boneyard](https://fountain.io/syntax/#boneyard): `/* … */` "will be ignored completely on formatted output" and "is the exception to the rule of syntax not carrying across line breaks."
- [Character](https://fountain.io/syntax/#character): "any line entirely in uppercase, with one empty line before it and without an empty line after it."
- [Dialogue](https://fountain.io/syntax/#dialogue): "any text following a Character or Parenthetical element."

The spec does not address:

- nesting
- `]]` or `[[` inside a note, or any escaping
- notes on the title page, in character cues or in scene headings
- what a note-only line *without* surrounding blank lines attaches to
- how notes and boneyard interact

Every answer below on those points comes from tool behaviour, not from the spec.

---

## 2. Spanning lines, blank lines, and what breaks a note

### Spec rule
Notes may span lines. A truly empty line ends the note, so a note that should contain one must use a line of two spaces instead.

### Tool behaviour

| Tool | Multi-line note | Empty line inside | Closing rule, nesting, `]]` |
| --- | --- | --- | --- |
| **ObjC** (FastFountainParser) | A *standalone* note is recognised only when it is a single line with no `]` inside: regex `^\s*\[{2}\s*([^\]\n])+\s*\]{2}\s*$` ([FastFountainParser.m L288-294](https://github.com/nyousefi/Fountain/blob/c09b65e9d4bf6cb1c672501f793b9b3f2becd452/Fountain/FastFountainParser.m#L288-L294)). Inline notes are stripped at HTML render time with `\[{2}(.*?)\]{2}`, where `.` does not match a newline ([FNHTMLScript.m L254](https://github.com/nyousefi/Fountain/blob/c09b65e9d4bf6cb1c672501f793b9b3f2becd452/Fountain/FNHTMLScript.m#L254)). The older regex parser accepts multi-line standalone notes via `\n\[{2}([^<>]+?)\]{2}\n` ([FountainRegexes.m L66](https://github.com/nyousefi/Fountain/blob/c09b65e9d4bf6cb1c672501f793b9b3f2becd452/Fountain/FountainRegexes.m#L66)). | The old regex parser allows one, since `[^<>]` matches `\n`. The fast parser does not. | Non-greedy, so the first `]]` closes the note. No nesting. |
| **aw-parser** (afterwriting) | Yes. When notes are hidden, it rewrites `[[` to ` /*` and `]]` to `*/` *before* splitting lines ([parser.js L40-42](https://github.com/afterwriting/aw-parser/blob/090e911c49599e0dbe41229e4f6a2c0f9639df8c/parser.js#L40-L42)), so notes become boneyard. | Yes. A note can span any number of blank lines, against the spec. | Nesting is counted (`nested_comments`, [L70-79](https://github.com/afterwriting/aw-parser/blob/090e911c49599e0dbe41229e4f6a2c0f9639df8c/parser.js#L70-L79), [L89](https://github.com/afterwriting/aw-parser/blob/090e911c49599e0dbe41229e4f6a2c0f9639df8c/parser.js#L89)), so `[[a [[b]] c]]` is one note. An unclosed `[[` hides the rest of the script. |
| **BetterFountain** | No. `note_inline` is `(?:\[{2}(?!\[+))([\s\S]+?)(?:\]{2}(?!\[+))` ([afterwriting-parser.ts L57](https://github.com/piersdeseilligny/betterfountain/blob/4f109ec1575c6ceb508a82310969f256cb41a0f7/src/afterwriting-parser.ts#L57)), but it is applied to one line token at a time ([L335-375](https://github.com/piersdeseilligny/betterfountain/blob/4f109ec1575c6ceb508a82310969f256cb41a0f7/src/afterwriting-parser.ts#L335-L375)). | n/a | The first `]]` closes the note. `[[[` and `]]]` are excluded by lookahead. |
| **fountain-js** | Yes, within one blank-line-separated block. `note_inline` is `\[{2}(?!\[+)([\s\S]+?)]{2}(?!\[+)`. A block that is entirely a note uses `note: /^\[{2}(?!\[+)(.+)]{2}(?!\[+)$/`, which is single-line only ([rules.ts L34-35](https://github.com/jonnygreenwald/fountain-js/blob/a0e57b77344c4fc333bd3ca2a653a58a9d62e0c1/src/rules.ts#L34-L35)). | No. The script is split on blank lines first. | The first `]]` closes the note. |
| **Jouvence** | Yes. `\[\[(?P<text>.+?)\]\]` with `re.DOTALL`, applied to each element's text at render time, which turns notes into footnotes ([renderer.py L130](https://github.com/ludovicchabant/Jouvence/blob/5f7d2b346cff34eff26087a2241b3238d9a31d76/jouvence/renderer.py#L130), [L143](https://github.com/ludovicchabant/Jouvence/blob/5f7d2b346cff34eff26087a2241b3238d9a31d76/jouvence/renderer.py#L143)). | Only within one element. | The first `]]` closes the note. |
| **fountain-mode** | Yes. `\[\[[\s\t]*\(\(?:\s\s\n\|.\n?\)*?\)[\s\t]*]]` ([fountain-mode.el L887-891](https://github.com/rnkn/fountain-mode/blob/74ddc5a783e8204beeda3343ea6725a3c198f4bc/fountain-mode.el#L887-L891)). | No. Only a two-space line is allowed, exactly as the spec says. | The first `]]` closes the note. |
| **Beat** | Yes, with special block tracking (`noteIn`/`noteOut`). | No. Hitting an empty line cancels the block ([ContinuousFountainParser+Notes.m L164](https://github.com/lmparppei/Beat/blob/ef3e27a3f5beca7f8cb1a8ff65c79e5639dd3e14/Frameworks/BeatParsing/BeatParsing/Parsing/Extensions/ContinuousFountainParser%2BNotes.m#L164)). | The first `]]` closes the note. A `[[` seen before a `]]` on a line means that line cannot terminate the block ([Line+Notes.m](https://github.com/lmparppei/Beat/blob/ef3e27a3f5beca7f8cb1a8ff65c79e5639dd3e14/Frameworks/BeatParsing/BeatParsing/Parsing/Assisting%20classes/Line%20Extensions/Line%2BNotes.m)). |
| **obsidian-fountain** | Yes. `NoteText = (!("]]"/"\n\n") .)*` and the closing `"]]"?` is *optional*, so an unclosed note ends at a blank line ([parser.peggy L143-148](https://github.com/bgrundmann/obsidian-fountain/blob/9ce172b90e5ae9625f08306be097a5126ddea69a/src/fountain/parser.peggy#L143-L148)). | No | The first `]]` closes the note. |
| **screenplain** (upstream and this repo) | Yes, within one paragraph. Lines are grouped by blank lines and then `\[\[.*?\]\]` (DOTALL) is removed from each group ([upstream L279](https://github.com/vilcans/screenplain/blob/abf0d0800ab0b9dfd5bbe780137641e746afbad4/screenplain/parsers/fountain.py#L279); this repo `fountain.py:47`, `:290`). | A two-space line works. An empty line splits the paragraph, so `[[` and `]]` print literally. The upstream test `tests/files/notes.fountain` locks this in. | The first `]]` closes the note, and nesting fails (see §6). |

### Agreement across tools
- The first `]]` closes the note in every tool. None supports escaping.
- An empty line ends or invalidates a note everywhere except aw-parser.
- Only aw-parser handles nesting.
- `]]` or `[[` inside a quoted value breaks the note in every tool. FSE §2.3 already forbids `[` and `]` in values, which is the right rule. A lone `]` would be safe in most tools, but `]]]` and `[[[` are treated specially by fountain-js and BetterFountain, so the blanket ban should stay.

---

## 3. Where notes can appear

The spec says only "between lines, or in the middle of a line". In practice:

| Location | Tool behaviour |
| --- | --- |
| **Inline in action or dialogue** | Supported everywhere. Notes are removed from (or footnoted in) the element text, and the surrounding text keeps whatever whitespace remains. In screenplain, `Yorick! [[x]] I knew` becomes `Yorick!  I knew`, with a double space. aw-parser eats one space on each side ([L41](https://github.com/afterwriting/aw-parser/blob/090e911c49599e0dbe41229e4f6a2c0f9639df8c/parser.js#L41)). |
| **Parenthetical** | Text-level, so it works in screenplain: `(aside [[FSE …]])` becomes `(aside )`. Most other tools strip notes from all text the same way. |
| **Character cue** | Works in screenplain because notes are stripped *before* classification: `HAMLET [[x]]` becomes the cue `HAMLET`. A note *between* a name and its extension leaves a double space, as in `HAMLET  (V.O.)`. In tools that classify before stripping, a cue containing a lowercase note is no longer "entirely uppercase". aw-parser's character regex `^([A-Z*_]+[0-9A-Z (._\-')]*)` does not even match `[` ([parser.js L17](https://github.com/afterwriting/aw-parser/blob/090e911c49599e0dbe41229e4f6a2c0f9639df8c/parser.js#L17)), but it only sees the cue after notes have been rewritten to boneyard. **Avoid notes in cues.** |
| **Scene heading** | Works in screenplain: `INT. HOUSE - DAY [[…]]` becomes the slug `INT. HOUSE - DAY`. In ObjC, fountain-js and BetterFountain the note stays in the heading text until render time. Scene-number detection (`#1#` at end of line) can break if the note comes after the number. **Avoid.** |
| **Title page** | Unspecified. In screenplain (this repo and upstream), notes are **not** stripped from title-page values: `Title: Hamlet [[x]]` keeps the note text. A note-only line inside the title page raises `ValueError: Invalid title page format` (`fountain.py:264-270`, `:336-338`). **Avoid.** |
| **Standalone line** | Supported everywhere, with the attachment caveats in §4. |

---

## 4. Note on its own line with no blank line around it

This is the case FSE §6.2 depends on. The spec says nothing about it directly. The closest text is "Dialogue is any text following a Character or Parenthetical element" together with its example, which places blank lines around a standalone note. The tools disagree.

### A. Note line directly *under* dialogue

```
HAMLET
Are you fair?
[[FSE ARRIVE ophelia]]
```

| Tool | Result |
| --- | --- |
| **this repo / upstream screenplain** | It stays in the dialogue block. The note is stripped and leaves an **empty dialogue line**: `Dialog(blocks=[…'Are you fair?', …''])`, verified by running it. If text follows on the next line, the dialogue continues with an empty line in the middle. |
| **ObjC FastFountainParser** | The note is appended to the Dialogue element's text, because the `Comment` rule requires `newlinesBefore > 0` ([L288-289](https://github.com/nyousefi/Fountain/blob/c09b65e9d4bf6cb1c672501f793b9b3f2becd452/Fountain/FastFountainParser.m#L288-L289), [L435-457](https://github.com/nyousefi/Fountain/blob/c09b65e9d4bf6cb1c672501f793b9b3f2becd452/Fountain/FastFountainParser.m#L435-L457)). It is later stripped in HTML output. |
| **aw-parser** | The line becomes ` ` after note-to-boneyard rewriting, which counts as an **empty line**: a separator that **ends the dialogue** ([L107-121](https://github.com/afterwriting/aw-parser/blob/090e911c49599e0dbe41229e4f6a2c0f9639df8c/parser.js#L107-L121)). The note therefore behaves as standalone. |
| **BetterFountain** | It is a dialogue token marked `ignore`, so the dialogue continues ([L357-365](https://github.com/piersdeseilligny/betterfountain/blob/4f109ec1575c6ceb508a82310969f256cb41a0f7/src/afterwriting-parser.ts#L357-L365)). |
| **fountain-js** | It is part of the dialogue block, rendered as an HTML comment inside the dialogue ([lexer.ts L194](https://github.com/jonnygreenwald/fountain-js/blob/a0e57b77344c4fc333bd3ca2a653a58a9d62e0c1/src/lexer.ts#L194)). |
| **Jouvence** | It stays in the dialogue text, because `_DialogState` reads until an empty line ([parser.py L257-275](https://github.com/ludovicchabant/Jouvence/blob/5f7d2b346cff34eff26087a2241b3238d9a31d76/jouvence/parser.py#L257-L275)), and is rendered as a footnote marker. |

**Conclusion:** five of six tools keep it inside the dialogue block. afterwriting is the exception and treats it as a separator. FSE §6.2's reading ("belongs to that dialogue block") matches the majority and the spec's definition of Dialogue. It is still tool-dependent, so the §6.2 recommendation of a blank line before standalone notes is well founded.

### B. Note line directly *above* a character cue

```
[[FSE ENTER hamlet from=vom-a]]
HAMLET
Hi.
```

| Tool | Result |
| --- | --- |
| **this repo / upstream screenplain** | **Breaks the dialogue.** The note is stripped and leaves the paragraph `['', 'HAMLET', 'Hi.']`. `append_dialog` then tests `''.isupper()`, which is False (`fountain.py:146-154`), so the whole block becomes **Action** (verified). |
| **ObjC** | Without a blank line before the note, the note line is not a Comment and merges into the previous element ([L461-475](https://github.com/nyousefi/Fountain/blob/c09b65e9d4bf6cb1c672501f793b9b3f2becd452/Fountain/FastFountainParser.m#L461)). With a blank line before it, it becomes a Comment and does **not** reset `newlinesBefore`, so the following `HAMLET` is still a Character. Notes are transparent in that case. |
| **aw-parser** | The note line becomes a separator, so `HAMLET` counts as "separated" and the cue still works. |
| **fountain-js** | The block starts with `[[…`. The dialogue regex requires the first line to be the cue, `[^^()\na-z]+`, so a note with lowercase text makes the block Action. An all-uppercase note would become the character name ([rules.ts L23](https://github.com/jonnygreenwald/fountain-js/blob/a0e57b77344c4fc333bd3ca2a653a58a9d62e0c1/src/rules.ts#L23)). |
| **BetterFountain** | The character regex explicitly rejects lines starting with `[[` ([L45](https://github.com/piersdeseilligny/betterfountain/blob/4f109ec1575c6ceb508a82310969f256cb41a0f7/src/afterwriting-parser.ts#L45)). The following line is then not "separated", so the cue is likely lost. |

**Conclusion:** a note directly above a cue is unsafe in this repo and in fountain-js. FSE §6.1 standalone notes should have a blank line both **before and after**, or this repo's parser should drop note-only lines before classifying a paragraph. This is the pattern FSE uses for `[[FSE ENTER …]]` before a speech, so it matters.

### C. Note line between two action lines (no blank lines)
In screenplain this produces an Action with an empty middle line, `['Act line one.', '', 'Act line two.']` (verified), which renders as a visible blank line.

---

## 5. Notes and boneyard

The spec says only that boneyard is for commenting out and notes are for annotation. It defines no interaction between them.

| Tool | Order and interaction |
| --- | --- |
| **this repo / upstream** | Boneyard is removed from the **whole file first** with a non-greedy DOTALL regex (`fountain.py:31`, `:247`), and notes are removed per paragraph afterwards. Results:<br>• A note inside boneyard disappears, which is what FSE §6.5 wants (verified).<br>• `/*` *inside a note* opens a boneyard: `[[note /* x ]] y */` becomes `[[note ` followed by the rest of the line, leaving a dangling `[[` (verified). |
| **ObjC** | Boneyard is a line-oriented state: a line starting with `/*` opens it and a line ending in `*/` closes it ([L234-269](https://github.com/nyousefi/Fountain/blob/c09b65e9d4bf6cb1c672501f793b9b3f2becd452/Fountain/FastFountainParser.m#L234-L269)). Mid-line `/*` is not boneyard in the fast parser. |
| **aw-parser** | Hidden notes **are** boneyard: `[[`/`]]` are rewritten to `/*`/`*/` and nesting is counted together with real boneyard ([L41](https://github.com/afterwriting/aw-parser/blob/090e911c49599e0dbe41229e4f6a2c0f9639df8c/parser.js#L41), [L89](https://github.com/afterwriting/aw-parser/blob/090e911c49599e0dbe41229e4f6a2c0f9639df8c/parser.js#L89)). A literal `*/` inside a note closes it early. |
| **fountain-js** | Boneyard `/\*[\S\s]*?\*\//g` is stripped from the whole source first ([lexer.ts L36-53](https://github.com/jonnygreenwald/fountain-js/blob/a0e57b77344c4fc333bd3ca2a653a58a9d62e0c1/src/lexer.ts#L36-L53)), which is the same order as screenplain. |
| **Jouvence** | Boneyard is recognised only when `/*` starts a line ([parser.py L415-430](https://github.com/ludovicchabant/Jouvence/blob/5f7d2b346cff34eff26087a2241b3238d9a31d76/jouvence/parser.py#L415-L430)). |

**Implication for FSE:** `/` and `*` are legal in FSE bare and quoted values, so `label="a/*b"` would start a boneyard in screenplain, fountain-js and aw-parser and hide the rest of the script up to the next `*/`. FSE should forbid `/*` and `*/` inside FSE notes, as it does for `[` and `]`.

**Related risk, emphasis before notes:** ObjC ([FNHTMLScript.m L246-254](https://github.com/nyousefi/Fountain/blob/c09b65e9d4bf6cb1c672501f793b9b3f2becd452/Fountain/FNHTMLScript.m#L246-L254)), Jouvence ([renderer.py L140-143](https://github.com/ludovicchabant/Jouvence/blob/5f7d2b346cff34eff26087a2241b3238d9a31d76/jouvence/renderer.py#L140-L143)) and fountain-js all apply `*` and `_` emphasis **before** handling notes. An `_` in an FSE id such as `vom_1`, paired with an `_` outside the note on the same line, can therefore produce unbalanced underline markup in those renderers. screenplain strips notes before emphasis, so it is not affected (verified: `*bold [[n]] still*` keeps its italics).

---

## 6. This repo's parser, concretely

`screenplain/parsers/fountain.py` on master behaves the same as upstream screenplain (note support was added upstream in aa4119c, "Add supports for notes", and is unchanged).

1. **L247:** `boneyard_re = r"/\*.*?\*/"` (DOTALL) is removed from the raw file before anything else.
2. **L264-270:** the title page is parsed with **no note stripping**.
3. **L288-290:** the body is grouped into paragraphs by blank lines, where blank means `""` or `" "` (`_is_blank`, L236-237). A two-space line is *not* blank, which is how the spec's two-space trick works. Each paragraph is joined with `\n` and `note_re = r"\[\[.*?\]\]"` (DOTALL, L47) is removed.
4. **L291-292:** a paragraph that becomes empty or `" "` after stripping is dropped. This is how standalone notes with blank lines around them disappear.
5. The remaining text is split back into lines and classified. **Notes leave no trace in the output AST.** Their positions are discarded, so FSE support will need a separate pass, or a change here that records note text and its anchor (paragraph, line and column).

Edge cases, verified by running the parser:

| Input | Result |
| --- | --- |
| `Alas! [[FSE …]] I knew` | Dialog line `Alas!  I knew` (double space) |
| note line under dialogue | an extra empty dialogue line |
| note line above a cue (no blank) | **the whole block becomes Action** |
| `HAMLET [[n]] (V.O.)` | cue `HAMLET  (V.O.)` |
| `(aside [[…]])` | parenthetical `(aside )` |
| `INT. HOUSE - DAY [[…]]` | slug `INT. HOUSE - DAY` |
| `[[a [[b]] c]]` | `Act  c]] end.` (nesting fails and leaks) |
| `label="a]]b"` | leaks `b"]]` into the text |
| `label="a]b"` | stripped cleanly (a single `]` is fine) |
| empty line inside a note | the note is not recognised, and `[[` and `]]` print literally |
| two-space line inside a note | stripped cleanly |
| `[[n /* x ]] y */` | `[[n ` dangles, because boneyard was stripped first |
| note inside `/* */` | gone |
| `Title: X [[n]]` | the note is kept in the title value |
| note-only line in the title page | `ValueError` |

---

## 7. Prior art for structured notes

There is no standard. Several tools give meaning to the leading word of a note. Each uses a loose prefix match, which is a reason for FSE's strict, case-sensitive `FSE ` marker (§2.6).

- **Beat** classifies every note by prefix in `BeatNoteData.withNote` ([BeatNoteData.m L29-46](https://github.com/lmparppei/Beat/blob/ef3e27a3f5beca7f8cb1a8ff65c79e5639dd3e14/Frameworks/BeatParsing/BeatParsing/Parsing/Assisting%20classes/BeatNoteData.m#L29-L46)):
  - `[[marker …]]` or `[[marker red: text]]`
  - `[[color …]]` or a bare colour name
  - `[[beat …]]` or `[[storyline …]]`
  - `[[page …]]`
  - `[[red: text]]` or `[[#hex: text]]`

  It exports these as JSON with type, range and content (L66-74). The match is case-insensitive `rangeOfString:… == 0`, so `[[Markers are wrong here]]` is classed as a marker. The marker syntax is documented in a comment as `[[marker color:Content]]` ([ContinuousFountainParser.m L947-950](https://github.com/lmparppei/Beat/blob/ef3e27a3f5beca7f8cb1a8ff65c79e5639dd3e14/Frameworks/BeatParsing/BeatParsing/Parsing/ContinuousFountainParser.m#L947-L950)).
- **Beat document settings** are machine-readable JSON in a trailing **boneyard** block, `/* If you're seeing this, you can remove the following stuff - BEAT: {json} END_BEAT */` ([BeatDocumentSettings.m L18-19](https://github.com/lmparppei/Beat/blob/ef3e27a3f5beca7f8cb1a8ff65c79e5639dd3e14/Frameworks/BeatParsing/BeatParsing/ScreenplayData/BeatDocumentSettings.m#L18-L19)). This is prior art for hiding data in boneyard rather than notes.
- **obsidian-fountain** has a formal grammar for note kinds ([parser.peggy L150-157](https://github.com/bgrundmann/obsidian-fountain/blob/9ce172b90e5ae9625f08306be097a5126ddea69a/src/fountain/parser.peggy#L150-L157)):
  - `[[+…]]` and `[[-…]]`
  - `[[>target|text]]` for links
  - `[[@word]]` for margin marks
  - `[[kind: …]]`, e.g. `[[todo: …]]`

  The README suggests `[[@effect]]` and `[[@laugh]]` for performance scripts, rendered in the margin, which is close to FSE's prompt-book mode. Todos are listed per scene.
- **BetterFountain** collects every inline note into the containing scene or section's `notes` list along with its line number, for the outline view ([L335-355](https://github.com/piersdeseilligny/betterfountain/blob/4f109ec1575c6ceb508a82310969f256cb41a0f7/src/afterwriting-parser.ts#L335-L355)). This is prior art for attaching notes to a scene.
- **Highland** reportedly uses `[[%]]` notes as navigation "markers": "these markers are nothing more than Fountain notes consisting of a single percent symbol" ([TidBITS, 2015](https://tidbits.com/2015/05/18/writing-screenplays-with-highland/)). This is a secondary source, since Highland is closed.
- **fountain-mode** once had a `fountain-note-template` for timestamped or authored notes. It is now obsolete ([L281-283](https://github.com/rnkn/fountain-mode/blob/74ddc5a783e8204beeda3343ea6725a3c198f4bc/fountain-mode.el#L281-L283)).

No tool was found that parses key/value directives inside notes, and none attaches meaning to the word position of an inline note. FSE appears to be novel in both respects.

---

## 8. Recommendations for FSE (`stagecraft.md`)

1. **§6.1:** require a blank line both **before and after** a standalone FSE note. A note directly above a cue turns the speech into Action in screenplain and fountain-js.
2. **§6.2:** keep the "under dialogue attaches inline" rule, since it matches the spec's definition of Dialogue and five of six tools, but note that afterwriting treats such a line as a block separator. The existing SHOULD-blank-line advice stands.
3. **§2.3 and Appendix B:** keep the `[`/`]` ban, and also forbid `/*` and `*/` in note content. Consider forbidding `*` and `_` adjacent to note boundaries, or just document the emphasis-ordering risk.
4. **Single-line FSE notes:** the grammar already excludes newlines (`ws` is spaces and tabs only, and `qchar` excludes newline). State this explicitly, since multi-line notes vary most between tools (ObjC's fast parser, BetterFountain).
5. **Placement:** say FSE notes MUST NOT appear in the title page, in character cues or in scene headings.
6. **Implementation (this repo):** `parse_body` throws away note text and positions (L290). The FSE pass needs them, so capture notes before stripping, with paragraph and offset. Also drop note-only lines *before* classification, so that a note above a cue cannot demote dialogue to Action, and so that a note under dialogue does not add an empty dialogue line.
