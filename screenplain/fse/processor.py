"""Processes a Screenplay's FSE notes into a `Blocking`.

Notes are read in script order. The declaration block (everything before
the first scene boundary) is read first, so references in it may point
forward. Processing stops at the first error.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import NoReturn

from screenplain.fse.blocking import (
    Blocking,
    Scene,
    Step,
    Timeline,
    cast_for,
    interpolate,
    normalise_character_cue,
)
from screenplain.fse.directives import (
    RESERVED_IDS,
    AnyDirective,
    Arrive,
    Enter,
    Entity,
    Exit,
    Fault,
    Move,
    Preset,
    Set,
    Stage,
    Strike,
    Via,
    parse_location,
    validate,
)
from screenplain.fse.model import (
    OFFSTAGE,
    UNPLACED,
    At,
    Bearing,
    Cast,
    Cue,
    EntityState,
    Entrance,
    Location,
    Mark,
    Moving,
    On,
    OpenMove,
    Place,
    Point,
    Prop,
    State,
    Toward,
    Waypoint,
    Whereabouts,
    With,
    carried,
    is_onstage,
)
from screenplain.fse.model import Entity as EntityType
from screenplain.fse.reports import FseError, Report
from screenplain.fse.script import ScriptPositions, Site, collect_sites
from screenplain.fse.tokens import (
    LeadingSeparator,
    NearMiss,
    RawDirective,
    is_unclosed_fse_note,
    tokenise,
)
from screenplain.types import (
    Dialog,
    DualDialog,
    Note,
    PageBreak,
    Screenplay,
    Section,
    Slug,
)

# W04: how far a cast member can reach, in metres.
REACH = 1.5


@dataclass
class _Outcome:
    """The result of tokenising one FSE note."""

    raws: list[RawDirective] | None = None
    near_miss: str | None = None
    leading_separator: bool = False

    @property
    def tokenises(self) -> bool:
        return self.raws is not None or self.leading_separator


def _tokenise(site: Site) -> _Outcome:
    try:
        return _Outcome(raws=tokenise(site.text))
    except NearMiss as error:
        return _Outcome(near_miss=str(error))
    except LeadingSeparator:
        return _Outcome(leading_separator=True)


def _a(noun: str) -> str:
    """Prefixes the indefinite article: `a prop`, `an entrance`."""
    return ("an " if noun[0] in "aeiou" else "a ") + noun


def _note_text(text: str) -> str:
    return " ".join(text.split())


def _carrier_of(whereabouts: Whereabouts) -> str | None:
    if isinstance(whereabouts, On):
        return whereabouts.prop
    if isinstance(whereabouts, With):
        return whereabouts.cast
    return None


def process(screenplay: Screenplay, *, stageplay: bool = False) -> Blocking:
    """Processes a script's FSE notes.

    In a stage play, headings in the front matter (before the first page
    break) are not scene boundaries.

    Returns the `Blocking`, or raises `FseError` on the first error.
    """
    return _Processor(screenplay, stageplay).run()


class _Processor:
    def __init__(self, screenplay: Screenplay, stageplay: bool = False) -> None:
        self.screenplay = screenplay
        self.paragraphs = screenplay.paragraphs
        self.body_start = 0
        if stageplay:
            self.body_start = next(
                (
                    index + 1
                    for index, para in enumerate(self.paragraphs)
                    if isinstance(para, PageBreak)
                ),
                0,
            )
        self.positions = ScriptPositions(screenplay)
        self.sites = collect_sites(screenplay)
        self.outcomes = [_tokenise(site) for site in self.sites]
        self.unclosed = [
            note
            for note in screenplay.unclosed_notes
            if is_unclosed_fse_note(note.text)
        ]
        self.unclosed.sort(key=lambda note: note.line)
        self.first_boundary = next(
            (
                index
                for index in range(len(self.paragraphs))
                if self._is_boundary(index)
            ),
            len(self.paragraphs),
        )
        self.warnings: list[Report] = []
        self.checked: set[int] = set()
        self.current = -1

        self.stage: Stage | None = None
        self.entities: dict[str, EntityType] = {}
        self.declarations: dict[str, Entity] = {}
        self.directives: dict[int, list[AnyDirective]] = {}
        self.first_directive: tuple[int, str] | None = None

        self.state: dict[str, EntityState] = {}
        self.initial = State()
        self.steps: list[Step] = []
        self.scenes: list[Scene] = []
        self.scene: Scene | None = None
        self.content = False
        self.moves: dict[tuple[str, Cue], Move] = {}
        self.ever_onstage: set[str] = set()
        self.unmatched_cues: set[str] = set()

    def _is_boundary(self, index: int) -> bool:
        return index >= self.body_start and isinstance(
            self.paragraphs[index], (Slug, Section)
        )

    # Reporting

    def _error(self, code: str, line: int, text: str, message: str) -> NoReturn:
        raise FseError(Report(code, line, text, message), list(self.warnings))

    def _fail(self, code: str, directive: AnyDirective, message: str) -> NoReturn:
        self._error(code, directive.line, directive.text, message)

    def _warn(self, code: str, line: int, text: str, message: str) -> None:
        self.warnings.append(Report(code, line, text, message))

    # The walk

    def run(self) -> Blocking:
        if not any(outcome.tokenises for outcome in self.outcomes):
            # Not an FSE script: near-misses warn, unclosed notes block.
            for index in range(len(self.sites)):
                self._check_site(index)
            self._unclosed_before(None)
            return Blocking(
                self.screenplay, None, {}, [], Timeline(State()), [], self.warnings
            )

        self._declare()
        self._walk()
        self._unclosed_before(None)
        self._check_open_moves()
        if self.stage is None:
            assert self.first_directive is not None
            line, text = self.first_directive
            self._error("E01", line, text, "the script has no STAGE")
        for entity_id, entity in self.entities.items():
            if isinstance(entity, (Cast, Prop)) and entity_id not in self.ever_onstage:
                declaration = self.declarations[entity_id]
                self._warn(
                    "W06",
                    declaration.line,
                    declaration.text,
                    f"{entity_id} never appears onstage",
                )
        directives = [
            d for index in sorted(self.directives) for d in self.directives[index]
        ]
        return Blocking(
            self.screenplay,
            self.stage,
            dict(self.entities),
            directives,
            Timeline(self.initial, self.steps),
            self.scenes,
            self.warnings,
        )

    def _unclosed_before(self, line: int | None) -> None:
        """Raises E21 for an unclosed FSE note before `line` (None for the
        end of the script).
        """
        if self.unclosed and (line is None or self.unclosed[0].line < line):
            note = self.unclosed[0]
            rows = [row.strip() for row in note.text.split("\n")]
            text = "[[" + next((row for row in rows if row), "")
            self._error(
                "E21",
                note.line,
                text,
                "no ]] before an empty line or the end of the script",
            )

    def _check_site(self, index: int) -> list[RawDirective] | None:
        """Checks a note's placement and tokenising, once. Returns its
        directives, or None for a near-miss.
        """
        site, outcome = self.sites[index], self.outcomes[index]
        if index in self.checked:
            return outcome.raws
        self.checked.add(index)
        self._unclosed_before(site.line)
        text = _note_text(site.text)
        if outcome.near_miss is not None:
            self._warn(
                "W01", site.line, text, f"{outcome.near_miss}; read as an ordinary note"
            )
            return None
        if outcome.leading_separator:
            self._error("E19", site.line, text, "';' straight after the FSE marker")
        if site.misplaced is not None:
            self._error(
                "E12",
                site.line,
                text,
                f"an FSE note may not appear in {site.misplaced}",
            )
        if site.glued:
            self._warn(
                "W09", site.line, text, "the note shares a paragraph with other text"
            )
        assert outcome.raws is not None
        if self.first_directive is None:
            raw = outcome.raws[0]
            self.first_directive = (site.line + raw.line_offset, raw.text)
        return outcome.raws

    def _validate(self, index: int, raw: RawDirective) -> AnyDirective:
        site = self.sites[index]
        line = site.line + raw.line_offset
        subject = raw.subject
        if subject is None and raw.keyword not in ("STAGE", "ENTITY") and site.speaker:
            cast = cast_for(self.entities, site.speaker)
            if cast is None:
                self._error(
                    "E02",
                    line,
                    raw.text,
                    f"the speaker {site.speaker} matches no cast for the implied subject",
                )
            subject = cast.id
        try:
            return validate(raw, cue=site.cue, line=line, subject=subject)
        except Fault as fault:
            self._error(fault.code, line, raw.text, fault.message)

    def _declare(self) -> None:
        """Reads the declaration block: STAGE and ENTITY directives before
        the first scene boundary. Sets the initial state.
        """
        seen_directive = False
        for index, site in enumerate(self.sites):
            if site.cue.paragraph >= self.first_boundary:
                break
            raws = self._check_site(index)
            for raw in raws or []:
                if raw.keyword == "STAGE":
                    stage = self._validate(index, raw)
                    assert isinstance(stage, Stage)
                    if self.stage is not None:
                        self._fail("E01", stage, "more than one STAGE")
                    if seen_directive:
                        self._fail(
                            "E12", stage, "STAGE must come before every other directive"
                        )
                    self.stage = stage
                    self.directives.setdefault(index, []).append(stage)
                elif raw.keyword == "ENTITY":
                    entity = self._validate(index, raw)
                    assert isinstance(entity, Entity)
                    self._declare_entity(entity)
                    self.directives.setdefault(index, []).append(entity)
                seen_directive = True

        for declaration in self.declarations.values():
            self._resolve_declaration(declaration)
        if self.stage is not None and self.stage.front is not None:
            front = self._ref(self.stage, self.stage.front, (Mark, Entrance), "front")
            assert isinstance(front, (Mark, Entrance))
            if not (front.point.x == 0 and front.point.y < 0):
                self._fail(
                    "E17", self.stage, f"front {front.id} is not on the negative y-axis"
                )
        self._check_cycles(self.state, list(self.declarations.values()))
        self.initial = State(self.state)
        self._note_onstage()

    def _declare_entity(self, declaration: Entity) -> None:
        entity_id = declaration.subject
        if entity_id in RESERVED_IDS:
            self._fail("E03", declaration, f"{entity_id} is a reserved id")
        if entity_id in self.entities:
            self._fail("E03", declaration, f"{entity_id} is already declared")
        line, label = declaration.line, declaration.label
        match declaration.type:
            case "cast":
                entity = Cast(entity_id, label, line, declaration.character_cue)
            case "prop":
                entity = Prop(entity_id, label, line)
            case "mark" | "entrance":
                assert isinstance(declaration.pos, Point)
                cls = Mark if declaration.type == "mark" else Entrance
                entity = cls(entity_id, label, line, declaration.pos)
            case _:
                raise AssertionError(declaration.type)
        self.entities[entity_id] = entity
        self.declarations[entity_id] = declaration

    def _resolve_declaration(self, declaration: Entity) -> None:
        entity = self.entities[declaration.subject]
        if isinstance(entity, Mark):
            assert isinstance(declaration.pos, Point)
            self._out_of_bounds(declaration, declaration.pos)
        if not isinstance(entity, (Cast, Prop)):
            return
        whereabouts: Whereabouts = OFFSTAGE
        if declaration.pos is not None:
            self._check_location(declaration, declaration.pos)
            if isinstance(declaration.pos, Point):
                self._out_of_bounds(declaration, declaration.pos)
            whereabouts = At(declaration.pos)
        elif declaration.on is not None:
            self._ref(declaration, declaration.on, (Prop,), "on")
            whereabouts = On(declaration.on)
        elif declaration.with_ is not None:
            self._ref(declaration, declaration.with_, (Cast,), "with")
            whereabouts = With(declaration.with_)
        self._check_facing(declaration, declaration.facing)
        self.state[entity.id] = EntityState(whereabouts, declaration.facing)

    def _walk(self) -> None:
        by_paragraph: dict[int, list[int]] = {}
        for index, site in enumerate(self.sites):
            by_paragraph.setdefault(site.cue.paragraph, []).append(index)
        for index in by_paragraph.pop(-1, []):
            self._note(index)
        for paragraph, para in enumerate(self.paragraphs):
            if self._is_boundary(paragraph):
                assert isinstance(para, (Slug, Section))
                self._boundary(para)
            elif not isinstance(para, (Note, PageBreak)):
                self.content = True
            indexes = by_paragraph.get(paragraph, [])
            if isinstance(para, Dialog):
                self._speech(paragraph, 0, para, indexes)
            elif isinstance(para, DualDialog):
                self._speech(paragraph, 0, para.left, indexes)
                self._speech(paragraph, 1, para.right, indexes)
            else:
                for index in indexes:
                    self._note(index)

    def _speech(
        self, paragraph: int, side: int, dialog: Dialog, indexes: list[int]
    ) -> None:
        """Processes a speech's notes, checking its speaker (W02, W07) as
        the first word is spoken.
        """
        cast = cast_for(self.entities, str(dialog.character))
        line = dialog.line or 0
        if cast is None:
            key = normalise_character_cue(str(dialog.character))
            if key not in self.unmatched_cues:
                self.unmatched_cues.add(key)
                self._warn(
                    "W07",
                    line,
                    str(dialog.character),
                    "the character cue matches no cast",
                )
        start = self.positions.at(Cue(paragraph, side, 0, 0))
        spoken = False
        for index in indexes:
            cue = self.sites[index].cue
            if cue.side != side:
                continue
            if not spoken and cue.part >= 0 and self.positions.at(cue) > start:
                self._speaker_check(cast, dialog, line)
                spoken = True
            self._note(index)
        if not spoken:
            self._speaker_check(cast, dialog, line)

    def _speaker_check(self, cast: Cast | None, dialog: Dialog, line: int) -> None:
        if cast is not None and not is_onstage(self.state, cast.id):
            self._warn(
                "W02", line, str(dialog.character), f"{cast.id} speaks while offstage"
            )

    def _boundary(self, para: Slug | Section) -> None:
        self._check_open_moves()
        snapshot = State(self.state)
        self.scene = Scene(para, snapshot, snapshot)
        self.scenes.append(self.scene)
        self.content = False

    def _check_open_moves(self) -> None:
        for entity_id, entity_state in self.state.items():
            whereabouts = entity_state.whereabouts
            if isinstance(whereabouts, Moving):
                move = self.moves[entity_id, whereabouts.move.start]
                self._fail(
                    "E15",
                    move,
                    f"{entity_id}'s move is not closed by ARRIVE before the scene ends",
                )

    def _note(self, index: int) -> None:
        self.current = index
        raws = self._check_site(index)
        if raws is None:
            return
        in_declarations = self.sites[index].cue.paragraph < self.first_boundary
        directives: list[AnyDirective] = []
        for raw in raws:
            if raw.keyword in ("STAGE", "ENTITY"):
                if in_declarations:
                    continue
                directive = self._validate(index, raw)
                if isinstance(directive, Stage) and self.stage is not None:
                    self._fail("E01", directive, "more than one STAGE")
                self._fail(
                    "E12",
                    directive,
                    f"{raw.keyword} must be in the declaration block, before the first scene",
                )
            directives.append(self._validate(index, raw))
        if directives:
            self.directives.setdefault(index, []).extend(directives)
            self._apply(self.sites[index].cue, directives)

    # Applying a note

    def _apply(self, cue: Cue, directives: list[AnyDirective]) -> None:
        pre = self.state
        presets = [d for d in directives if isinstance(d, Preset)]
        preset_note = all(
            isinstance(d, Preset) or (isinstance(d, Strike) and d.subject == "all")
            for d in directives
        )
        if presets:
            preset = presets[0]
            if not preset_note:
                other = next(
                    d for d in directives if not isinstance(d, (Preset, Strike))
                )
                self._fail(
                    "E12",
                    preset,
                    f"PRESET may not share a note with {type(other).__name__.upper()}",
                )
            if self.scene is None:
                self._fail("E12", preset, "PRESET must follow a scene boundary")
            if self.content:
                self._fail(
                    "E12",
                    preset,
                    "PRESET must come before any other content in the scene",
                )

        for directive in directives:
            self._check(directive, pre)
        self._check_same_entity(directives, pre)
        for directive in directives:
            self._check_reach(directive, pre)
            pos = getattr(directive, "pos", None)
            if isinstance(pos, Point):
                self._out_of_bounds(directive, pos)

        new = dict(pre)
        for directive in sorted(
            directives, key=lambda d: not isinstance(d, Strike) or d.subject != "all"
        ):
            self._effect(directive, pre, new)
        self._check_cycles(new, directives)

        self.state = new
        step = Step(cue, tuple(directives), State(new))
        self.steps.append(step)
        self._note_onstage()
        if self.scene is not None:
            self.scene.steps.append(step)
            if preset_note and not self.content:
                self.scene.preset = step.state
        if not preset_note:
            self.content = True

    def _note_onstage(self) -> None:
        for entity_id in self.state:
            if entity_id not in self.ever_onstage and is_onstage(self.state, entity_id):
                self.ever_onstage.add(entity_id)

    # Checks

    def _ref(
        self,
        directive: AnyDirective,
        entity_id: str,
        kinds: tuple[type[EntityType], ...],
        key: str,
    ) -> EntityType:
        """Looks up the entity an attribute refers to (E02, E04)."""
        wanted = " or ".join(kind.kind for kind in kinds)
        if entity_id in RESERVED_IDS:
            self._fail(
                "E04",
                directive,
                f"{key}={entity_id}: {entity_id} is reserved, not {_a(wanted)}",
            )
        entity = self.entities.get(entity_id)
        if entity is None:
            self._fail("E02", directive, f"{entity_id} is not declared")
        if not isinstance(entity, kinds):
            self._fail(
                "E04",
                directive,
                f"{key}={entity_id}: {entity_id} is {_a(entity.kind)}, not {_a(wanted)}",
            )
        return entity

    def _check_location(
        self, directive: AnyDirective, location: Location | None
    ) -> None:
        if isinstance(location, Place):
            self._ref(directive, location.id, (Mark, Entrance), "pos")

    def _check_facing(
        self, directive: AnyDirective, facing: Bearing | Toward | None
    ) -> None:
        if isinstance(facing, Toward) and isinstance(facing.location, Place):
            self._ref(directive, facing.location.id, (Mark, Entrance), "facing")

    def _check_by(self, directive: AnyDirective, by: str | None) -> None:
        if by is not None and by != "crew":
            self._ref(directive, by, (Cast,), "by")

    def _subject(
        self, directive: AnyDirective, kinds: tuple[type[EntityType], ...]
    ) -> EntityType:
        subject: str = getattr(directive, "subject")  # noqa: B009
        keyword = type(directive).__name__.upper()
        if subject in RESERVED_IDS:
            self._fail(
                "E04", directive, f"{subject} cannot be the subject of {keyword}"
            )
        entity = self.entities.get(subject)
        if entity is None:
            self._fail("E02", directive, f"{subject} is not declared")
        if isinstance(entity, (Mark, Entrance)):
            self._fail(
                "E07", directive, f"{subject} is {_a(entity.kind)}, which is fixed"
            )
        if not isinstance(entity, kinds):
            wanted = " or ".join(kind.kind for kind in kinds)
            self._fail(
                "E04",
                directive,
                f"{subject} is {_a(entity.kind)}; {keyword} needs {_a(wanted)}",
            )
        return entity

    def _not_on(self, directive: AnyDirective, entity: EntityType, *keys: str) -> None:
        """Raises E16 for any of `keys` given on a directive whose subject
        is `entity`.
        """
        for key in keys:
            if getattr(directive, key) is not None:
                name = key.rstrip("_")
                keyword = type(directive).__name__.upper()
                self._fail(
                    "E16",
                    directive,
                    f"{name} is not an attribute of {keyword} on {_a(entity.kind)}",
                )

    def _check(self, directive: AnyDirective, pre: dict[str, EntityState]) -> None:
        match directive:
            case Enter():
                entity = self._subject(directive, (Cast, Prop))
                if isinstance(entity, Cast):
                    if directive.from_ is None:
                        self._fail(
                            "E08", directive, "ENTER on a cast member needs from"
                        )
                else:
                    self._not_on(directive, entity, "facing")
                    if directive.from_ is None and directive.pos is None:
                        self._fail(
                            "E08", directive, "ENTER on a prop needs from or pos"
                        )
                if directive.from_ is not None:
                    self._ref(directive, directive.from_, (Entrance,), "from")
                self._check_location(directive, directive.pos)
                self._check_facing(directive, directive.facing)
                if is_onstage(pre, entity.id):
                    self._fail("E06", directive, f"{entity.id} is already onstage")
            case Exit():
                if directive.via is not None:
                    self._ref(directive, directive.via, (Entrance,), "via")
                if directive.subject == "all":
                    return
                entity = self._subject(directive, (Cast,))
                if directive.via is None:
                    self._fail("E08", directive, "EXIT needs via")
                if not is_onstage(pre, entity.id):
                    self._fail("E05", directive, f"{entity.id} is offstage")
            case Move():
                entity = self._subject(directive, (Cast, Prop))
                self._not_on(
                    directive, entity, "by" if isinstance(entity, Cast) else "facing"
                )
                self._check_location(directive, directive.pos)
                self._check_facing(directive, directive.facing)
                self._check_by(directive, directive.by)
                whereabouts = pre[entity.id].whereabouts
                if isinstance(whereabouts, Moving):
                    self._fail(
                        "E13", directive, f"{entity.id} already has an open move"
                    )
                if not is_onstage(pre, entity.id):
                    self._fail("E05", directive, f"{entity.id} is offstage")
                if isinstance(whereabouts, (On, With)):
                    carrier = _carrier_of(whereabouts)
                    self._fail(
                        "E20",
                        directive,
                        f"{entity.id} is attached to {carrier}; SET it down first",
                    )
            case Via():
                entity = self._subject(directive, (Cast, Prop))
                self._check_location(directive, directive.pos)
                if not isinstance(pre[entity.id].whereabouts, Moving):
                    self._fail("E14", directive, f"{entity.id} has no open move")
            case Arrive():
                entity = self._subject(directive, (Cast, Prop))
                if isinstance(entity, Prop):
                    self._not_on(directive, entity, "facing")
                self._check_facing(directive, directive.facing)
                if not isinstance(pre[entity.id].whereabouts, Moving):
                    self._fail("E14", directive, f"{entity.id} has no open move")
            case Set():
                entity = self._subject(directive, (Cast, Prop))
                if isinstance(entity, Cast):
                    self._not_on(directive, entity, "pos", "on", "with_", "by")
                    if directive.facing is None:
                        self._fail(
                            "E08", directive, "SET on a cast member needs facing"
                        )
                else:
                    self._not_on(directive, entity, "facing")
                    if (
                        directive.pos is None
                        and directive.on is None
                        and directive.with_ is None
                    ):
                        self._fail(
                            "E08", directive, "SET on a prop needs pos, on or with"
                        )
                self._check_location(directive, directive.pos)
                self._check_facing(directive, directive.facing)
                if directive.on is not None:
                    self._ref(directive, directive.on, (Prop,), "on")
                    if directive.on == entity.id:
                        self._fail("E11", directive, f"{entity.id} cannot be on itself")
                if directive.with_ is not None:
                    self._ref(directive, directive.with_, (Cast,), "with")
                self._check_by(directive, directive.by)
            case Strike():
                if directive.subject == "all":
                    if directive.by is not None:
                        self._fail(
                            "E16", directive, "by is not an attribute of STRIKE all"
                        )
                    return
                entity = self._subject(directive, (Prop,))
                self._check_by(directive, directive.by)
                if not is_onstage(pre, entity.id):
                    self._fail("E05", directive, f"{entity.id} is offstage")
            case Preset():
                entity = self._subject(directive, (Cast, Prop))
                if isinstance(entity, Cast):
                    self._not_on(directive, entity, "on", "with_")
                else:
                    self._not_on(directive, entity, "facing")
                self._check_location(directive, directive.pos)
                self._check_facing(directive, directive.facing)
                if directive.on is not None:
                    self._ref(directive, directive.on, (Prop,), "on")
                    if directive.on == entity.id:
                        self._fail("E11", directive, f"{entity.id} cannot be on itself")
                if directive.with_ is not None:
                    self._ref(directive, directive.with_, (Cast,), "with")
            case _:
                raise AssertionError(directive)

    def _affected(
        self, directive: AnyDirective, pre: dict[str, EntityState]
    ) -> set[str]:
        """The entities a directive affects (§6.3): its subject and, when it
        moves its subject or takes it off, every prop carried by it.
        """
        if isinstance(directive, Exit) and directive.subject == "all":
            ids = {
                entity_id
                for entity_id, entity in self.entities.items()
                if isinstance(entity, Cast) and is_onstage(pre, entity_id)
            }
            return ids.union(*(carried(pre, entity_id) for entity_id in ids))
        subject: str = getattr(directive, "subject")  # noqa: B009
        moves = not (
            isinstance(directive, Set)
            and directive.facing is not None
            and isinstance(self.entities[subject], Cast)
        )
        if moves:
            return {subject, *carried(pre, subject)}
        return {subject}

    def _check_same_entity(
        self, directives: Sequence[AnyDirective], pre: dict[str, EntityState]
    ) -> None:
        strike_all = any(
            isinstance(d, Strike) and d.subject == "all" for d in directives
        )
        affected: set[str] = set()
        for directive in directives:
            if isinstance(directive, Strike) and directive.subject == "all":
                continue
            if strike_all and not isinstance(directive, Preset):
                self._fail(
                    "E10", directive, "STRIKE all in the same note affects every entity"
                )
            ids = self._affected(directive, pre)
            overlap = ids & affected
            if overlap:
                self._fail(
                    "E10",
                    directive,
                    f"{', '.join(sorted(overlap))} is affected by another directive in this note",
                )
            affected |= ids

    def _check_cycles(
        self, state: dict[str, EntityState], directives: Sequence[AnyDirective]
    ) -> None:
        for entity_id in state:
            seen = [entity_id]
            whereabouts = state[entity_id].whereabouts
            while isinstance(whereabouts, On):
                if whereabouts.prop in seen:
                    cycle = [*seen[seen.index(whereabouts.prop) :], whereabouts.prop]
                    culprit = next(
                        (d for d in directives if getattr(d, "subject", None) in cycle),
                        directives[0],
                    )
                    self._fail(
                        "E11",
                        culprit,
                        f"props attached in a loop: {' on '.join(cycle)}",
                    )
                seen.append(whereabouts.prop)
                whereabouts = state[whereabouts.prop].whereabouts

    def _out_of_bounds(self, directive: AnyDirective, point: Point) -> None:
        if self.stage is not None and not self.stage.contains(point):
            self._warn(
                "W03",
                directive.line,
                directive.text,
                f"{point.x:g},{point.y:g} is outside the stage",
            )

    # Points and reach

    def _resolve(self, location: Location) -> Point:
        if isinstance(location, Point):
            return location
        entity = self.entities[location.id]
        assert isinstance(entity, (Mark, Entrance))
        return entity.point

    def _point(
        self, state: dict[str, EntityState], entity_id: str, cue: Cue
    ) -> Point | None:
        seen: set[str] = set()
        while entity_id not in seen:
            seen.add(entity_id)
            whereabouts = state[entity_id].whereabouts
            if isinstance(whereabouts, At):
                return self._resolve(whereabouts.location)
            if isinstance(whereabouts, Moving):
                return self._point_in_transit(entity_id, whereabouts.move, cue)
            carrier = _carrier_of(whereabouts)
            if carrier is None:
                return None
            entity_id = carrier
        return None

    def _point_in_transit(self, entity_id: str, move: OpenMove, cue: Cue) -> Point:
        last = move.vias[-1] if move.vias else Waypoint(move.origin, move.start)
        end_location, end_cue = self._segment_end(entity_id, move)
        return interpolate(
            self._resolve(last.location),
            self._resolve(end_location),
            self.positions.at(last.cue),
            self.positions.at(end_cue) if end_cue else self.positions.at(last.cue),
            self.positions.at(cue),
        )

    def _segment_end(
        self, entity_id: str, move: OpenMove
    ) -> tuple[Location, Cue | None]:
        """Looks ahead for where the current segment of an open move ends:
        the next VIA for the entity, or whatever closes the move.
        """
        boundary = next(
            (
                index
                for index in range(
                    self.sites[self.current].cue.paragraph + 1, len(self.paragraphs)
                )
                if self._is_boundary(index)
            ),
            None,
        )
        for index in range(self.current + 1, len(self.sites)):
            site, outcome = self.sites[index], self.outcomes[index]
            if boundary is not None and site.cue.paragraph > boundary:
                return move.destination, Cue(boundary)
            for raw in outcome.raws or []:
                subject = raw.subject
                if subject is None and site.speaker:
                    cast = cast_for(self.entities, site.speaker)
                    subject = cast.id if cast else None
                if raw.keyword in ("STRIKE", "EXIT") and subject == "all":
                    return move.destination, site.cue
                if subject != entity_id:
                    continue
                if raw.keyword == "VIA":
                    pos = dict(raw.attributes).get("pos")
                    location = parse_location(pos) if pos else None
                    if location is not None:
                        return location, site.cue
                if raw.keyword in ("ARRIVE", "EXIT", "SET", "STRIKE"):
                    return move.destination, site.cue
        if boundary is not None:
            return move.destination, Cue(boundary)
        return move.destination, None

    def _check_reach(
        self, directive: AnyDirective, pre: dict[str, EntityState]
    ) -> None:
        if not isinstance(directive, (Set, Move, Strike)):
            return
        by = directive.by
        if by is None or by == "crew" or directive.subject == "all":
            return
        if not is_onstage(pre, by):
            self._warn("W04", directive.line, directive.text, f"{by} is offstage")
            return
        reach_point = self._point(pre, by, directive.cue)
        assert reach_point is not None
        units = self.stage.units if self.stage else "m"
        reach = REACH / (self.stage.metres_per_unit if self.stage else 1.0)
        targets: list[tuple[str, Point | None]] = [
            (directive.subject, self._point(pre, directive.subject, directive.cue))
        ]
        if isinstance(directive, Set):
            if directive.pos is not None:
                targets.append(
                    (str(_location_text(directive.pos)), self._resolve(directive.pos))
                )
            for target in (directive.on, directive.with_):
                if target is not None:
                    targets.append((target, self._point(pre, target, directive.cue)))
        for name, point in targets:
            if point is None:
                continue
            distance = reach_point.distance(point)
            if distance > reach + 1e-9:
                self._warn(
                    "W04",
                    directive.line,
                    directive.text,
                    f"{by} is {distance:.1f} {units} from {name}",
                )
                return

    # Effects

    def _go_offstage(
        self, entity_id: str, pre: dict[str, EntityState], new: dict[str, EntityState]
    ) -> None:
        new[entity_id] = UNPLACED
        for prop in carried(pre, entity_id):
            new[prop] = UNPLACED

    def _effect(
        self,
        directive: AnyDirective,
        pre: dict[str, EntityState],
        new: dict[str, EntityState],
    ) -> None:
        cue = directive.cue
        match directive:
            case Strike(subject="all"):
                for entity_id in new:
                    facing = (
                        None if is_onstage(pre, entity_id) else pre[entity_id].facing
                    )
                    new[entity_id] = EntityState(OFFSTAGE, facing)
            case Exit(subject="all"):
                for entity_id, entity in self.entities.items():
                    if isinstance(entity, Cast) and is_onstage(pre, entity_id):
                        self._go_offstage(entity_id, pre, new)
            case Exit() | Strike():
                self._go_offstage(directive.subject, pre, new)
            case Enter():
                assert directive.from_ is not None or directive.pos is not None
                location = directive.pos or Place(directive.from_ or "")
                self._place(directive.subject, At(location), directive.facing, pre, new)
            case Move():
                location: Location = directive.pos
                whereabouts: Whereabouts = At(location)
                if directive.until_arrive:
                    current = pre[directive.subject].whereabouts
                    assert isinstance(current, At)
                    whereabouts = Moving(OpenMove(current.location, location, cue))
                    self.moves[directive.subject, cue] = directive
                self._place(directive.subject, whereabouts, directive.facing, pre, new)
            case Via():
                current = pre[directive.subject].whereabouts
                assert isinstance(current, Moving)
                waypoint = Waypoint(directive.pos, cue)
                move = replace(current.move, vias=(*current.move.vias, waypoint))
                self._place(directive.subject, Moving(move), None, pre, new)
            case Arrive():
                current = pre[directive.subject].whereabouts
                assert isinstance(current, Moving)
                destination = At(current.move.destination)
                self._place(directive.subject, destination, directive.facing, pre, new)
            case Set():
                whereabouts = _target(directive.pos, directive.on, directive.with_)
                if whereabouts is None:
                    whereabouts = pre[directive.subject].whereabouts
                self._place(directive.subject, whereabouts, directive.facing, pre, new)
            case Preset():
                whereabouts = (
                    _target(directive.pos, directive.on, directive.with_) or OFFSTAGE
                )
                subject = directive.subject
                if whereabouts == OFFSTAGE and is_onstage(pre, subject):
                    self._go_offstage(subject, pre, new)
                    new[subject] = EntityState(OFFSTAGE, directive.facing)
                else:
                    self._place(subject, whereabouts, directive.facing, pre, new)
            case _:
                raise AssertionError(directive)

    def _place(
        self,
        entity_id: str,
        whereabouts: Whereabouts,
        facing: Bearing | Toward | None,
        pre: dict[str, EntityState],
        new: dict[str, EntityState],
    ) -> None:
        if facing is None:
            facing = pre[entity_id].facing
        new[entity_id] = EntityState(whereabouts, facing)


def _target(
    pos: Location | None, on: str | None, with_: str | None
) -> Whereabouts | None:
    if pos is not None:
        return At(pos)
    if on is not None:
        return On(on)
    if with_ is not None:
        return With(with_)
    return None


def _location_text(location: Location) -> str:
    if isinstance(location, Point):
        return f"{location.x:g},{location.y:g}"
    return location.id
