# Fountain Stage Extension (FSE) Specification

Draft 0.2 · Oct 14, 2026 · @Henry

## 1. Introduction

FSE adds machine-readable stage blocking to Fountain scripts by placing structured directives inside Fountain notes (`[[ ]]`) that begin with the marker `FSE`. An FSE script remains a valid Fountain script: tools that do not understand FSE hide the directives as ordinary notes.

### 1.1 Scope

FSE covers three things: the stage (its type and coordinate system), the entities on it (cast, props, marks, entrances), and how those entities move and change state through the script. Lighting, sound and other technical cues are out of scope for this draft.

### 1.2 Design goals

- **Graceful degradation.** Every FSE directive is a legal Fountain note, so existing tools render the script correctly without modification.
- **Unambiguous marking.** The `FSE` marker distinguishes directives from writer notes, so an ordinary note is never mistaken for blocking.
- **Logical blocking over physical geometry.** Blocking should refer to named marks where possible, so a production can be remapped to a new venue by changing mark positions rather than rewriting cues.
- **Trackable state.** A processor can know where every entity is at any point in the script, which enables validation and generated paperwork such as preset sheets and prop tracking.
- **Precise timing.** Movement can be anchored to a specific word of dialogue, matching prompt-book practice.

### 1.3 Conformance

The key words MUST, MUST NOT, SHOULD and MAY are used as described in RFC 2119. A *processor* is any tool that reads FSE directives. A *conforming processor* parses directives as defined in sections 2 to 6 and reports the errors in section 7.

### 1.4 Status

Draft 0.2. The syntax (section 2), state semantics (sections 3 to 6), script position (6.7) and validation (section 7) are settled, and every ambiguity found while planning a conforming processor has been resolved. The questions in Appendix C remain open, and everything remains open to change before 1.0.

## 2. Directive syntax

An FSE note is a Fountain note whose content begins with the marker `FSE`, followed by whitespace and one or more directives. Each directive begins with an uppercase keyword, optionally followed by an id and then zero or more attributes.

```
[[FSE KEYWORD id key=value key=value]]
```

The marker is case-sensitive: `[[fse MOVE ...]]` is an ordinary note.

An FSE note MAY span several lines, as any Fountain note may. Line breaks count as whitespace wherever whitespace is allowed: after `[[`, after the marker, between tokens and around `;`. A line holding only spaces or tabs is whitespace too; this is Fountain's way of keeping a gap inside a note. A line break MUST NOT appear inside a quoted value.

```
[[FSE STRIKE all;
      PRESET throne pos=0,4;
      PRESET claudius pos=0,3 facing=0,-5]]
```

A truly empty line ends a Fountain note, so an FSE note interrupted by one is never closed: `[[` followed by the marker with no `]]` before an empty line or the end of the script is an error (E21).

Reading a directive happens in two layers. **Tokenising** splits the note into keyword-led directives made of tokens (2.6, Appendix B); a note that cannot be split is a *near-miss* and is ignored. **Validation** then checks each token against the rules for its directive and key: the id rule (2.2), the known keys (Appendix A) and the value types (2.4). A directive that tokenises but fails validation is an error (section 7), not a near-miss.

### 2.1 Keywords

Keywords are uppercase and drawn from a fixed set: `STAGE`, `ENTITY`, `ENTER`, `EXIT`, `MOVE`, `VIA`, `ARRIVE`, `SET`, `STRIKE` and `PRESET`. Within an FSE note, an unknown keyword (including a lowercase one) makes the note a near-miss (see 2.6).

### 2.2 Ids

An id names an entity. Ids MUST match `[a-z0-9][a-z0-9_-]*`: lowercase letters, digits, hyphen and underscore, starting with a letter or digit. An id MUST NOT also be a valid number (2.4), so `90` and `1.5` are not ids while `2b` and `vom-1` are. Ids are unique across the whole script regardless of entity type.

A subject or reference that does not match this rule, such as `Hamlet` or `90`, is a bad value (E17), not an unknown id.

The reserved ids `crew` and `all` (Appendix A) count as already declared: an `ENTITY` declaring either is a duplicate id (E03), and using either outside its permitted place is a wrong type (E04).

### 2.3 Attributes

An attribute is `key=value` with no spaces around `=`. The key is everything before the first `=` in the token, and the value everything after it, so `label=a=b` has the value `a=b`. Keys are lowercase; a key that is not defined for the directive, including a wrongly cased one such as `Pos`, is an unknown attribute (E16).

A value is either *bare* or *quoted*:

- A **bare** value is one or more characters other than whitespace, `;`, `"`, `[` and `]`.
- A **quoted** value is wrapped in double quotes and may contain spaces and `;`. Inside it, `\"` is a literal double quote and `\\` a literal backslash; any other backslash is literal, so `"a\nb"` is the four characters `a`, `\`, `n`, `b`. A quote left unclosed makes the note a near-miss.

`[` and `]` MUST NOT appear in any value, quoted or bare, since they delimit Fountain notes.

`/*` and `*/` MUST NOT appear anywhere in an FSE note. Fountain removes boneyard (`/* */`) from the whole script before it reads notes, so a `/*` inside a note opens a boneyard that swallows the rest of the note and everything after it up to the next `*/`. A processor sees only what remains, which is usually an unclosed note (E21).

```
[[FSE ENTITY skull type=prop label="Yorick's skull"]]
[[FSE ENTITY lantern type=prop label=Lantern]]
```

An attribute MUST NOT appear twice in the same directive (E18).

### 2.4 Values

Bare and quoted are the only forms the tokeniser knows. Each key then expects one of the types below; a value of the wrong type for its key is a bad value (E17).

- **Number:** an optional `-`, then digits with an optional fractional part, or a fractional part alone: `3`, `-2.5`, `0.5`, `.5`. A leading `+`, an exponent (`1e3`), a trailing dot (`5.`) and separators are not numbers. Dimensions (`width`, `depth`, `radius`) MUST be greater than zero.
- **Id:** a reference to a declared entity, e.g. `with=hamlet`.
- **Coordinate:** two numbers separated by a comma, no spaces, e.g. `pos=-2.5,3`. Coordinates may be of any sign; one outside the stage is a warning (W03), not an error.
- **Location:** either a coordinate or the id of a `mark` or `entrance` entity. Wherever a location is accepted, `pos=window` and `pos=-5,0` are interchangeable.
- **Direction:** the value of `facing`. A location, or a bearing in degrees given as a number (see 4.2).
- **Text:** any bare or quoted value, used for labels and cues. Text containing spaces must be quoted.

### 2.5 Compound directives

Several directives MAY share one FSE note, separated by `;`, with optional whitespace on either side. The `FSE` marker appears once, at the start of the note, and MUST NOT be repeated before later directives. Directives in one note take effect simultaneously (see 6.3).

```
[[FSE MOVE hamlet pos=window; MOVE horatio pos=0,0]]
```

A single trailing `;` at the end of the note is allowed and ignored. An empty directive between two separators (`;;`) makes the note a near-miss. A `;` straight after the marker (`[[FSE ; MOVE ...]]`) is an error (E19).

### 2.6 Strict parsing

A note is an FSE note only if its content, after any leading whitespace (including line breaks), begins with the marker `FSE` followed by whitespace. A processor MUST NOT interpret any other note, even one that begins with an FSE keyword, so a writer's note such as `[[MOVE this scene earlier?]]` is always an ordinary note.

If a note carries the marker but cannot be tokenised, it is a *near-miss*: the whole note MUST be treated as an ordinary Fountain note and no part of it takes effect. A processor SHOULD emit a warning (W01) for near-misses, since the marker shows the author intended a directive. A note is a near-miss when:

- a directive does not start with a known keyword;
- a quoted value is not closed, or contains a line break;
- a token after the subject has no `=`, or has an empty key or an empty value (`=1,2`, `pos=`);
- a value contains `[` or `]`;
- two separators enclose an empty directive (`;;`).

Only the first token after the keyword may lack `=`; it is the subject. Everything else about a directive, such as wrongly cased keys, malformed ids or values of the wrong type, is checked in validation and reported as an error.

## 3. Stage declaration

An *FSE script* is one with at least one FSE note that tokenises (2.6). A script whose only FSE notes are near-misses is not an FSE script and needs no `STAGE`; an unclosed note (E21) is reported in any script.

Every FSE script MUST contain exactly one `STAGE` directive, placed in the declaration block (see 4.4) before any other FSE directive; a `STAGE` after another FSE directive is misplaced (E12). It fixes the stage type, its dimensions and the frame that all coordinates are measured in.

```
[[FSE STAGE type=proscenium width=10 depth=8 units=m]]
[[FSE STAGE type=round radius=6 units=m front=vom-a]]
```

### 3.1 Stage types

| Type | Required attributes | Notes |
| --- | --- | --- |
| `proscenium` | `width`, `depth` | Audience on one side. |
| `traverse` | `width`, `depth` | Audience on two opposite sides, at −y and +y; `width` runs along the playing axis (x). |
| `round` | `radius` or `width` + `depth` | Audience on all sides. A radius declares a circular stage; width and depth declare a rectangular one. |
| `flexible` | `width`, `depth` | Black box or promenade staging with no fixed audience relationship. |

Any other `type`, including `thrust`, is a bad value (E17). Thrust staging is an open question (Appendix C).

### 3.2 Units

`units` is one of `m`, `cm`, `ft` or `in`. All coordinates and dimensions in the script use the declared unit. If omitted, the default is `m`.

### 3.3 Coordinate frame

The origin `0,0` is the centre of the playing area: the midpoint of the declared width and depth, or the centre of a circular round. Every stage type uses the same frame, a ground plan drawn as seen from the default audience position, with that audience at the bottom of the page (−y):

- **+x** runs toward stage left (the audience's right); −x toward stage right.
- **+y** runs upstage, away from the default audience.

Bearings (4.2) follow the same frame: 0 is +y and angles increase clockwise seen from above, so 90 is stage left.

A coordinate is out of bounds (W03) when it lies outside the width × depth rectangle, or for a circular round, further than `radius` from the origin. Entrance positions are not checked: wings, vomitories and aisles sit on or beyond the edge of the playing area.

### 3.4 Front

`front` is OPTIONAL for every stage type. Without it the default audience position is simply at −y. When given, it is the id of an `entrance` or `mark` entity that marks the default audience position for production paperwork, conventionally a vomitory or the control booth. That entity MUST lie on the negative y-axis (a position `0,y` with y less than 0); any other position is a bad value (E17).

`front` MAY reference an entity declared later in the declaration block.

## 4. Entities

Every named thing in the blocking is an entity, declared once with `ENTITY` and referred to by id thereafter.

```
[[FSE ENTITY hamlet type=cast]]
[[FSE ENTITY skull type=prop on=table label="Yorick's skull"]]
```

### 4.1 Entity types

| Type | Meaning | Location attributes allowed |
| --- | --- | --- |
| `cast` | A performer or character. | `pos`, `facing`, or none (offstage) |
| `prop` | Any object that can be placed, carried or struck, including furniture. | `pos`, `on`, `with`, or none (offstage) |
| `mark` | A named fixed position on stage. | `pos` (required) |
| `entrance` | A named way on or off stage: a wing, door, vom or aisle. | `pos` (required) |

Marks and entrances are fixed: they MUST NOT be the subject of a movement directive.

### 4.2 Location attributes

- `pos=<location>` places the entity on the stage floor at a coordinate or mark.
- `on=<prop id>` places a prop on another prop. It moves with its parent.
- `with=<cast id>` means the prop is carried by that cast member. It moves with them.
- `facing=<direction>` gives the direction a cast member faces: either a location they face toward (a coordinate or a mark or entrance id), or a bearing in degrees, where 0 is +y and angles increase clockwise. Any number is accepted and taken modulo 360, so `facing=-90` equals `facing=270`. A processor MUST accept all three forms. Because an id is never a number (2.2), the form is always unambiguous: a number is a bearing, `x,y` is a coordinate, anything else is an id. Props have no facing: `facing` on any directive whose subject is a prop is an unknown attribute (E16).

An entity has at most one of `pos`, `on` and `with` at any time. A prop `on` or `with` something has its carrier's position at every point in the script, including while the carrier is in transit (5.7).

#### 4.2.1 Onstage and offstage

Whether an entity is onstage is derived from its location:

- A cast member is **onstage** when it has a `pos`, and **offstage** otherwise.
- A prop is **onstage** when its chain of `on` and `with` links ends at something onstage: a prop with a `pos`, or an onstage cast member. A prop with no location, or whose chain ends at something offstage, is **offstage**.

A prop MAY be attached to an offstage entity: preset `on` a trolley in the wings, or `with` an actor waiting to enter. The attachment is kept, and the prop comes on when its carrier does.

**Going offstage** is the transition of an onstage entity to offstage, by `EXIT`, `STRIKE` or `PRESET`. When an entity goes offstage, every prop `on` or `with` it, directly or through a chain, goes offstage too and **loses its attachment**: nothing that was arranged on stage survives into the wings, so a prop brought back is placed afresh. Going offstage also clears a cast member's `facing`.

A cast member's `facing` is unset until a directive gives it. It MAY be set while they are offstage (`PRESET` or `SET` without `pos`), for instance to have them enter backwards, and is kept until they enter. Unset is a valid state; renderers decide how to draw it.

### 4.3 Cast and dialogue cues

A cast id matches a Fountain character cue case-insensitively, so `hamlet` matches `HAMLET`. Where the cue cannot be written as an id, `cue=` gives it explicitly:

```
[[FSE ENTITY first-gravedigger type=cast cue="FIRST GRAVEDIGGER"]]
```

Character extensions such as `(V.O.)` or `(CONT'D)` are ignored when matching.

### 4.4 The declaration block

The `STAGE` directive and all `ENTITY` directives MUST appear in a declaration block: after the Fountain title page and before the first scene heading. Location attributes given here are the entity's position at the top of the play. References inside the block MAY point forward to entities declared later in the same block.

A bare `ENTITY` outside the declaration block is misplaced (E12). Entities that appear mid-play are declared up front without a location (offstage) and brought on with `ENTER` or `SET`.

## 5. Movement and state

Eight directives change where entities are. Each one's subject types are fixed (Appendix A); naming an entity of another type is a wrong type (E04). `MOVE` is travel across the stage, and with `VIA` and `ARRIVE` it can span several lines; `SET` is an instantaneous change of state; `ENTER`, `EXIT`, `STRIKE` and `PRESET` handle the boundary between onstage and off.

### 5.1 ENTER

```
[[FSE ENTER hamlet from=vom-a pos=0,3 facing=window]]
```

Brings an offstage cast member or prop on. `from` (an `entrance` id) is REQUIRED for cast. `pos` gives where they arrive; if omitted, they stop at the entrance's position. A cast member's `facing` is the one given here, or else the one set while offstage, or else unset.

Props an entering cast member carries come on with them: either attached while offstage (`ENTITY`, `PRESET` or `SET ... with=`), or given with `SET ... with=` in the same note.

For a prop, `from` and `pos` are each OPTIONAL but at least one is REQUIRED (E08); with only `from`, the prop lands at the entrance's position. `ENTER` places a prop on the floor only: it takes no `on` or `with`, so a prop that arrives on or with something is either `SET` there or attached offstage and brought on with its carrier. `ENTER` on a prop that is attached to something offstage detaches it and places it; the carrier stays offstage.

### 5.2 EXIT

```
[[FSE EXIT horatio via=vom-b]]
[[FSE EXIT all]]
```

Takes an onstage cast member off. `via` (an `entrance` id) is REQUIRED. Everything they carry goes off too and is detached (4.2.1). Props leave by `STRIKE`, or by being carried off; `EXIT` on a prop is a wrong type (E04).

The reserved subject `all` takes every onstage cast member off at once. `via` is OPTIONAL: if given, everyone leaves that way; if not, the route is unrecorded. Each cast member leaves as for a single `EXIT`, closing any open move and taking carried props with them. Props on the floor stay where they are, which distinguishes it from `STRIKE all`. `EXIT all` on an empty stage is valid and does nothing.

### 5.3 MOVE

```
[[FSE MOVE hamlet pos=window facing=table]]
```

Moves an onstage cast member, or a prop on the floor, to a new location. `pos` is REQUIRED. `facing` is optional and, if omitted, is unchanged. A `MOVE` is a straight cross; a cross that does not run straight is written as an open move with a `VIA` for each turning point (see 5.7).

A prop `MOVE` applies only to a prop on the floor (with a `pos`); `MOVE` on a prop that is `on` or `with` something is an error (E20). To move it across the floor, first `SET` it down, then `MOVE` it.

An optional `by=<cast id>` on a prop `MOVE` records who moves it. `by` on a cast `MOVE` is an unknown attribute (E16).

### 5.4 SET

```
[[FSE SET skull with=hamlet]]
[[FSE SET skull on=table by=hamlet]]
[[FSE SET lantern pos=-1,0 by=horatio]]
```

Changes a prop's location instantly: a pick-up, put-down or handoff. Exactly one of `pos`, `on` or `with` is REQUIRED. `by` is OPTIONAL and names the cast member performing the action; when present, it is checked for reach (W04).

The prop MAY be offstage before the `SET`, and the target of `on` or `with` MAY be offstage: the prop is then attached offstage and comes on with its carrier (4.2.1). A `SET` on a prop in transit closes its open move implicitly: the destination is discarded and the `SET` applies.

`SET` also changes `facing` on a cast member without travel: `[[FSE SET hamlet facing=vom-a]]`. This is allowed while they are offstage or in transit.

### 5.5 STRIKE

```
[[FSE STRIKE table by=crew]]
```

Removes an onstage prop from the stage, along with anything `on` it; all of them go offstage and are detached (4.2.1). A prop that is `on` or `with` something is detached as it is struck. A prop in transit has its open move discarded. `STRIKE` on an offstage prop is an error (E05), and on a cast member a wrong type (E04): cast leave by `EXIT`.

`by` is OPTIONAL and may name a cast member or the reserved id `crew`. A struck prop is offstage and may return with `ENTER` or `SET`.

```
[[FSE STRIKE all]]
```

The reserved subject `all` clears the stage: every cast member and prop goes offstage, all attachments are dropped, and any open moves are discarded. Marks and entrances are unaffected. `STRIKE all` MAY appear anywhere, and is also permitted at the top of a scene before its `PRESET` directives (see 5.6 and 6.4).

### 5.6 PRESET

```
[[FSE PRESET skull on=table; PRESET hamlet pos=0,3]]
```

Asserts an entity's location at the top of a scene, after a scene boundary. `PRESET` uses the same location attributes as `ENTITY`. An entity listed with no `pos`, `on` or `with` is asserted to be offstage; a cast member may still be given a `facing` there (4.2.1). A `PRESET` that takes an onstage entity off is going offstage, with the usual detachment.

`PRESET` MUST appear at the top of a scene: after the scene boundary and before any other content. Blank lines, page breaks, ordinary (non-FSE) notes, synopses and boneyard are not content; dialogue, action, transitions, centred text and any FSE note holding another directive are. A character cue is content, so any FSE note inside a dialogue block comes after content. A misplaced FSE note (E12) still counts as content; a near-miss (W01) is an ordinary note and does not. A note holding a `PRESET` MUST contain only `PRESET` and `STRIKE all` directives. Either violation is misplaced (E12).

A `PRESET` that differs from the carried-over state is not an error: it describes a scene change (see 6.4).

### 5.7 Open moves: VIA and ARRIVE

A move that spans several lines is written as an *open move*: a `MOVE` with `until=arrive`, closed later by `ARRIVE`. Both ends are cued by their position in the text, like any other directive.

```
[[FSE MOVE hamlet pos=-4,0 until=arrive]]
...
[[FSE VIA hamlet pos=0,1]]
...
[[FSE ARRIVE hamlet]]
```

`until=arrive` is valid on `MOVE` for cast members and for props on the floor. From the `MOVE` until its `ARRIVE`, the entity is *in transit*. The pair is matched by entity id: an entity has at most one open move at a time, so no label is needed.

`ARRIVE` takes a subject and optionally `facing`. From that cue on, the entity is at the `MOVE`'s `pos`.

`VIA` takes a subject and a required `pos`, and states where an in-transit entity is at that cue. It splits the cross into segments without ending it. A change of course is written as a `VIA`, never as a second `MOVE`. A planned route with several turning points is a series of `VIA` notes:

```
[[FSE MOVE hamlet pos=1,2 until=arrive]]
[[FSE VIA hamlet pos=-2,2]]
[[FSE ARRIVE hamlet]]
```

**Position in transit.** Where a processor needs a position for an entity in transit (plan view, reach checks), it interpolates linearly along each segment in proportion to script position (6.7) between the segment's start and end cues. Because cues are anchored to text rather than clock time, arrivals stay on their words whatever the pacing. A later version may add a `dur=` attribute for clock-timed moves.

**Segments with no script length.** A segment whose start and end cues have the same script position, such as a `MOVE`, `VIA` and `ARRIVE` in consecutive notes, is valid. It has no script length, but it is not instantaneous: stage time may pass between adjacent notes, and the script does not record how much. Each note is still its own step, so the entity is at each `VIA` point at that `VIA`'s cue and the route is never skipped. There is nothing to interpolate inside such a segment.

**Props and actions in transit.** Anything `with` an entity in transit travels with it. A `SET` with `by=` naming an entity in transit is allowed; the reach check (W04) uses the interpolated position.

**Exits and scene ends.** `EXIT` on an entity in transit closes the open move implicitly: the destination is discarded and the entity leaves by the named entrance. `SET` and `STRIKE` on a prop in transit, and `STRIKE all`, likewise discard the move; a later `ARRIVE` is then E14. Every open move MUST be closed before the next scene boundary, since a scene change starts from a settled stage.

**Concurrent moves.** Any number of entities may be in transit at once. Moves that start or end in the same note do so together; moves in separate notes are staggered.

```
[[FSE MOVE hamlet pos=-4,0 until=arrive; MOVE ophelia pos=2,3 until=arrive]]

HAMLET
Ha, ha! Are you honest?

OPHELIA
My lord?

HAMLET
Are you fair?

[[FSE ARRIVE ophelia]]

OPHELIA
What means your lordship?

HAMLET
That if you be honest and fair, your honesty should
admit no discourse to your beauty.

[[FSE ARRIVE hamlet]]
```

Both crosses start before Hamlet's first line. Ophelia arrives in the gap after "Are you fair?", so her cross spans three lines; Hamlet arrives after his final speech. Written inline as `Are you fair? [[FSE ARRIVE ophelia]]`, her arrival would land on "fair" instead (see 6.2).

**Moving together.** Two cast members walking side by side are two open moves started in one note, as above. A `group` entity for formation movement remains an open question (Appendix C).

## 6. Timing and scope

A directive takes effect at the point in the script where its note appears. Its position in the text is its cue.

### 6.1 Standalone notes

A *standalone note* is a paragraph of its own: an empty line before it, an empty line after it, and nothing but notes in between. It takes effect between the elements around it: after the preceding action or dialogue finishes, before the next begins. Several note-only lines MAY be stacked in one paragraph; they are separate notes, applied in order (6.3).

The empty lines are required by Fountain, not added by FSE. Fountain classifies a paragraph by its lines, and a note-only line is still a line: a Character cue needs an empty line directly above it, so a note glued above a cue turns the whole speech into action.

```
[[FSE ENTER hamlet from=vom-a pos=0,3]]
HAMLET
Alas, poor Yorick!
```

A note-only line that shares a paragraph with lines that are not note-only is a *glued note* (W09). It still takes effect where it sits, at the start, middle or end of that paragraph, and Fountain decides what the paragraph is. A processor MUST NOT reclassify the paragraph to suit the note.

### 6.2 Inline notes in dialogue

A note inside a dialogue line takes effect at that word, matching prompt-book practice of marking moves against specific words.

```
HAMLET
Alas, poor Yorick! [[FSE MOVE pos=1,2]] I knew him, Horatio.
```

Inside dialogue, the subject id MAY be omitted and defaults to the speaking character. This is unambiguous because the first token after the keyword then contains `=`. An explicit id is still allowed and is needed to move someone other than the speaker.

Inline notes MAY also appear inside action lines, parentheticals and lyrics, with the same meaning. The implied subject applies only within dialogue and parentheticals. Anywhere else, a directive that takes a subject but has none is a missing attribute (E08).

**Blank lines are significant.** To cue on the last word of a speech, write the note inline at the end of the last line. A note on its own line beneath the speech is a glued note (W09): it still belongs to the dialogue block and cues at the end of the speech, but Fountain tools render it as an empty dialogue line or end the speech there.

```
HAMLET
Are you fair? [[FSE ARRIVE ophelia]]
```

The inline and standalone placements usually cue nearly the same moment, but the difference can matter: an inline note cues on the last word rather than in the gap after the speech, and an id-less directive becomes a directive on the speaker.

### 6.3 Sequence and simultaneity

Directives in one note, separated by `;`, are simultaneous. Separate notes are sequential, in text order, even when adjacent. A processor MUST resolve each directive against the state left by the previous note, so this is valid:

```
[[FSE ENTER hamlet from=vom-a pos=0,3]]
[[FSE SET skull with=hamlet]]
```

Within one note, all directives are checked against the state before the note, then applied together. Two directives in one note MUST NOT affect the same entity (E10). A directive affects its subject and, when it moves its subject or takes it offstage, every prop carried by the subject (`on` or `with` it, directly or through a chain) before the note. So `[[FSE EXIT hamlet via=vom-c; SET skull pos=grave]]`, with the skull `with` Hamlet, is E10 and must be split into two notes, while `[[FSE ENTER horatio from=vom-b; SET lantern with=horatio]]` is valid because the lantern is not carried by Horatio before the note.

### 6.4 Scene boundaries

State carries across scene boundaries (a scene heading, forced or not, or a section heading of any depth) unchanged, since that is what physically happens on stage unless something is moved. A `PRESET` at the top of a scene overrides the carried state for the entities it names. A mid-scene reset is written by starting a new scene, for instance with a section heading.

The difference between the carried state and the state after the top-of-scene `PRESET` and `STRIKE all` directives is the **scene change**: the props that must be set, struck or moved, and the cast who must reposition, in the transition. A processor SHOULD be able to report it per scene, which gives the crew's shift list directly.

To reset the stage instead of carrying state over, open the scene with `[[FSE STRIKE all]]` followed by `PRESET`s for what the scene needs. This suits productions with full blackout resets between scenes.

```
.ACT V, SCENE II - A HALL IN THE CASTLE

[[FSE STRIKE all]]
[[FSE PRESET throne pos=0,4; PRESET claudius pos=0,3]]
```

### 6.5 Fountain sections and boneyard

Directives inside Fountain boneyard (`/* */`) are ignored. Fountain sections (`#`) are scene boundaries (6.4) but do not change state themselves; synopses (`=`) have no effect on state.

### 6.6 Where FSE notes may appear

An FSE note MAY appear only as a standalone note (6.1), or inline in action, dialogue, a parenthetical or lyrics (6.2). An FSE note anywhere else is misplaced (E12): in the title page, a character cue, a scene heading, a section heading, a synopsis, a transition, centred text or a page break. These elements have no defined cue, and Fountain tools disagree on how a note inside them is classified.

### 6.7 Script position

A cue's *script position* is the number of words performed before it, counted from the start of the script. It measures how far through the text a cue is, not clock time, and it is what interpolation in transit (5.7) runs on.

- **Only performed text counts:** dialogue, parentheticals, lyrics and action. Character cues, scene and section headings, synopses, transitions, centred text, page breaks and notes count zero.
- **A word** is a whitespace-separated token of the element's text, with notes and emphasis markup removed. Punctuation-only tokens such as `—` count.
- **Dual dialogue** counts in script order: the left speech, then the right.
- A standalone note's position is the count of everything before it. An inline note's position includes the words before it on its line, so a note at the end of a line falls *on* the last word (6.2). A note inside a word falls on that word: `fa[[FSE ARRIVE ophelia]]ir` cues as `fair [[FSE ARRIVE ophelia]]`.

## 7. Validation

A conforming processor MUST report the errors below and SHOULD report the warnings. Each report SHOULD give the line number and the directive that caused it. A processor MAY stop at the first error, since later reports may be consequences of it.

### 7.1 Errors

| Code | Condition |
| --- | --- |
| `E01 no-stage` | No `STAGE` directive, or more than one. |
| `E02 unknown-id` | A directive refers to an id that is not declared. |
| `E03 duplicate-id` | An id is declared more than once. |
| `E04 wrong-type` | A subject or attribute refers to an entity of the wrong type, e.g. `with=table`, `from=hamlet`, `STRIKE hamlet` or `EXIT skull`. |
| `E05 not-onstage` | `MOVE`, `EXIT` or `STRIKE` on an entity that is offstage (4.2.1). |
| `E06 already-onstage` | `ENTER` on an entity that is already onstage. |
| `E07 fixed-entity` | A movement directive names a `mark` or `entrance`. |
| `E08 missing-attribute` | A required subject or attribute is absent, e.g. a cast `ENTER` without `from`, a prop `ENTER` with neither `from` nor `pos`, or a directive with no subject outside dialogue and parentheticals (see 6.2). |
| `E09 conflicting-location` | More than one of `pos`, `on`, `with` in one directive. |
| `E10 same-entity` | Two directives in one note affect the same entity, including a prop carried by another directive's subject (see 6.3). |
| `E11 cycle` | Props attached in a loop, e.g. a box `on` a lid that is `on` the box. |
| `E12 misplaced` | `ENTITY` or `STAGE` outside the declaration block, `STAGE` after another FSE directive, `PRESET` after other scene content, `PRESET` in a note with a directive other than `PRESET` or `STRIKE all` (see 5.6), or an FSE note in an element that cannot hold one, such as the title page, a character cue, a scene heading or a page break (see 6.6). |
| `E13 already-in-transit` | `MOVE` on an entity that already has an open move. |
| `E14 not-in-transit` | `VIA` or `ARRIVE` on an entity with no open move. |
| `E15 unclosed-move` | An open move is still open at the next scene boundary or the end of the script. |
| `E16 unknown-attribute` | A key not defined for the directive and its subject type, including a wrongly cased one, e.g. `MOVE hamlet Pos=1,2`, `facing` on a prop, or `by` on a cast `MOVE` (see 2.3). |
| `E17 bad-value` | A value of the wrong type for its key, a malformed id, a dimension that is not greater than zero, an unknown stage `type`, or a `front` entity not on the negative y-axis, e.g. `width=window`, `MOVE Hamlet pos=1,2` or `type=thrust` (see 2.2, 2.4, 3). |
| `E18 duplicate-attribute` | The same key appears twice in one directive. |
| `E19 leading-separator` | A `;` straight after the `FSE` marker, e.g. `[[FSE ; MOVE hamlet pos=1,2]]` (see 2.5). |
| `E20 attached` | `MOVE` on a prop that is `on` or `with` something (see 5.3). |
| `E21 unclosed-note` | `[[` followed by the `FSE` marker (after any leading whitespace) with no `]]` before an empty line or the end of the script. Fountain does not treat it as a note, so its text would print in the script. Use a line with two spaces to keep a gap inside a note (see 2). |

### 7.2 Warnings

| Code | Condition |
| --- | --- |
| `W01 near-miss` | A note begins with the `FSE` marker but cannot be tokenised into directives (see 2.6). |
| `W02 speaker-offstage` | A cast member has dialogue while offstage. Voices off are legitimate, so this is a warning. |
| `W03 out-of-bounds` | A coordinate falls outside the declared stage dimensions (see 3.3). Entrance positions are not checked. |
| `W04 reach` | `SET`, `MOVE` or `STRIKE` with `by=` where that cast member is offstage, or further than 1.5 m from the prop, converted to the declared unit (150 cm, about 4.92 ft or 59.06 in). The cast member's point is their position at the cue, interpolated if in transit (5.7). The prop's point is where it is before the note; a `SET` is also checked against its target (the `pos`, or the point of the `on` or `with` entity). An offstage prop or target is not checked for distance, nor is `by=crew`. |
| `W06 unused` | A cast member or prop is declared but never appears onstage. Marks and entrances are not checked. |
| `W07 unmatched-cue` | A dialogue cue matches no `cast` entity. |
| `W09 glued-note` | A line holding only an FSE note shares a paragraph with a line that is not note-only, e.g. a note directly above a character cue or beneath a speech (see 6.1, 6.2). It still takes effect where it sits, but Fountain tools render the paragraph differently from what the author likely meant. |

W05 (shared mark) and W08 (collision) were withdrawn in 0.2: keeping performers apart, or deliberately together, is a staging matter for the company, not a fault in the blocking.

## 8. Rendering and compatibility

FSE changes nothing about how a Fountain script is parsed. Tools without FSE support treat every directive as a note, so the script renders as normal with blocking hidden (or shown as notes, if the tool displays notes).

Some Fountain tools apply emphasis (`*italic*`, `_underline_`) before they remove notes, so a `*` or `_` inside an FSE note, such as an id like `grave_digger`, can pair with one elsewhere on the line and break emphasis in those tools. FSE does not forbid these characters; authors who target such tools may prefer hyphens in ids.

### 8.1 Output modes

An FSE-aware renderer SHOULD offer at least these modes:

- **Script.** Directives are hidden. Suitable for the actor's script and for submission.
- **Prompt book.** Directives are rendered in the margin beside the line or word they are anchored to, in a compact notation (e.g. `HAM → WINDOW`).
- **Generated paperwork.** Per-scene preset sheets, scene-change shift lists (see 6.4), and a prop tracking table showing each prop's location through the play.

A renderer MAY also produce a plan view: a ground plan of the declared stage showing entity positions at any point in the script.

### 8.2 Ordinary notes

Notes that are not FSE (see 2.6) MUST be passed through untouched and rendered exactly as a standard Fountain tool would render them.

### 8.3 Editing

An FSE-aware editor SHOULD NOT rewrite directive formatting the author did not touch. It MAY offer autocomplete for ids and keywords, and inline display of validation reports.

## 9. Complete example

The graveyard scene from *Hamlet*, staged in the round, followed by the top of the next scene. Scene headings use Fountain's forced form (a leading `.`), which suits act and scene numbering.

```
Title: Hamlet (FSE excerpt)
Author: William Shakespeare

[[FSE STAGE type=round radius=6 units=m front=vom-a]]
[[FSE ENTITY vom-a type=entrance pos=0,-6]]
[[FSE ENTITY vom-b type=entrance pos=5.2,3]]
[[FSE ENTITY vom-c type=entrance pos=-5.2,3]]
[[FSE ENTITY grave type=mark pos=0,0]]
[[FSE ENTITY graveside type=mark pos=1.2,-0.5]]
[[FSE ENTITY hamlet type=cast]]
[[FSE ENTITY horatio type=cast]]
[[FSE ENTITY first-gravedigger type=cast cue="FIRST GRAVEDIGGER"]]
[[FSE ENTITY spade type=prop with=first-gravedigger]]
[[FSE ENTITY skull type=prop pos=grave]]
[[FSE ENTITY lantern type=prop]]

.ACT V, SCENE I - A CHURCHYARD

[[FSE PRESET first-gravedigger pos=grave facing=vom-a]]

The FIRST GRAVEDIGGER digs, singing.

[[FSE ENTER hamlet from=vom-b pos=3,1; ENTER horatio from=vom-b pos=3.5,2; SET lantern with=horatio]]

HAMLET
Has this fellow no feeling of his business, that he sings at grave-making?

The gravedigger throws up a skull.

[[FSE SET skull pos=graveside by=first-gravedigger]]

HAMLET
[[FSE MOVE pos=graveside facing=grave]] Let me see. [[FSE SET skull with=hamlet]] Alas, poor Yorick! I knew him, Horatio.

[[FSE SET skull pos=grave by=hamlet]]
[[FSE EXIT hamlet via=vom-c; EXIT horatio via=vom-c]]

.ACT V, SCENE II - A HALL IN THE CASTLE

[[FSE PRESET first-gravedigger; PRESET skull]]

[[FSE ENTER hamlet from=vom-a pos=0,-2; ENTER horatio from=vom-a pos=1,-3]]
```

From this a processor can derive, without further input:

- **Scene change I→II:** the first gravedigger exits (the spade goes off with him and is no longer his) and the skull is struck from the grave. That is the crew's shift list.
- **Attachment:** the spade is declared `with` the gravedigger while he is offstage, so it comes on with him when he is preset at the grave.
- **Prop tracking:** the lantern enters with Horatio in V.i and goes off when he exits, losing its attachment. It does not return in V.ii unless set with him again, which may be a continuity note for the director.
- **Timing:** Hamlet starts his cross to the graveside on "Let me see" and takes the skull on "Alas".

## Appendix A. Directive reference

| Directive | Subject | Required | Optional |
| --- | --- | --- | --- |
| `STAGE` | none | `type` + dimensions (3.1) | `units`, `front` |
| `ENTITY` | id | `type`; `pos` for mark and entrance | `pos`, `on`, `with` (prop), `facing` (cast), `cue` (cast), `label` |
| `ENTER` | cast or prop | `from` (cast); `from` or `pos` (prop) | `pos`, `facing` (cast) |
| `EXIT` | cast, or all | `via` (not for `all`) | `via` (for `all`) |
| `MOVE` | cast, or prop on the floor | `pos` | `facing` (cast), `by` (prop), `until=arrive` |
| `VIA` | entity in transit | `pos` | none |
| `ARRIVE` | entity in transit | none | `facing` |
| `SET` | prop, or cast for `facing` | one of `pos`, `on`, `with`, or `facing` | `by` |
| `STRIKE` | onstage prop, or all | none | `by` (not for `all`) |
| `PRESET` | cast or prop | none (no location means offstage) | `pos`, `on`, `with` (prop), `facing` (cast) |

Every directive appears inside a note that begins with the `FSE` marker (see 2).

Two ids are reserved and need no declaration: `crew`, which MAY appear only as the value of `by`, and `all`, which MAY appear only as the subject of `STRIKE` or `EXIT`.

## Appendix B. Grammar sketch

An informal EBNF for the tokeniser: the content between `[[` and `]]`. A note that does not match is a near-miss (W01). Matching notes are then validated (2.2 to 2.4): keys against Appendix A, ids against 2.2, values against the type each key expects.

```
note       = "FSE" ws directive { ws? ";" ws? directive } [ ws? ";" ] ws? ;
directive  = keyword [ ws subject ] { ws attribute } ;
keyword    = "STAGE" | "ENTITY" | "ENTER" | "EXIT"
           | "MOVE" | "VIA" | "ARRIVE"
           | "SET" | "STRIKE" | "PRESET" ;
subject    = value ;                      (* contains no "=" *)
attribute  = key "=" value ;
key        = keychar { keychar } ;        (* bchar except "=" *)
value      = bare | quoted ;
bare       = bchar { bchar } ;
bchar      = ? any char except whitespace, ";", '"', "[", "]" ? ;
quoted     = '"' { qchar | '\"' | '\\' } '"' ;
qchar      = ? any char except '"', "[", "]", newline ? ;
ws         = wschar { wschar } ;
wschar     = " " | "\t" | newline ;         (* never two newlines in a row: Fountain ends the note there *)
```

A backslash in a quoted value not followed by `"` or `\` is literal. One failure is an error rather than a near-miss: a `;` straight after the marker (E19). An FSE note with no closing `]]` is not matched by this grammar at all; it is E21. Leading and trailing whitespace inside the note, including line breaks, is ignored. The subject is omitted for `STAGE`, and MAY be omitted inside dialogue (6.2). The value types checked in validation are:

```
number     = [ "-" ] ( digits [ "." digits ] | "." digits ) ;
coordinate = number "," number ;
id         = idstart { idchar } ;             (* and not a number *)
idstart    = "a".."z" | "0".."9" ;
idchar     = idstart | "-" | "_" ;
location   = coordinate | id ;
direction  = location | number ;              (* number = bearing *)
```

## Appendix C. Open questions

- **Polar positions.** Should the round get sugar such as `pos=9/mid` (clock position and ring) alongside `pos=x,y`, or should marks carry readability alone?
- **Levels.** Rostra, stairs and balconies need a height or a named level, e.g. `level=balcony`.
- **Groups.** Crowd and ensemble movement may want a `group` entity type so one `MOVE` can address several cast members.
- **Doubling.** One performer playing several characters. Whether a cast entity is a performer or a character affects validation.
- **Thrust stages.** A `thrust` type with the stage projecting downstage of the proscenium line; its width, origin and bounds need defining.
- **Prop orientation.** A `facing` for props such as a throne or an angled bench, and whether a carried prop's facing follows its carrier.
- **Moving attached props.** A way to send a carried prop across the stage in one directive, such as a throw, instead of `SET` then `MOVE` (E20).
- **Mid-scene PRESET.** Resetting entities in place mid-scene, and how such resets appear in the shift list. For now a reset starts a new scene.
- **Versioning.** A title page key such as `FSE: 0.1` would let processors detect the spec version.
- **Lighting and sound.** Deliberately out of scope for this draft; the keyword namespace should leave room for them.
