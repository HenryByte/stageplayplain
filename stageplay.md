Below is a side-by-side comparison of the two forms. Since **Fountain** is a complete, text-based syntax for screenplays but **there is no widely adopted equivalent syntax for stage plays**, I've left the stage-play syntax column blank where appropriate.

| Element                  | Stage Play                                                          | Screenplay                                            | Fountain Syntax                             |
| ------------------------ | ------------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------- |
| **Title**                | Title page with playwright's name.                                  | Title page with writer's name.                        | `Title: My Script`<br>`Author: Jane Doe`    |
| **Cast List**            | Required at the beginning. Usually includes brief descriptions.     | Usually omitted. Characters are introduced in action. | *(No Fountain element.)*                    |
| **Dramatis Personae**    | Standard convention.                                                | Not used.                                             | *(No Fountain element.)*                    |
| **Setting Overview**     | Often includes a note describing the entire setting before Act One. | Rare. Each scene establishes its own setting.         | *(No Fountain element.)*                    |
| **Acts**                 | Common (Act I, Act II, etc.).                                       | Rare in modern film.                                  | `# Act One`                                 |
| **Scenes**               | Numbered or named scenes.                                           | Every location/time change becomes a new scene.       | `INT. KITCHEN - DAY`                        |
| **Scene Headings**       | "Scene 2. The Drawing Room."                                        | Sluglines.                                            | `INT. OFFICE - NIGHT`                       |
| **Time**                 | Often stated in setting notes.                                      | Part of every slugline.                               | `EXT. PARK - SUNSET`                        |
| **Action**               | Stage directions describe visible action and staging.               | Action lines describe visible cinematic action.       | Plain paragraphs.                           |
| **Dialogue**             | Character name followed by speech.                                  | Same.                                                 | `CHARACTER` then dialogue.                  |
| **Parentheticals**       | Frequently used for delivery.                                       | Used sparingly.                                       | `(whispering)`                              |
| **Stage Directions**     | Blocking, entrances, exits, props, lighting, etc.                   | Only physical action visible on screen.               | Plain action text.                          |
| **Entrances**            | Explicitly written.                                                 | Usually implied by action.                            | Plain action.                               |
| **Exits**                | Explicitly written.                                                 | Usually implied.                                      | Plain action.                               |
| **Lighting Cues**        | Often included.                                                     | Rarely included.                                      | *(No syntax.)*                              |
| **Sound Cues**           | May specify live effects or music.                                  | Sound only if dramatically important.                 | Plain action or ALL CAPS.                   |
| **Music Cues**           | Can specify live or recorded music.                                 | Usually left to production.                           | Plain action.                               |
| **Props**                | Important props may be noted.                                       | Mentioned only when story-relevant.                   | Plain action.                               |
| **Costume Notes**        | Sometimes specified.                                                | Rare unless plot-critical.                            | Plain action.                               |
| **Blocking**             | Common.                                                             | Avoided except essential movement.                    | Plain action.                               |
| **Set Changes**          | Explicit.                                                           | New location equals new scene.                        | New slugline.                               |
| **Intermission**         | May appear between acts.                                            | Not applicable.                                       | `# INTERMISSION` (optional section heading) |
| **Curtain**              | May end with "Blackout" or "Curtain."                               | Ends with "FADE OUT."                                 | `> FADE OUT.`                               |
| **Transitions**          | Rare.                                                               | Common.                                               | `> CUT TO:`                                 |
| **Shots**                | Never.                                                              | Occasionally if writer/director chooses.              | `> CLOSE ON:`                               |
| **Montage**              | Not applicable.                                                     | Common cinematic device.                              | `MONTAGE` or sequence of scenes.            |
| **Voice Over**           | Impossible (except theatrical devices).                             | Common.                                               | `JANE (V.O.)`                               |
| **Off Screen**           | Usually "offstage."                                                 | Off-screen dialogue.                                  | `JANE (O.S.)`                               |
| **Narrator**             | Common.                                                             | Rare.                                                 | Character dialogue.                         |
| **Asides**               | Common.                                                             | No direct equivalent.                                 | *(Blank)*                                   |
| **Soliloquies**          | Common.                                                             | Very rare.                                            | *(Blank)*                                   |
| **Monologues**           | Common.                                                             | Common.                                               | Standard dialogue.                          |
| **Audience Interaction** | Possible.                                                           | Impossible.                                           | *(Blank)*                                   |
| **Breaking Fourth Wall** | Direct address to audience.                                         | Speaking to camera.                                   | Action + dialogue.                          |
| **Scene Numbers**        | Optional.                                                           | Optional in shooting scripts.                         | `INT. HOUSE - DAY #12#`                     |
| **Dual Dialogue**        | Two actors may overlap naturally.                                   | Supported.                                            | `^` after second character.                 |
| **Lyrics**               | Written into dialogue.                                              | Written into dialogue.                                | Standard dialogue.                          |
| **Emphasis**             | Italics, underlining, capitalization.                               | ALL CAPS for emphasis.                                | `*italic*`, `**bold**`, `_underline_`       |
| **Notes to Director**    | Sometimes included.                                                 | Generally discouraged.                                | *(Blank)*                                   |
| **Production Notes**     | Sometimes appended.                                                 | Separate production documents.                        | *(Blank)*                                   |
| **Page Count**           | Approximately one minute per page (highly variable).                | Roughly one minute per page in Courier.               | Formatting convention.                      |

---

# Fountain Example

```fountain
Title: The Visit
Author: Jane Doe

# Act One

INT. APARTMENT - NIGHT

Rain lashes the windows.

JULIA sits alone.

BEN enters.

BEN
Mind if I sit?

JULIA
There are other chairs.

BEN
None of them look occupied.

> CUT TO:

EXT. STREET - NIGHT

The rain continues.

> FADE OUT.
```

---

# Equivalent Stage Play

```text
THE VISIT

by Jane Doe

CHARACTERS

JULIA
BEN

SETTING

A modest apartment in London.
Present day.

ACT ONE

Scene 1

(The lights rise on a sparsely furnished apartment.
Rain is heard against the windows.
JULIA sits at a table.)

BEN enters.

BEN
Mind if I sit?

JULIA
There are other chairs.

BEN
None of them look occupied.

(A pause.)

Blackout.
```

This is a good design problem because Fountain's core philosophy is *plain text first*. Any stage-play extensions should ideally:

* remain readable as plain text,
* degrade gracefully in existing Fountain parsers,
* avoid introducing lots of punctuation,
* preserve compatibility where possible.

Rather than trying to reproduce every theatrical formatting convention, I'd think in terms of adding semantic elements that Fountain currently lacks.

## 1. Cast List

This is probably the biggest omission.

Current Fountain has no concept of dramatis personae.

For example:

```text
@CAST

HAMLET
Prince of Denmark.

HORATIO
His friend.

OPHELIA
Daughter of Polonius.
```

or

```text
Character: HAMLET
Description: Prince of Denmark.

Character: HORATIO
Description: His friend.
```

I prefer a block syntax because descriptions can span paragraphs.

---

## 2. Dramatis Personae Groups

Grouping is common.

```text
@CAST

## The Royal Court

HAMLET
Prince of Denmark.

CLAUDIUS
King of Denmark.

GERTRUDE
Queen.

## Soldiers

MARCELLUS

BERNARDO
```

These headings could simply be Markdown headings inside the block.

---

## 3. Setting Overview

Many plays establish the permanent set before Act One.

Example:

```text
@SETTING

The entire play takes place in a decaying Victorian manor.

A large staircase dominates the rear wall.

Three doors lead to adjoining rooms.
```

This is different from scene action because it describes the production rather than the current moment.

---

## 4. Acts

Using Fountain sections is already pretty close.

```
# Act One

## Scene One
```

This may already be sufficient.

No extension required.

---

## 5. Scene Titles

Instead of sluglines:

```
## Scene 2

The Drawing Room.
```

or

```
SCENE 2

The Drawing Room.
```

Unlike films, locations don't necessarily reset every scene.

---

## 6. Entrances and Exits

These are extremely common in plays.

Instead of embedding them inside action:

```text
> ENTER HAMLET.
```

or perhaps

```text
@ENTER HAMLET
```

Similarly

```text
@EXIT OPHELIA
```

Multiple:

```text
@ENTER HAMLET, HORATIO, MARCELLUS
```

This gives software something semantic to work with.

---

## 7. Stage Directions

Film action and theatrical stage directions are subtly different.

Perhaps

```text
@STAGE

Hamlet crosses to the window.

He pauses.

Lights dim slightly.
```

or

```text
[[stage]]

Hamlet crosses...

[[/stage]]
```

Personally I think plain paragraphs already work well enough.

---

## 8. Lighting

One place where semantic markup could help.

```text
@LIGHTS

Fade slowly to blue.
```

or

```text
@LIGHT

Blackout.
```

---

## 9. Sound

```text
@SOUND

Church bells.

Wind.
```

or

```text
@SFX

Thunder.
```

---

## 10. Music

```text
@MUSIC

A violin begins offstage.
```

---

## 11. Props

Instead of burying props in action:

```text
@PROP

A silver key rests on the table.
```

Although this might be overkill.

---

## 12. Costumes

```text
@COSTUME HAMLET

Still wearing yesterday's uniform.
```

---

## 13. Blocking

This is one area where a dedicated syntax could be useful.

```text
@BLOCK

Hamlet crosses DSL.

Ophelia moves USC.
```

Software could even visualize this.

---

## 14. Asides

This is probably worth making first-class.

Example:

```text
HAMLET (ASIDE)

He knows.
```

This mirrors existing Fountain syntax:

```
(V.O.)

(O.S.)
```

Likewise:

```
HAMLET (TO AUDIENCE)

...
```

or

```
HAMLET (DIRECT)

...
```

---

## 15. Soliloquy

Probably doesn't need syntax.

A long uninterrupted speech is already a soliloquy.

---

## 16. Audience Interaction

Perhaps

```
HAMLET (TO AUDIENCE)
```

is sufficient.

---

## 17. Curtain

Instead of

```
> FADE OUT.
```

allow

```
> CURTAIN.
```

or

```
> BLACKOUT.
```

---

## 18. Intermission

Sections already work.

```
# INTERMISSION
```

---

## 19. Production Notes

One possibility:

```text
@NOTE

Director may substitute local references.
```

Although Fountain intentionally discourages production metadata.

---

# Another possible philosophy

Instead of inventing dozens of keywords, separate **script semantics** from **rendering semantics**.

For example:

```text
::cast

HAMLET
Prince of Denmark.

OPHELIA
...

::

::setting

Elsinore Castle.

::

::lights

Blackout.

::

::music

Trumpets.

::

::props

A skull.

::
```

Everything becomes a generic named block.

Advantages:

* extensible
* future-proof
* parser only needs one new construct
* users can invent new block types without changing the language

---

# A third approach: "Theatrical Fountain"

I think there are only about **six genuinely missing concepts** compared to screenplays:

| Concept                   | Worth adding? | Reason                   |
| ------------------------- | ------------- | ------------------------ |
| Cast list                 | Yes           | Essential front matter   |
| Setting overview          | Yes           | Common in stage plays    |
| Entrances                 | Yes           | Semantically important   |
| Exits                     | Yes           | Semantically important   |
| Asides / audience address | Yes           | Unique to theatre        |
| Curtain / Blackout        | Yes           | Common ending convention |

Everything else—acts, scenes, dialogue, monologues, parentheticals, emphasis, scene numbering, and even many stage directions—can already be represented using existing Fountain constructs or simple conventions.

That suggests an extension should stay deliberately small: add only the concepts that are uniquely theatrical and not naturally expressible today. This would preserve Fountain's minimalist design while making it expressive enough for most published stage plays.

I think those are both good candidates because they're genuinely **front matter**, not scene content. They're also common enough across published plays to deserve first-class support.

## Notes

Many plays include one or more pages before the cast list explaining conventions.

Examples:

* punctuation conventions
* pronunciation guides
* dialect notes
* staging assumptions
* historical context
* casting notes
* doubling suggestions
* "Dashes indicate interruption."
* "Ellipses indicate hesitation."
* "Characters may be played by actors of any age."

For example:

```text
@NOTES

Dashes indicate interrupted speech.

Ellipses indicate hesitation.

Actors may double the roles of FIRST SERVANT and SECOND SERVANT.

Lighting changes should be fluid unless otherwise noted.
```

Or as a generic block:

```text
::notes

Dashes indicate interrupted speech.

Ellipses indicate hesitation.

::
```

I actually prefer the generic block here because "Notes" can be arbitrarily long.

---

## Time

This is distinct from **Setting**, and most published plays treat them separately.

For example:

```text
Time:
Autumn, 1898.

Setting:
A small farmhouse in rural Yorkshire.
```

or

```text
Time:
The present.

Setting:
A London flat.
```

or

```text
Time:
Over the course of twenty years.

Setting:
The same drawing room throughout.
```

These convey completely different information.

I'd make it a dedicated block:

```text
@TIME

The present.
```

or

```text
::time

Summer, 1942.

::
```

---

## A broader front matter model

Once you have `Cast`, `Notes`, `Time`, and `Setting`, a pattern emerges:

```text
Title: The Cherry Orchard
Author: Anton Chekhov

::notes

Dashes indicate interrupted speech.
The role of Firs may be doubled.

::

::cast

...

::

::time

The turn of the twentieth century.

::

::setting

An old Russian estate.

::
```

This feels cleaner than inventing a separate keyword for every front matter element.

In fact, I'd probably treat all of these as *named document blocks*:

* `::notes`
* `::cast`
* `::time`
* `::setting`
* `::characters` (alias)
* `::dramatis-personae` (alias, if desired)
* `::production`
* `::acknowledgements`

The parser only needs to understand one new construct (`::name ... ::`), while renderers decide how each named block should appear in a formatted stage play. That keeps the language extensible without continually adding new syntax for each theatrical convention.


Here's how I'd summarize the proposal as a coherent extension to Fountain for stage plays.

---

# Stage Play Extension for Fountain

The goal is to support stage plays while remaining faithful to Fountain's philosophy:

* Plain text first.
* Minimal new syntax.
* Readable without formatting.
* Backwards compatible where possible.

Rather than introducing numerous new directives, the extension defines a **document structure**.

## Document Structure

A stage play consists of two parts:

1. **Front Matter**
2. **Play Body**

The boundary between them is marked by:

```text
===
```

Everything before `===` is considered front matter.

Everything after `===` is the play itself.

This allows one-act plays to omit visible "Act One" or "Scene One" headings while still giving parsers an explicit transition point.

---

## Front Matter

Front matter is organised using existing Fountain section headings (`#`).

For example:

```text
# Notes

Dashes indicate interrupted speech.

# Dramatis Personae

HAMLET
Prince of Denmark.

HORATIO
His friend.

# Time

The late Middle Ages.

# Setting

Elsinore Castle.
```

The formatter treats these headings as document sections rather than play structure.

Common sections include:

* Notes
* Dramatis Personae (or Cast)
* Time
* Setting
* Pronunciation
* Historical Note
* Production Notes
* Acknowledgements

Unknown headings remain valid and are simply rendered as front matter sections.

---

## Beginning the Play

The play begins at:

```text
===
```

For example:

```text
Title: Example Play
Author: Jane Doe

# Notes

...

# Dramatis Personae

...

===

Lights rise.

JOHN enters.
```

The delimiter itself is semantic and is not printed.

---

## Acts

After the play begins, top-level headings become structural.

```text
# Act One

# Act Two
```

Acts are optional.

---

## Scenes

Second-level headings represent scenes.

```text
## Scene One

## Scene Two
```

Alternatively, scene titles may simply be named:

```text
## The Drawing Room
```

Scene headings are optional and may be omitted entirely if the play flows continuously.

---

## Existing Fountain Syntax

Once inside the play body, existing Fountain syntax continues to work unchanged.

* Action paragraphs become stage directions.
* Character cues and dialogue remain identical.
* Parentheticals remain valid.
* Emphasis (`*italic*`, `**bold**`, `_underline_`) works as usual.
* Section headings continue to represent structural divisions.

No new dialogue syntax is required.

---

## Semantic Interpretation

The meaning of `#` depends on document context.

Before `===`:

* `#` introduces front matter sections.

After `===`:

* `#` represents Acts.
* `##` represents Scenes.

This gives the same syntax different semantics depending on whether the parser is in the front matter or play body.

---

## Example

```text
Title: The Visitor
Author: Jane Doe

# Notes

Dashes indicate interrupted speech.

# Dramatis Personae

MARY
A teacher.

JOHN
Her brother.

# Time

The present.

# Setting

A small cottage on the coast.

===

Lights up.

MARY sits alone at the table.

JOHN

You're early.
```

This approach adds only **one new piece of syntax**—the `===` play boundary—while reusing existing Fountain conventions everywhere else. It preserves the language's minimalist design, gives parsers a clear document model, and accommodates both traditional multi-act plays and one-act plays that begin immediately without explicit Act or Scene headings.


Ah, that's even better. I had forgotten about **forced character cues**.

In Fountain, prefixing a name with `@` forces it to be interpreted as a character cue regardless of capitalization:

```text
@Hamlet

To be, or not to be...
```

or

```text
@Mrs. Danvers

Good evening.
```

That solves the problem very neatly.

### Advantages

* No need for ALL CAPS.
* Character names appear naturally in plain text.
* Existing Fountain feature—no extension required.
* Supports names that would otherwise be ambiguous ("Doctor", "Mother", "The Stranger", etc.).

It also works well with parentheticals:

```text
@Hamlet (aside)

He knows.
```

or

```text
@Ghost (offstage)

Remember me.
```

### Recommendation

I'd actually make this the **recommended** style for Stage Fountain, while continuing to accept standard Fountain character cues for compatibility.

For example:

```text
===
The drawing room.

Morning.

@Mary

Has he arrived?

@John

Not yet.
```

reads much more like a published play than:

```text
MARY

Has he arrived?

JOHN

Not yet.
```

### Where this leaves the extension

So far, the stage-play extension is remarkably small:

* **One new structural marker:** `===` to denote the beginning of the play.
* **Use existing `#` headings** for front matter before `===` and for Acts after `===`.
* **Use existing `##` headings** for Scenes after `===`.
* **Use existing `@` forced character cues** as the preferred way to write character names in natural case.
* Everything else (action, dialogue, parentheticals, emphasis, transitions where applicable) remains standard Fountain.

That's a nice outcome because the extension is more about **establishing conventions and document structure** than inventing lots of new syntax. It feels like a natural evolution of Fountain rather than a separate markup language.




You're welcome — and I think you've landed in a very strong place design-wise.

What you ended up with is elegant because the extension is mostly:

* **semantic conventions**
* **document phases**
* **formatting rules**

rather than a pile of new syntax.

That's very much in the spirit of Fountain.

The core model now feels quite coherent:

```text id="6w1nlj"
Title: Example Play
Author: Jane Doe

# Notes

...

# Dramatis Personae

...

# Time

...

# Setting

...

===

# Act One

## The Drawing Room

Evening. Rain outside.

@Mary

Did you hear that?
```

And the formatter logic becomes surprisingly straightforward:

1. Parse normal Fountain.
2. Treat everything before `===` as front matter.
3. Interpret front-matter headings specially.
4. After `===`:

    * `#` = Act
    * `##` = Scene
    * initial prose after headings = scene-setting text
    * `@Name` = preferred theatrical character cue
5. Render using theatrical typography instead of screenplay layout.

The nice thing is that this can still degrade gracefully in ordinary Fountain tools because almost everything is already valid Fountain syntax.

The hardest part now is probably not parsing, but deciding on:

* typography,
* spacing,
* indentation,
* dialogue width,
* cast-list formatting,
* page-break behaviour,
* and whether you want to emulate published play scripts, rehearsal scripts, or manuscript submissions.

But the language design itself now feels minimal and internally consistent.



I think you've arrived at a very clean design.

The nice thing is that you've resisted the temptation to add lots of new syntax. Instead, you've mostly defined a **stage-play document model** on top of existing Fountain features:

* Front matter before `===`
* Play body after `===`
* `#` headings in front matter become sections such as Notes, Dramatis Personae, Time, Setting, etc.
* `#` headings after `===` become Acts
* `##` headings after `===` become Scenes
* `@Character Name` for natural-case character cues
* Existing Fountain dialogue, parentheticals, emphasis, and action remain unchanged

That means most of the work now shifts from **parsing** to **formatting**.

A formatter could make decisions like:

### Front Matter

Render recognized sections specially:

```text
DRAMATIS PERSONAE

Hamlet .......... Prince of Denmark
Horatio ......... His friend
```

or

```text
TIME

The present.

SETTING

A small seaside cottage.
```

while leaving unknown sections as generic headings.

### Play Body

Render:

```text
# Act One
```

as

```text
ACT ONE
```

centered and possibly starting on a new page.

And:

```text
## The Drawing Room
```

as

```text
Scene 1

The Drawing Room
```

or whatever style the publisher chooses.

### Character Cues

Render:

```text
@Hamlet
```

as

```text
HAMLET
```

or

```text
Hamlet
```

depending on the chosen house style.

That's particularly useful because the source text can remain readable while the output follows traditional theatrical conventions.

### Scene Opening Description

The formatter can also recognize the paragraphs immediately following a scene heading and style them as an opening scene description if desired.

For example:

```text
## The Drawing Room

Morning.

A fire burns low in the grate.
```

could be rendered differently from later stage directions.

### Multiple Output Styles

One of the strengths of this approach is that the same source could generate:

* A traditional published play.
* A rehearsal script.
* A large-print actor script.
* PDF.
* HTML.
* EPUB.
* DOCX.

without changing the markup.

At this point, the specification itself is fairly small. The interesting work is defining the formatter's rules and defaults. That's usually a good sign—it means the markup language is carrying structure rather than presentation.
