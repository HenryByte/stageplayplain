"""Step groups and picture changes: the moments of a scene's blocking that
earn a margin plan.

A step group is consecutive steps with nothing of the script between
their notes. It earns a plan when any of its steps is a picture change:
some cast member's or prop's place on the floor, or whether it is onstage,
changes. Steps at the top of a scene never do: the scene plan shows them.
"""

from __future__ import annotations

from dataclasses import dataclass

from screenplain.fse.blocking import Blocking, Scene, Step
from screenplain.fse.model import (
    At,
    Cue,
    Moving,
    OpenMove,
    Point,
    State,
    carrier,
)
from screenplain.types import (
    SCREENPLAY_TYPES,
    Action,
    Dialog,
    DualDialog,
    Note,
)

# What an entity looks like on a plan: offstage, or onstage with whether it
# is carried and where its carrier chain meets the floor.
type Picture = tuple[bool] | tuple[bool, bool, Point | OpenMove]


def picture(blocking: Blocking, state: State, entity: str) -> Picture:
    """How an entity shows on a plan. A change of carrier alone, such as a
    hand-over in place, leaves it unchanged; being picked up or put down
    does not.
    """
    if not state.onstage(entity):
        return (False,)
    attached = carrier(state.whereabouts(entity)) is not None
    seen: set[str] = set()
    current = entity
    while current not in seen:
        seen.add(current)
        whereabouts = state.whereabouts(current)
        if isinstance(whereabouts, At):
            return (True, attached, blocking.resolve(whereabouts.location))
        if isinstance(whereabouts, Moving):
            return (True, attached, whereabouts.move)
        parent = carrier(whereabouts)
        assert parent is not None
        current = parent
    raise AssertionError(f"{entity} is onstage through a cycle")


def picture_changes(blocking: Blocking, before: State, after: State) -> set[str]:
    """The cast members and props whose picture differs between states."""
    return {
        entity
        for entity in after
        if picture(blocking, before, entity) != picture(blocking, after, entity)
    }


@dataclass(frozen=True)
class StepGroup:
    """Consecutive steps of a scene with nothing of the script between
    their notes. `before` is the state before the first step, and
    `previous` the cue of the step that produced it, if any.
    """

    scene: Scene
    steps: tuple[Step, ...]
    before: State
    previous: Cue | None

    @property
    def after(self) -> State:
        return self.steps[-1].state

    @property
    def cue(self) -> Cue:
        """Where the group is cued: its first note."""
        return self.steps[0].cue

    @property
    def last_cue(self) -> Cue:
        return self.steps[-1].cue


def top_of_scene(scene: Scene) -> int:
    """How many of a scene's steps are its top-of-scene `PRESET` and
    `STRIKE all` notes.
    """
    for index, step in enumerate(scene.steps):
        if step.state is scene.preset:
            return index + 1
    return 0


def step_groups(blocking: Blocking) -> list[StepGroup]:
    """Every scene's step groups that hold a picture change, in script
    order. Steps before the first scene are in no group.
    """
    steps = blocking.timeline.steps
    position = {id(step): index for index, step in enumerate(steps)}
    paragraphs = blocking.screenplay.paragraphs
    groups: list[StepGroup] = []
    for scene in blocking.scenes:
        runs: list[list[Step]] = []
        for step in scene.steps[top_of_scene(scene) :]:
            if runs and not has_text_between(paragraphs, runs[-1][-1].cue, step.cue):
                runs[-1].append(step)
            else:
                runs.append([step])
        for run in runs:
            index = position[id(run[0])]
            previous = steps[index - 1] if index else None
            before = previous.state if previous else blocking.timeline.initial
            changed = any(
                picture_changes(
                    blocking,
                    steps[position[id(step)] - 1].state
                    if position[id(step)]
                    else blocking.timeline.initial,
                    step.state,
                )
                for step in run
            )
            if changed:
                groups.append(
                    StepGroup(
                        scene,
                        tuple(run),
                        before,
                        previous.cue if previous else None,
                    )
                )
    return groups


def _chunks(para: SCREENPLAY_TYPES) -> list[tuple[int, int, str]]:
    """A paragraph's text as (side, part, text) in script order. A
    character cue is part -1 of its speech. Elements that cannot hold a
    cue count as one piece of text.
    """
    if isinstance(para, Note):
        return []
    if isinstance(para, Action) and not para.centered:
        return [(0, part, str(line)) for part, line in enumerate(para.lines)]
    if isinstance(para, Dialog):
        return _speech_chunks(para, 0)
    if isinstance(para, DualDialog):
        return _speech_chunks(para.left, 0) + _speech_chunks(para.right, 1)
    return [(0, -1, type(para).__name__)]


def _speech_chunks(dialog: Dialog, side: int) -> list[tuple[int, int, str]]:
    return [(side, -1, str(dialog.character))] + [
        (side, part, str(text)) for part, (_, text) in enumerate(dialog.blocks)
    ]


def has_text_between(paragraphs: list[SCREENPLAY_TYPES], a: Cue, b: Cue) -> bool:
    """Whether anything of the script lies between two cues, `a` first:
    a word, or any other element.
    """
    for index in range(a.paragraph, b.paragraph + 1):
        for side, part, text in _chunks(paragraphs[index]):
            where = (index, side, part)
            start, end = 0, len(text)
            if a.part >= 0:
                here = (a.paragraph, a.side, a.part)
                if where < here:
                    continue
                if where == here:
                    start = a.offset
            if b.part >= 0:
                there = (b.paragraph, b.side, b.part)
                if where > there:
                    continue
                if where == there:
                    end = b.offset
            elif index == b.paragraph:
                continue
            if text[start:end].strip():
                return True
    return False
