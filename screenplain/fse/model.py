"""The blocking's data model: locations, whereabouts, entities and state.

Locations are kept as written (`Place("window")` or `Point(-5, 0)`), so
remapping a venue means moving marks; coordinates are resolved on demand.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, override


@dataclass(frozen=True)
class Point:
    """A coordinate on the stage floor, in the declared unit."""

    x: float
    y: float

    def distance(self, other: Point) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass(frozen=True)
class Place:
    """A location given as the id of a mark or entrance."""

    id: str


type Location = Point | Place


@dataclass(frozen=True)
class Bearing:
    """A facing in degrees: 0 is +y (upstage), clockwise seen from above."""

    degrees: float


@dataclass(frozen=True)
class Toward:
    """A facing toward a location."""

    location: Location


# None is an unset facing.
type Facing = Bearing | Toward | None


@dataclass(frozen=True, order=True)
class Cue:
    """The point in the script where a directive takes effect.

    `paragraph` indexes `screenplay.paragraphs`. A standalone note's cue
    is its `Note` paragraph, with `part` -1. An inline (or glued) note's
    cue is its element's `side` (1 for the right speech of a
    `DualDialog`, else 0), its `part` (an index into `Action.lines` or
    `Dialog.blocks`) and the character `offset` into that part.

    Stacked notes can share a cue; step order breaks the tie.
    """

    paragraph: int
    side: int = 0
    part: int = -1
    offset: int = 0


@dataclass(frozen=True)
class Waypoint:
    """A `VIA` point of an open move, with its cue."""

    location: Location
    cue: Cue


@dataclass(frozen=True)
class OpenMove:
    """A `MOVE ... until=arrive` not yet closed."""

    origin: Location
    destination: Location
    start: Cue
    vias: tuple[Waypoint, ...] = ()


@dataclass(frozen=True)
class At:
    location: Location


@dataclass(frozen=True)
class On:
    prop: str


@dataclass(frozen=True)
class With:
    cast: str


@dataclass(frozen=True)
class Moving:
    move: OpenMove


@dataclass(frozen=True)
class Offstage:
    pass


OFFSTAGE = Offstage()

type Whereabouts = At | On | With | Moving | Offstage


@dataclass(frozen=True)
class Cast:
    kind: ClassVar[str] = "cast member"

    id: str
    label: str | None
    line: int
    # The `cue=` value, or None to match the id.
    character_cue: str | None = None


@dataclass(frozen=True)
class Prop:
    kind: ClassVar[str] = "prop"

    id: str
    label: str | None
    line: int


@dataclass(frozen=True)
class Mark:
    kind: ClassVar[str] = "mark"

    id: str
    label: str | None
    line: int
    point: Point


@dataclass(frozen=True)
class Entrance:
    kind: ClassVar[str] = "entrance"

    id: str
    label: str | None
    line: int
    point: Point


type Entity = Cast | Prop | Mark | Entrance

ENTITY_TYPES: dict[str, type[Cast | Prop | Mark | Entrance]] = {
    "cast": Cast,
    "prop": Prop,
    "mark": Mark,
    "entrance": Entrance,
}


@dataclass(frozen=True)
class EntityState:
    whereabouts: Whereabouts = OFFSTAGE
    facing: Facing = None


UNPLACED = EntityState()


class State(Mapping[str, EntityState]):
    """An immutable snapshot of every cast member's and prop's state."""

    def __init__(self, entries: Mapping[str, EntityState] | None = None) -> None:
        self._entries = MappingProxyType(dict(entries or {}))

    @override
    def __getitem__(self, key: str) -> EntityState:
        return self._entries[key]

    @override
    def __iter__(self) -> Iterator[str]:
        return iter(self._entries)

    @override
    def __len__(self) -> int:
        return len(self._entries)

    @override
    def __repr__(self) -> str:
        return f"State({dict(self._entries)!r})"

    def whereabouts(self, entity: str) -> Whereabouts:
        return self._entries[entity].whereabouts

    def facing(self, entity: str) -> Facing:
        return self._entries[entity].facing

    def onstage(self, entity: str) -> bool:
        return is_onstage(self._entries, entity)

    def carried(self, entity: str) -> list[str]:
        return carried(self._entries, entity)


def is_onstage(state: Mapping[str, EntityState], entity: str) -> bool:
    """Whether an entity is onstage: at a location or moving, or attached
    through an `on` and `with` chain to something that is.
    """
    seen: set[str] = set()
    while entity not in seen:
        seen.add(entity)
        whereabouts = state[entity].whereabouts
        if isinstance(whereabouts, (At, Moving)):
            return True
        if isinstance(whereabouts, On):
            entity = whereabouts.prop
        elif isinstance(whereabouts, With):
            entity = whereabouts.cast
        else:
            return False
    return False


def carrier(whereabouts: Whereabouts) -> str | None:
    if isinstance(whereabouts, On):
        return whereabouts.prop
    if isinstance(whereabouts, With):
        return whereabouts.cast
    return None


def carried(state: Mapping[str, EntityState], entity: str) -> list[str]:
    """The props `on` or `with` an entity, directly or through a chain."""
    children: dict[str, list[str]] = {}
    for entity_id, entity_state in state.items():
        parent = carrier(entity_state.whereabouts)
        if parent is not None:
            children.setdefault(parent, []).append(entity_id)
    result: list[str] = []
    pending = list(children.get(entity, []))
    while pending:
        prop = pending.pop(0)
        if prop in result or prop == entity:
            continue
        result.append(prop)
        pending += children.get(prop, [])
    return result
