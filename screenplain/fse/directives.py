"""Typed directives, one class per keyword, and their validation.

Validation here covers what a directive says on its own: known keys
(E16), duplicates (E18), value types (E17), required attributes (E08)
and conflicting locations (E09). Checks that need the declared entities
or the state are made by the processor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from screenplain.fse.model import Bearing, Cue, Facing, Location, Place, Point, Toward
from screenplain.fse.tokens import RawDirective

_number_re = re.compile(r"-?(?:\d+(?:\.\d+)?|\.\d+)")
_id_re = re.compile(r"[a-z0-9][a-z0-9_-]*")

STAGE_TYPES = ("proscenium", "traverse", "round", "flexible")
UNITS = {"m": 1.0, "cm": 0.01, "ft": 0.3048, "in": 0.0254}

RESERVED_IDS = ("crew", "all")


class Fault(Exception):
    """A validation failure: a code and a message, without a line."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def parse_number(value: str) -> float | None:
    """Parses a number, or returns None.

    >>> parse_number('-2.5'), parse_number('.5'), parse_number('5.'), parse_number('1e3')
    (-2.5, 0.5, None, None)
    """
    return float(value) if _number_re.fullmatch(value) else None


def is_id(value: str) -> bool:
    """Whether a value is a well-formed id.

    >>> is_id('vom-1'), is_id('2b'), is_id('Hamlet'), is_id('90')
    (True, True, False, False)
    """
    return _id_re.fullmatch(value) is not None and parse_number(value) is None


def parse_coordinate(value: str) -> Point | None:
    """Parses `x,y`, or returns None.

    >>> parse_coordinate('-2.5,3')
    Point(x=-2.5, y=3.0)
    """
    parts = value.split(",")
    if len(parts) != 2:
        return None
    x, y = (parse_number(part) for part in parts)
    if x is None or y is None:
        return None
    return Point(x, y)


def parse_location(value: str) -> Location | None:
    point = parse_coordinate(value)
    if point is not None:
        return point
    return Place(value) if is_id(value) else None


def parse_direction(value: str) -> Bearing | Toward | None:
    """Parses a facing: a bearing (mod 360), coordinate or id.

    >>> parse_direction('-90')
    Bearing(degrees=270.0)
    >>> parse_direction('window')
    Toward(location=Place(id='window'))
    """
    number = parse_number(value)
    if number is not None:
        return Bearing(number % 360)
    location = parse_location(value)
    return Toward(location) if location is not None else None


@dataclass(frozen=True, kw_only=True)
class Directive:
    """A validated directive. `text` is its source, `line` the source line
    it starts on, and `implied_subject` says that its subject was taken
    from the speaker (an id-less directive in dialogue).
    """

    cue: Cue
    line: int
    text: str
    implied_subject: bool = False


@dataclass(frozen=True, kw_only=True)
class Stage(Directive):
    type: str
    units: str = "m"
    width: float | None = None
    depth: float | None = None
    radius: float | None = None
    front: str | None = None

    @property
    def metres_per_unit(self) -> float:
        return UNITS[self.units]

    def contains(self, point: Point) -> bool:
        """Whether a point lies on the declared stage (W03)."""
        if self.radius is not None:
            return point.distance(Point(0, 0)) <= self.radius
        assert self.width is not None and self.depth is not None
        return abs(point.x) <= self.width / 2 and abs(point.y) <= self.depth / 2


@dataclass(frozen=True, kw_only=True)
class Entity(Directive):
    subject: str
    type: str
    pos: Location | None = None
    on: str | None = None
    with_: str | None = None
    facing: Facing = None
    character_cue: str | None = None
    label: str | None = None


@dataclass(frozen=True, kw_only=True)
class Enter(Directive):
    subject: str
    from_: str | None = None
    pos: Location | None = None
    facing: Facing = None


@dataclass(frozen=True, kw_only=True)
class Exit(Directive):
    subject: str
    via: str | None = None


@dataclass(frozen=True, kw_only=True)
class Move(Directive):
    subject: str
    pos: Location
    facing: Facing = None
    by: str | None = None
    until_arrive: bool = False


@dataclass(frozen=True, kw_only=True)
class Via(Directive):
    subject: str
    pos: Location


@dataclass(frozen=True, kw_only=True)
class Arrive(Directive):
    subject: str
    facing: Facing = None


@dataclass(frozen=True, kw_only=True)
class Set(Directive):
    subject: str
    pos: Location | None = None
    on: str | None = None
    with_: str | None = None
    facing: Facing = None
    by: str | None = None


@dataclass(frozen=True, kw_only=True)
class Strike(Directive):
    subject: str
    by: str | None = None


@dataclass(frozen=True, kw_only=True)
class Preset(Directive):
    subject: str
    pos: Location | None = None
    on: str | None = None
    with_: str | None = None
    facing: Facing = None


type AnyDirective = (
    Stage | Entity | Enter | Exit | Move | Via | Arrive | Set | Strike | Preset
)

KEYS: dict[str, tuple[str, ...]] = {
    "STAGE": ("type", "units", "width", "depth", "radius", "front"),
    "ENTITY": ("type", "pos", "on", "with", "facing", "cue", "label"),
    "ENTER": ("from", "pos", "facing"),
    "EXIT": ("via",),
    "MOVE": ("pos", "facing", "by", "until"),
    "VIA": ("pos",),
    "ARRIVE": ("facing",),
    "SET": ("pos", "on", "with", "facing", "by"),
    "STRIKE": ("by",),
    "PRESET": ("pos", "on", "with", "facing"),
}

# Keys allowed on ENTITY per entity type.
ENTITY_KEYS: dict[str, tuple[str, ...]] = {
    "cast": ("type", "pos", "facing", "cue", "label"),
    "prop": ("type", "pos", "on", "with", "label"),
    "mark": ("type", "pos", "label"),
    "entrance": ("type", "pos", "label"),
}

LOCATION_KEYS = ("pos", "on", "with")


class _Values:
    """A directive's attribute values, parsed for their keys (E17)."""

    def __init__(self, attributes: tuple[tuple[str, str], ...]) -> None:
        self.raw = dict(attributes)

    def __contains__(self, key: str) -> bool:
        return key in self.raw

    def _bad(self, key: str, why: str = "is not a valid value") -> Fault:
        return Fault("E17", f"{key}={self.raw[key]} {why}")

    def text(self, key: str) -> str | None:
        return self.raw.get(key)

    def ident(self, key: str) -> str | None:
        value = self.raw.get(key)
        if value is not None and not is_id(value):
            raise self._bad(key, "is not a valid id")
        return value

    def dimension(self, key: str) -> float | None:
        value = self.raw.get(key)
        if value is None:
            return None
        number = parse_number(value)
        if number is None:
            raise self._bad(key, "is not a number")
        if number <= 0:
            raise self._bad(key, "must be greater than zero")
        return number

    def location(self, key: str) -> Location | None:
        value = self.raw.get(key)
        if value is None:
            return None
        location = parse_location(value)
        if location is None:
            raise self._bad(key, "is not a coordinate or id")
        return location

    def facing(self) -> Facing:
        value = self.raw.get("facing")
        if value is None:
            return None
        direction = parse_direction(value)
        if direction is None:
            raise self._bad("facing", "is not a bearing, coordinate or id")
        return direction

    def check_all(self) -> None:
        """Checks every value's type, in source order."""
        for key in self.raw:
            if key in ("width", "depth", "radius"):
                self.dimension(key)
            elif key == "pos":
                self.location(key)
            elif key == "facing":
                self.facing()
            elif key in ("on", "with", "from", "via", "by", "front"):
                self.ident(key)
            elif key == "units" and self.raw[key] not in UNITS:
                raise self._bad(key, "is not one of m, cm, ft, in")
            elif key == "until" and self.raw[key] != "arrive":
                raise self._bad(key, "must be arrive")


def validate(
    raw: RawDirective, *, cue: Cue, line: int, subject: str | None
) -> AnyDirective:
    """Validates a tokenised directive into a typed one.

    `subject` is the explicit subject, or the implied one if the raw
    directive has none. Raises `Fault` on the first failure.
    """
    keyword = raw.keyword
    allowed = KEYS[keyword]
    for key, _ in raw.attributes:
        if key not in allowed:
            raise Fault("E16", f"{key} is not an attribute of {keyword}")
    seen: set[str] = set()
    for key, _ in raw.attributes:
        if key in seen:
            raise Fault("E18", f"{key} is given twice")
        seen.add(key)
    values = _Values(raw.attributes)
    values.check_all()

    common = Directive(cue=cue, line=line, text=raw.text)
    if keyword == "STAGE":
        if raw.subject is not None:
            raise Fault("E16", f"STAGE takes no subject, got {raw.subject!r}")
        return _stage(values, common)

    if subject is None:
        raise Fault("E08", f"{keyword} has no subject")
    if not is_id(subject):
        raise Fault("E17", f"{subject!r} is not a valid id")
    common = replace(common, implied_subject=raw.subject is None)

    if keyword in ("ENTITY", "SET", "PRESET"):
        given = [key for key in LOCATION_KEYS if key in values]
        if len(given) > 1:
            raise Fault("E09", f"{' and '.join(given)} given together")

    def base() -> dict[str, Any]:
        return {
            "cue": common.cue,
            "line": common.line,
            "text": common.text,
            "implied_subject": common.implied_subject,
            "subject": subject,
        }

    match keyword:
        case "ENTITY":
            return _entity(values, base())
        case "ENTER":
            return Enter(
                **base(),
                from_=values.ident("from"),
                pos=values.location("pos"),
                facing=values.facing(),
            )
        case "EXIT":
            return Exit(**base(), via=values.ident("via"))
        case "MOVE":
            pos = values.location("pos")
            if pos is None:
                raise Fault("E08", "MOVE needs pos")
            return Move(
                **base(),
                pos=pos,
                facing=values.facing(),
                by=values.ident("by"),
                until_arrive="until" in values,
            )
        case "VIA":
            pos = values.location("pos")
            if pos is None:
                raise Fault("E08", "VIA needs pos")
            return Via(**base(), pos=pos)
        case "ARRIVE":
            return Arrive(**base(), facing=values.facing())
        case "SET":
            return Set(
                **base(),
                pos=values.location("pos"),
                on=values.ident("on"),
                with_=values.ident("with"),
                facing=values.facing(),
                by=values.ident("by"),
            )
        case "STRIKE":
            return Strike(**base(), by=values.ident("by"))
        case _:
            assert keyword == "PRESET"
            return Preset(
                **base(),
                pos=values.location("pos"),
                on=values.ident("on"),
                with_=values.ident("with"),
                facing=values.facing(),
            )


def _stage(values: _Values, common: Directive) -> Stage:
    stage_type = values.text("type")
    if stage_type is None:
        raise Fault("E08", "STAGE needs type")
    if stage_type not in STAGE_TYPES:
        raise Fault("E17", f"type={stage_type} is not a stage type")
    width, depth = values.dimension("width"), values.dimension("depth")
    radius = values.dimension("radius")
    if radius is not None:
        if stage_type != "round":
            raise Fault("E16", f"radius is not an attribute of a {stage_type} stage")
        if width is not None or depth is not None:
            raise Fault("E16", "a round stage takes radius, or width and depth")
    else:
        for key, value in (("width", width), ("depth", depth)):
            if value is None:
                needed = "radius, or width and depth" if stage_type == "round" else key
                raise Fault("E08", f"a {stage_type} stage needs {needed}")
    return Stage(
        cue=common.cue,
        line=common.line,
        text=common.text,
        type=stage_type,
        units=values.text("units") or "m",
        width=width,
        depth=depth,
        radius=radius,
        front=values.ident("front"),
    )


def _entity(values: _Values, base: dict[str, Any]) -> Entity:
    entity_type = values.text("type")
    if entity_type is None:
        raise Fault("E08", "ENTITY needs type")
    if entity_type not in ENTITY_KEYS:
        raise Fault("E17", f"type={entity_type} is not an entity type")
    for key in values.raw:
        if key not in ENTITY_KEYS[entity_type]:
            raise Fault("E16", f"{key} is not an attribute of a {entity_type}")
    pos = values.location("pos")
    if entity_type in ("mark", "entrance"):
        if pos is None:
            raise Fault("E08", f"a {entity_type} needs pos")
        if not isinstance(pos, Point):
            raise Fault("E17", f"a {entity_type}'s pos must be a coordinate")
    return Entity(
        **base,
        type=entity_type,
        pos=pos,
        on=values.ident("on"),
        with_=values.ident("with"),
        facing=values.facing(),
        character_cue=values.text("cue"),
        label=values.text("label"),
    )
