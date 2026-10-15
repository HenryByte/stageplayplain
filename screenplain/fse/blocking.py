"""The result of processing a script's FSE notes: the `Blocking`."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from functools import cached_property

from screenplain.fse.directives import AnyDirective, Stage
from screenplain.fse.model import (
    At,
    Cast,
    Cue,
    Entity,
    Entrance,
    Facing,
    Location,
    Mark,
    Moving,
    On,
    Point,
    State,
    Whereabouts,
    With,
)
from screenplain.fse.reports import Report
from screenplain.fse.script import ScriptPositions
from screenplain.types import (
    SCREENPLAY_TYPES,
    DualDialog,
    Screenplay,
    Section,
    Slug,
)


@dataclass(frozen=True)
class Step:
    """The effect of one FSE note: its cue, its directives, and the state
    of every entity after they apply together.
    """

    cue: Cue
    directives: tuple[AnyDirective, ...]
    state: State


@dataclass
class Timeline:
    """The steps of a script's blocking, from which the state at any cue
    can be read. `initial` is the state at the top of the play, produced
    by the declaration block.
    """

    initial: State
    steps: list[Step] = field(default_factory=list)

    @cached_property
    def _cues(self) -> list[Cue]:
        return [step.cue for step in self.steps]

    def steps_at(self, paragraph: int) -> list[Step]:
        """The steps cued in a paragraph, in order."""
        return [step for step in self.steps if step.cue.paragraph == paragraph]

    def state_at(self, cue: Cue) -> State:
        """The state after every step at or before a cue."""
        index = bisect_right(self._cues, cue)
        return self.steps[index - 1].state if index else self.initial


@dataclass(frozen=True)
class Change:
    """How one entity differs between a scene's carried and preset state."""

    entity: str
    before: Whereabouts
    after: Whereabouts
    facing_before: Facing
    facing_after: Facing


@dataclass
class Scene:
    """A scene: the element that opens it, the state carried into it, the
    state after its top-of-scene `PRESET` and `STRIKE all` directives,
    and its steps (those included).
    """

    boundary: Slug | Section
    carried: State
    preset: State
    steps: list[Step] = field(default_factory=list)

    @property
    def change(self) -> list[Change]:
        """The entities that differ between the carried and preset state,
        including those that come on or go off with their carrier.
        """
        changes: list[Change] = []
        for entity_id in self.preset:
            before, after = self.carried[entity_id], self.preset[entity_id]
            if before != after or self.carried.onstage(
                entity_id
            ) != self.preset.onstage(entity_id):
                changes.append(
                    Change(
                        entity_id,
                        before.whereabouts,
                        after.whereabouts,
                        before.facing,
                        after.facing,
                    )
                )
        return changes


def normalise_character_cue(text: str) -> str:
    """Drops a character extension and case, for matching a cast member.

    >>> normalise_character_cue("Hamlet (V.O.)")
    'hamlet'
    """
    return " ".join(text.split("(", 1)[0].split()).casefold()


def cast_for(entities: dict[str, Entity], character_cue: str) -> Cast | None:
    """The cast member a character cue names, if any (§4.3)."""
    wanted = normalise_character_cue(character_cue)
    for entity in entities.values():
        if isinstance(entity, Cast):
            name = entity.character_cue or entity.id
            if normalise_character_cue(name) == wanted:
                return entity
    return None


def interpolate(start: Point, end: Point, s0: float, s1: float, s: float) -> Point:
    """The point at script position `s` on a segment from `start` at `s0`
    to `end` at `s1`. A segment with no script length stays at its start.

    >>> interpolate(Point(0, 0), Point(4, 2), 10, 14, 11)
    Point(x=1.0, y=0.5)
    >>> interpolate(Point(0, 0), Point(4, 2), 10, 10, 10)
    Point(x=0, y=0)
    """
    if s1 <= s0:
        return start
    t = min(max((s - s0) / (s1 - s0), 0.0), 1.0)
    return Point(start.x + (end.x - start.x) * t, start.y + (end.y - start.y) * t)


@dataclass
class Blocking:
    """Everything derived from one script's FSE notes.

    `stage` is None only for a script that is not an FSE script (one whose
    only FSE notes are near-misses). `reports` holds warnings only: a
    script with an error has no Blocking.
    """

    screenplay: Screenplay
    stage: Stage | None
    entities: dict[str, Entity]
    directives: list[AnyDirective]
    timeline: Timeline
    scenes: list[Scene]
    reports: list[Report]

    @cached_property
    def _positions(self) -> ScriptPositions:
        return ScriptPositions(self.screenplay)

    def cast_for(self, character_cue: str) -> Cast | None:
        """The cast member a character cue names: case-insensitive, with
        extensions such as `(V.O.)` dropped.
        """
        return cast_for(self.entities, character_cue)

    def element_at(self, cue: Cue) -> SCREENPLAY_TYPES:
        """The element a cue points into: a paragraph, or one speech of a
        dual dialogue.
        """
        para = self.screenplay.paragraphs[cue.paragraph]
        if isinstance(para, DualDialog):
            return para.right if cue.side == 1 else para.left
        return para

    def script_position(self, cue: Cue) -> int:
        """The number of words performed before a cue."""
        return self._positions.at(cue)

    def resolve(self, location: Location) -> Point:
        """The coordinate of a location."""
        if isinstance(location, Point):
            return location
        entity = self.entities[location.id]
        assert isinstance(entity, (Mark, Entrance))
        return entity.point

    def point_at(self, entity: str, cue: Cue) -> Point | None:
        """Where an entity is at a cue, interpolated if it is in transit;
        None when it is offstage.
        """
        state = self.timeline.state_at(cue)
        seen: set[str] = set()
        while entity not in seen:
            seen.add(entity)
            whereabouts = state.whereabouts(entity)
            if isinstance(whereabouts, At):
                return self.resolve(whereabouts.location)
            if isinstance(whereabouts, On):
                entity = whereabouts.prop
            elif isinstance(whereabouts, With):
                entity = whereabouts.cast
            elif isinstance(whereabouts, Moving):
                return self._point_in_transit(entity, whereabouts, cue)
            else:
                return None
        return None

    def _point_in_transit(self, entity: str, moving: Moving, cue: Cue) -> Point:
        move = moving.move
        last_location, last_cue = move.origin, move.start
        if move.vias:
            last_location, last_cue = move.vias[-1].location, move.vias[-1].cue
        # The segment ends at the next step that changes the move.
        end_location, end_cue = move.destination, last_cue
        index = bisect_right(self.timeline._cues, cue)
        for step in self.timeline.steps[index:]:
            whereabouts = step.state.whereabouts(entity)
            if whereabouts != moving:
                end_cue = step.cue
                if isinstance(whereabouts, Moving) and whereabouts.move.vias:
                    end_location = whereabouts.move.vias[-1].location
                break
        return interpolate(
            self.resolve(last_location),
            self.resolve(end_location),
            self.script_position(last_cue),
            self.script_position(end_cue),
            self.script_position(cue),
        )
