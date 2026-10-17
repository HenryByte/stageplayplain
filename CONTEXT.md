# Screenplain

Converts Fountain scripts (screenplays and stage plays) to PDF, HTML and FDX, and processes Fountain Stage Extension (FSE) blocking.

## Language

**FSE**:
Fountain Stage Extension: machine-readable stage blocking carried in Fountain notes that begin with the `FSE` marker. Defined in `stagecraft.md`. Independent of output mode: any Fountain script may carry it.
_Avoid_: stagecraft (the spec file's name, not the extension)

**FSE note**:
A Fountain note whose content begins with the marker `FSE` followed by whitespace.
_Avoid_: directive note, blocking note

**FSE script**:
A Fountain script with at least one FSE note that tokenises. Only an FSE script is processed and needs a `STAGE`; a script whose only FSE notes are near-misses is not one.
_Avoid_: annotated script

**Standalone note**:
An FSE note that forms a paragraph of its own, with empty lines around it and nothing but notes between them. It cues in the gap between the elements around it.
_Avoid_: note on its own line (a note-only line can still be glued)

**Inline note**:
An FSE note sharing a line with action, dialogue, parenthetical or lyric text. It cues at that word.

**Glued note**:
A line holding only an FSE note that shares a paragraph with lines that are not note-only, e.g. directly above a character cue or beneath a speech. Neither standalone nor inline: it cues where it sits, but Fountain classifies the paragraph without regard to it.

**Blocking**:
Everything a processor derives from one script's FSE notes: the stage, the declared entities, the directives with their cues, the timeline of state, and the reports.
_Avoid_: FSE data, parse result

**Cue**:
The point in the script where a directive takes effect: the gap before an element (standalone note), or a word within an element's line (inline or glued note). Anchored to the script's own elements, not to a separate copy of the text.
_Avoid_: anchor, position (position is where an entity is on stage)

**Character cue**:
Fountain's line naming the speaker above a speech, e.g. `HAMLET`. Always qualified; a bare "cue" is the timing sense. The `cue=` attribute gives a cast member's character cue.
_Avoid_: cue (unqualified), speaker line

**Timeline**:
The ordered steps of a script's blocking, grouped into scenes, from which the state at any cue can be read.

**Step**:
The effect of one FSE note: its cue, its directives, and the state of every entity after they apply together. The note is the unit of simultaneity, so the step is the timeline's tick.
_Avoid_: event, frame

**Script position**:
How far through the script a cue is, counted in words of performed text (dialogue, parentheticals, lyrics and action) before it. Not clock time: adjacent notes share a script position although stage time may pass between them.
_Avoid_: time, position (position is where an entity is on stage)

**Location**:
A place on the stage floor: a coordinate, or the id of a mark or entrance. Kept in the form the author wrote it; a mark's coordinate is looked up only when one is needed, so remapping a venue means moving marks.
_Avoid_: position (the interpolated point of an entity in transit)

**Whereabouts**:
Where an entity is at a step: at a location, on a prop, with a cast member, moving, or offstage. Exactly one at a time. Whether it is onstage is derived from it, never stored.
_Avoid_: location (that is only the floor place), placement (that is standalone, glued or inline)

**Moving**:
The whereabouts of an entity in transit: crossing the floor under an open move. Only cast members and props on the floor can be moving; anything with them follows.
_Avoid_: movement (a movement directive is any directive that changes whereabouts)

**Open move**:
A `MOVE ... until=arrive` not yet closed: its origin, destination, start cue and the `VIA` points with their cues. Closed by `ARRIVE`, or discarded by `EXIT`, `SET`, `STRIKE` or `STRIKE all`.

**Directive**:
One keyword-led instruction inside an FSE note; a note may hold several, separated by `;`.

**Processor**:
Any tool that reads FSE directives; a conforming processor parses them and reports the spec's errors and warnings.

**Scene boundary**:
A slugline, a forced (`.`) scene heading, or a section heading of any depth (`#`, `##`, …). Applies in screenplay and stage-play mode alike.
_Avoid_: scene break (ambiguous with page break `===`)

**PRESET**:
A directive asserting an entity's location at the top of a scene, after a scene boundary and before any other content. Only `PRESET` and `STRIKE all` may share its note.

**Scene change**:
The difference between the state carried into a scene and the state after its top-of-scene `PRESET` and `STRIKE all` directives: the props and cast the crew must set, strike or reposition in the transition.
_Avoid_: shift (the crew's list of the work, not the difference itself)

**Report**:
An error or warning a processor gives about the blocking: its code, line and the directive text that caused it. Processing stops at the first error, since later errors may be its consequences; warnings never stop it.
_Avoid_: diagnostic, message

**Near-miss**:
An FSE note whose content cannot be split into keyword-led directives of `key=value` attributes (unknown keyword, unterminated quote, malformed token). It is treated as an ordinary note and warned (W01). A note that splits cleanly but has wrong keys or values is not a near-miss; it fails validation.
_Avoid_: parse failure (too broad; key and value errors are validation)

**Offstage**:
An entity with no location of its own on the stage: a cast member with no `pos`, or a prop that has no `pos` and is not `on` or `with` anything onstage. A prop may be `on` or `with` an offstage entity (pre-set on a trolley, carried by an actor in the wings) and comes on when its carrier does.
_Avoid_: in the wings (implies a tracked offstage place)

**Onstage**:
A cast member with `pos`, or a prop whose `pos`, `on` or `with` chain ends on the stage floor.

**Going offstage**:
The transition of an onstage entity to offstage (`EXIT`, `STRIKE`, `STRIKE all`, or a `PRESET` with no location). Every prop `on` or `with` it goes off too and loses that attachment; attachments made while already offstage are kept.

**Plan**:
A small ground-plan drawing of the declared stage showing where entities are at one moment. Drawn only when blocking output is asked for.
_Avoid_: diagram, minimap, stage picture

**Scene plan**:
The plan at the top of a scene, showing the state after its top-of-scene `PRESET` and `STRIKE all`: the stage as the lights come up. It sits at the head of the scene, before its script, and carries the scene's key. A scene with nothing but another scene boundary before the next one has none.

**Key**:
The legend on a scene plan naming every cast member (by initials) and every prop (by number) that appears anywhere in its scene, including those off at the top. A prop keeps its number for the whole scene. Margin plans have no key of their own; they are read against their scene's key.
_Avoid_: legend

**Step group**:
Consecutive steps whose notes have nothing of the script between them (no dialogue, action or other element, not even a word). It gets one margin plan. Steps separated by anything stay in separate groups.
_Avoid_: cluster, merged steps

**Picture change**:
A step that changes the stage picture: some cast member's or prop's whereabouts, followed through `on` and `with` to the floor, or whether it is onstage. Starting an open move, each `VIA` and `ARRIVE` are picture changes; a facing change or a change of carrier alone is not.
_Avoid_: movement step

**Margin plan**:
The plan beside the script for one step group that holds at least one picture change, tied to its cue by a marker. Steps at the top of a scene never get one: the scene plan shows them. It is a drawing only, with no key. Margin plans stack in script order down the margin; the script text never moves to make room.

**Front matter**:
In a stage play, everything before the first page break (cast list, setting, notes): not part of the performance. Under blocking output it may hold no FSE note, declarations included, since it has no scenes to draw plans in.
_Avoid_: preamble, prelims
