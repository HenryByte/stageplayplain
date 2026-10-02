# Stage Play Fountain

Conventions for writing stage plays in [Fountain](https://fountain.io).

The goal is to stay faithful to Fountain's philosophy: plain text first,
minimal new syntax, readable without formatting. Almost everything here is
already valid Fountain; a stage play file opens sensibly in any Fountain tool.

## Declaring a stage play

Add a `Format` key to the title page:

```text
Title: The Visitor
Author: Jane Doe
Format: Stage Play
```

`Stage Play` and `Stageplay` are accepted, in any case. With Screenplain, the
`--stageplay` flag does the same for files without the key.

## Document structure

A stage play has two parts, separated by the first `===` on a line of its own:

1. **Front matter** — everything before the first `===`.
2. **Play body** — everything after it.

`===` is Fountain's page break, so other tools show a page break there, which
is also where the play begins. Any later `===` is an ordinary page break. If
there is no `===`, the whole document is the play body.

## Front matter

Front matter is divided into sections with `#` headings:

```text
# Notes

Dashes indicate interrupted speech.

# Dramatis Personae

@Mary
A teacher.

@Mrs. Danvers
The housekeeper.

## Others

John

# Time

The present.

# Setting

A small cottage on the coast.
```

Any heading is allowed and is rendered as a section of prose. Text before the
first heading is rendered without a heading.

### Cast list

A section named `Dramatis Personae`, `Cast`, `Characters` or
`Cast of Characters` (any case) is a cast list. Each entry is a paragraph,
separated from the next by a blank line:

* A name followed by description lines: `@Mary` / `A teacher.`
* A name on its own: `John`
* `##` headings group characters, e.g. `## Others`.

A paragraph of several lines that isn't a name with a description is
rendered as prose.

Entries must be separated by blank lines. Two upper-case names on adjacent
lines (`MARCELLUS` / `BERNARDO`) would read as a name with a description.

## Play body

All existing Fountain syntax works in the body.

| Source | Meaning |
|---|---|
| `# Act One` | Act. Starts a new page. |
| `## The Drawing Room` | Scene. Printed as written; no automatic numbering. |
| `###` and deeper | Rendered like scenes. |
| `INT. HOUSE - DAY` (sluglines) | Scene. Scene numbers (`#12#`) are dropped. |
| Plain paragraphs | Stage directions. |
| `@Mary` + lines | Dialogue. |
| `@Hamlet (aside)` | Dialogue with an extension. |
| `(She turns.)` in dialogue | Parenthetical, printed inline. |
| `> CURTAIN.` | Transition, right-aligned. |
| `> THE END <` | Centered text. |
| `^` after a cue | Dual dialogue, side by side. |
| `===` | Page break. |

### Character names

Write character cues with Fountain's `@` prefix, so names can be written in
their natural case:

```text
@Mary
Has he arrived?

@Mrs. Danvers
Not yet, madam.
```

Upper-case cues without `@` (`MARY`) still work.

Screenplay continuation markers in cues — `(CONT'D)`, `(CONTD)`, `(CONT.)`,
`(CONTINUED)`, in any case — are removed, along with the parentheses if
nothing else is left in them. Other extensions are kept: `MARY (O.S., CONT'D)`
becomes `MARY (O.S.)`.

Inside stage directions, `@` marks a character name:

```text
@Mrs. Danvers crosses to @Mary.
```

The name after `@` is matched against the names in the cast list and the
dialogue cues, longest first and ignoring case, so multi-word names work. An
unknown name is taken to be the single word after `@`. Names without `@` are
left as written.

**Gotcha:** a stage direction of two or more lines that *starts* with `@` is
read as dialogue (`@Mary enters.` would be a cue). Start it with `!` to force a
stage direction:

```text
!@Mary enters.
She looks around.
```

A single-line direction starting with `@` needs no `!`.

## Formatting

Stage play output follows the style of a published acting edition:

* A4, EB Garamond 12pt (Times with `--standard-font`).
* Title page, then the front matter flowing together, then the play body on a
  new page. Pages are numbered from the play body.
* Front matter headings and scene headings are centered small caps. Acts are
  upper case, centered, each on a new page.
* Cast list entries: `MARY, a teacher` — name in small caps, description in
  italic.
* Dialogue: the cue in small caps followed by a period, with the speech running
  on the same line; extensions and parentheticals in italic.
* Stage directions are italic and indented, with character names in roman
  small caps.

Supported outputs are PDF and HTML. FDX output is not supported for stage
plays yet.

## Possible future settings

* Page size (Letter, trade paperback).
* US manuscript style (centered cues, indented directions).
* Automatic scene numbering.
* Distinct styling for opening scene descriptions and for Time/Setting.
