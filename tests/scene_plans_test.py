"""Scene plans in real `--blocking` output: which scenes get one, the key,
and where the block sits in both PDF layouts.
"""

import io
from pathlib import Path

import pytest
from reportlab.platypus import Flowable, Paragraph

from screenplain import fse
from screenplain.export import pdf, plans, stageplay_pdf
from screenplain.export.plans import ScenePlan
from screenplain.parsers import fountain
from screenplain.stageplay import to_stageplay
from screenplain.types import Screenplay, Section, Slug
from tests.recording_canvas import Recorder

HERE = Path(__file__).parent / "blocking"


def parse(source: str) -> Screenplay:
    return fountain.parse(io.StringIO(source))


def load(name: str) -> tuple[Screenplay, fse.Blocking]:
    screenplay = parse((HERE / name).read_text(encoding="utf-8"))
    return screenplay, fse.process(screenplay)


def heading(blocking: fse.Blocking, index: int) -> str:
    para = blocking.screenplay.paragraphs[index]
    assert isinstance(para, (Slug, Section))
    return str(para.line if isinstance(para, Slug) else para.text)


# Which scenes


def test_scenes_with_content_get_a_plan() -> None:
    _, blocking = load("acts.fountain")
    assert ["Act One", "Scene 1", "Act Two", "Scene 2", "Scene 3"] == [
        heading(blocking, blocking.screenplay.paragraphs.index(scene.boundary))
        for scene in blocking.scenes
    ]
    planned = plans.scene_plans(blocking)
    # Act One runs straight into Scene 1; Scene 2 holds only its PRESET.
    assert ["Scene 1", "Act Two", "Scene 3"] == [
        heading(blocking, index) for index in planned
    ]


def test_scripts_with_only_scene_headings() -> None:
    _, blocking = load("../fse/hamlet.fountain")
    planned = plans.scene_plans(blocking)
    assert ["ACT V, SCENE I - A CHURCHYARD"] == [
        heading(blocking, index) for index in planned
    ]
    (scene,) = planned.values()
    assert scene is blocking.scenes[0]


def test_no_scenes_no_plans() -> None:
    blocking = fse.process(
        parse(
            "[[FSE STAGE type=proscenium width=10 depth=8]]\n"
            "[[FSE ENTITY hamlet type=cast pos=0,0]]\n\nHAMLET\nTo be.\n"
        )
    )
    assert {} == plans.scene_plans(blocking)


# The key


def test_key_lists_cast_then_props_appearing_anywhere_in_the_scene() -> None:
    _, blocking = load("acts.fountain")
    key = plans.scene_key(blocking, blocking.scenes[1])
    assert ["mary", "arthur"] == [cast.id for cast in key.cast]
    # The letter never appears in Scene 1.
    assert ["sofa"] == [prop.id for prop in key.props]
    # Arthur comes on later in the scene.
    assert {"arthur"} == key.off
    assert {"sofa": 1} == key.numbers


def test_prop_numbers_are_fixed_per_scene() -> None:
    _, blocking = load("ballroom.fountain")
    key = plans.scene_key(blocking, blocking.scenes[0])
    assert 1 == key.numbers["piano"]
    # The handbag is off at the top; it keeps its number.
    assert 8 == key.numbers["handbag"]
    assert "handbag" in key.off
    assert "lady-b" in key.off
    entries = plans.key_entries(key)
    assert ("LB", "Lady Bracknell", True) == (
        entries[0].tag,
        entries[0].name,
        entries[0].grey,
    )
    assert ("8", "Black leather handbag", True) == (
        entries[len(key.cast) + 7].tag,
        entries[len(key.cast) + 7].name,
        entries[len(key.cast) + 7].grey,
    )


def test_long_entries_wrap_with_a_hanging_indent() -> None:
    entry = plans.KeyEntry("6", "Plate of cucumber sandwiches, thinly cut", False)
    first, *rest = plans.entry_lines(entry, plans.KEY_COLUMN_WIDTH)
    assert "6" == first.tag
    assert rest
    assert all("" == line.tag and line.indent == first.indent > 0 for line in rest)
    assert entry.name == " ".join(line.text for line in [first, *rest])


def test_key_fills_down_then_across_without_splitting_an_entry() -> None:
    one = [plans.KeyLine("1", "a", 0, False)]
    two = [plans.KeyLine("2", "b", 0, False), plans.KeyLine("", "c", 0, False)]
    three = [plans.KeyLine("3", "d", 0, False)]

    def tags(columns: list[list[plans.KeyLine]] | None) -> list[list[str]] | None:
        if columns is None:
            return None
        return [[line.tag for line in column] for column in columns]

    # The two-line entry does not fit under the first, so it starts column 2.
    assert [["1"], ["2", ""], ["3"]] == tags(
        plans.layout_columns([one, two, three], columns=3, rows=2)
    )
    assert None is plans.layout_columns([one, two, three], columns=2, rows=2)
    assert [["1", "2", ""], ["3"]] == tags(
        plans.layout_columns([one, two, three], columns=2, rows=3)
    )


# The block


def test_block_is_as_tall_as_the_drawing_when_the_key_fits() -> None:
    _, blocking = load("acts.fountain")
    block = ScenePlan(blocking, blocking.scenes[1])
    settings = stageplay_pdf.StagePlaySettings()
    width, height = block.wrap(settings.frame_width, 1000)
    assert width == settings.frame_width
    assert height == plans.SCENE_PLAN_HEIGHT
    assert 1 == len(block.columns)


@pytest.mark.parametrize("layout", ["stageplay", "screenplay"])
def test_key_overflowing_every_column_makes_the_block_taller(layout: str) -> None:
    _, blocking = load("ballroom.fountain")
    if layout == "stageplay":
        frame_width = stageplay_pdf.StagePlaySettings().frame_width
    else:
        frame_width = pdf.Settings().frame_width
    block = ScenePlan(blocking, blocking.scenes[0])
    _, height = block.wrap(frame_width, 1000)
    rows = max(len(column) for column in block.columns)
    assert 3 == len(block.columns)
    assert height == rows * plans.KEY_LEADING > plans.SCENE_PLAN_HEIGHT


def test_drawing_sits_at_the_right_edge_and_the_key_to_its_left() -> None:
    _, blocking = load("ballroom.fountain")
    block = ScenePlan(blocking, blocking.scenes[0])
    width, height = block.wrap(400, 1000)
    canvas = Recorder()
    block.drawOn(canvas, 0, 0)
    frame = canvas.shapes[0]
    assert (
        width - plans.SCENE_PLAN_WIDTH,
        height - plans.SCENE_PLAN_HEIGHT,
        plans.SCENE_PLAN_WIDTH,
        plans.SCENE_PLAN_HEIGHT,
    ) == pytest.approx(frame.args)
    key = [s for s in canvas.shapes if s.font[1] == plans.KEY_FONT_SIZE]
    assert min(s.args[0] for s in key) == 0
    assert max(s.args[0] for s in key) < width - plans.SCENE_PLAN_WIDTH - plans.KEY_GAP
    greyed = {s.text for s in key if s.fill == plans.KEY_GREY}
    assert {"LB", "Lady Bracknell", "8", "Black leather handbag"} == greyed


def test_block_never_splits() -> None:
    _, blocking = load("ballroom.fountain")
    block = ScenePlan(blocking, blocking.scenes[0])
    block.wrap(400, 1000)
    assert [] == block.split(400, 20)
    assert block.getKeepWithNext()


# In both layouts


Placed = list[tuple[int, Flowable]]


def is_content(flowable: Flowable) -> bool:
    """Leaves out the bookkeeping flowables that keeping together adds."""
    return isinstance(flowable, (Paragraph, pdf.SlugWithSceneNumbers, ScenePlan))


def place_stageplay(
    screenplay: Screenplay,
    blocking: fse.Blocking | None,
    monkeypatch: pytest.MonkeyPatch,
) -> Placed:
    placed: Placed = []

    def after(doc: stageplay_pdf.StagePlayDocTemplate, flowable: Flowable) -> None:
        if is_content(flowable):
            placed.append((doc.page, flowable))

    monkeypatch.setattr(
        stageplay_pdf.StagePlayDocTemplate, "afterFlowable", after, raising=False
    )
    stageplay_pdf.to_pdf(to_stageplay(screenplay), io.BytesIO(), blocking=blocking)  # ty: ignore[invalid-argument-type]
    return placed


def place_screenplay(
    screenplay: Screenplay,
    blocking: fse.Blocking | None,
    monkeypatch: pytest.MonkeyPatch,
) -> Placed:
    placed: Placed = []

    def after(doc: pdf.DocTemplate, flowable: Flowable) -> None:
        if is_content(flowable):
            placed.append((doc.page, flowable))

    monkeypatch.setattr(pdf.DocTemplate, "afterFlowable", after, raising=False)
    pdf.to_pdf(screenplay, io.BytesIO(), blocking=blocking)  # ty: ignore[invalid-argument-type]
    return placed


def text(flowable: Flowable) -> str:
    if isinstance(flowable, pdf.SlugWithSceneNumbers):
        flowable = flowable.slug_paragraph
    if isinstance(flowable, Paragraph):
        return flowable.getPlainText()
    return type(flowable).__name__


def around_plans(placed: Placed) -> list[tuple[str, str, str]]:
    """For each scene plan: the text before it, and after it."""
    return [
        (text(placed[n - 1][1]), "ScenePlan", text(placed[n + 1][1]))
        for n, (_, flowable) in enumerate(placed)
        if isinstance(flowable, ScenePlan)
    ]


def test_stage_play_plans_sit_under_their_headings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    screenplay, blocking = load("acts.fountain")
    placed = place_stageplay(screenplay, blocking, monkeypatch)
    # Character names are set in small caps.
    assert [
        ("SCENE 1", "ScenePlan", "MARY sits on the sofa."),
        ("ACT TWO", "ScenePlan", "The curtain rises on an empty room."),
        ("SCENE 3", "ScenePlan", "MARY. A letter?"),
    ] == around_plans(placed)


def test_screenplay_plans_sit_under_their_headings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    screenplay, blocking = load("../fse/hamlet.fountain")
    placed = place_screenplay(screenplay, blocking, monkeypatch)
    assert [
        (
            "ACT V, SCENE I - A CHURCHYARD",
            "ScenePlan",
            "The FIRST GRAVEDIGGER digs, singing.",
        )
    ] == around_plans(placed)


@pytest.mark.parametrize("layout", ["stageplay", "screenplay"])
def test_without_blocking_there_are_no_plans(
    layout: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    screenplay, _ = load("acts.fountain")
    place = place_stageplay if layout == "stageplay" else place_screenplay
    assert [] == around_plans(place(screenplay, None, monkeypatch))


def at_page_foot(lines: int, slug: bool) -> str:
    """A script whose second scene heading falls lower down the page as
    `lines` grows.
    """
    heading = "INT. LIBRARY" if slug else "## Scene 2"
    return (
        ("" if slug else "Title: Foot\nFormat: Stage Play\n\n===\n\n")
        + "[[FSE STAGE type=proscenium width=10 depth=8]]\n"
        + "[[FSE ENTITY hamlet type=cast]]\n\n"
        + ("INT. HALL" if slug else "## Scene 1")
        + "\n\n[[FSE PRESET hamlet pos=0,0]]\n\n"
        + "".join(f"Hamlet waits, {n}.\n\n" for n in range(lines))
        + f"{heading}\n\n[[FSE PRESET hamlet pos=1,1]]\n\nHamlet reads.\n\n"
        + "Hamlet sleeps.\n"
    )


@pytest.mark.parametrize("layout", ["stageplay", "screenplay"])
def test_heading_plan_and_first_element_keep_together_at_a_page_foot(
    layout: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    place = place_stageplay if layout == "stageplay" else place_screenplay
    moved = 0
    for lines in range(10, 40):
        screenplay = parse(at_page_foot(lines, slug=layout == "screenplay"))
        placed = place(screenplay, fse.process(screenplay), monkeypatch)
        *_, n = [n for n, (_, f) in enumerate(placed) if isinstance(f, ScenePlan)]
        heading_page, plan_page, first_page = (placed[i][0] for i in (n - 1, n, n + 1))
        assert heading_page == plan_page == first_page, lines
        if plan_page > placed[n - 2][0]:
            moved += 1
    # Some of those runs put the heading at the foot of the page, and all
    # three moved over together.
    assert moved
