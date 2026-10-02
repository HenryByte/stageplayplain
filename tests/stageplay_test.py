from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from io import StringIO
from typing import override
from unittest import TestCase

from screenplain.main import main
from screenplain.parsers.fountain import parse_lines
from screenplain.richstring import italic, plain
from screenplain.stageplay import (
    is_stageplay,
    split_names,
    strip_continuation,
    to_stageplay,
)
from screenplain.types import (
    Act,
    Action,
    CastGroup,
    CastList,
    CastMember,
    CharacterName,
    Dialog,
    DualDialog,
    FrontMatterSection,
    PageBreak,
    Scene,
    StageDirection,
    StagePlay,
    Transition,
)


def parse(source: str) -> StagePlay:
    return to_stageplay(parse_lines(source.splitlines()))


def direction(text: str) -> StageDirection:
    return StageDirection([[plain(text)]])


class DetectionTests(TestCase):
    def test_format_key(self) -> None:
        self.assertTrue(is_stageplay(parse_lines(["Format: Stage Play", "", "x"])))

    def test_format_key_is_case_insensitive(self) -> None:
        self.assertTrue(is_stageplay(parse_lines(["format: STAGEPLAY", "", "x"])))

    def test_other_format(self) -> None:
        self.assertFalse(is_stageplay(parse_lines(["Format: Screenplay", "", "x"])))

    def test_no_title_page(self) -> None:
        self.assertFalse(is_stageplay(parse_lines(["Lights up."])))


class FrontMatterTests(TestCase):
    def test_no_page_break_means_no_front_matter(self) -> None:
        play = parse("# Notes\n\nLights up.")
        self.assertEqual([], play.front_matter)
        self.assertEqual([Act(plain("Notes")), direction("Lights up.")], play.body)

    def test_first_page_break_ends_front_matter(self) -> None:
        play = parse("# Notes\n\nSome notes.\n\n===\n\nLights up.\n\n===\n\nEnd.")
        self.assertEqual(
            [FrontMatterSection(plain("Notes"), [direction("Some notes.")])],
            play.front_matter,
        )
        self.assertEqual(3, len(play.body))
        self.assertEqual(direction("Lights up."), play.body[0])
        self.assertIsInstance(play.body[1], PageBreak)
        self.assertEqual(direction("End."), play.body[2])

    def test_text_before_first_heading(self) -> None:
        play = parse("A preface.\n\n===\n\nLights up.")
        self.assertEqual(
            [FrontMatterSection(None, [direction("A preface.")])], play.front_matter
        )

    def test_cast_list(self) -> None:
        play = parse(
            "# Dramatis Personae\n\n"
            "@Mary\nA teacher.\n\n"
            "## Others\n\n"
            "John\n\n"
            "===\n\nLights up."
        )
        self.assertEqual(
            [
                CastList(
                    plain("Dramatis Personae"),
                    [
                        CastMember(plain("Mary"), [plain("A teacher.")]),
                        CastGroup(plain("Others")),
                        CastMember(plain("John")),
                    ],
                )
            ],
            play.front_matter,
        )

    def test_cast_list_titles(self) -> None:
        for title in ("Cast", "CHARACTERS", "cast of characters"):
            play = parse(f"# {title}\n\nJohn\n\n===\n\nLights up.")
            self.assertIsInstance(play.front_matter[0], CastList, title)

    def test_multi_line_action_in_cast_list_is_prose(self) -> None:
        play = parse("# Cast\n\nSome roles\nmay be doubled.\n\n===\n\nLights up.")
        cast_list = play.front_matter[0]
        assert isinstance(cast_list, CastList)
        self.assertEqual(
            [StageDirection([[plain("Some roles")], [plain("may be doubled.")]])],
            cast_list.entries,
        )


class BodyTests(TestCase):
    def test_acts_and_scenes(self) -> None:
        play = parse("# Act One\n\n## Scene One\n\n### Deeper")
        self.assertEqual(
            [Act(plain("Act One")), Scene(plain("Scene One")), Scene(plain("Deeper"))],
            play.body,
        )

    def test_slug_becomes_scene_without_number(self) -> None:
        play = parse("INT. HOUSE - DAY #12#")
        self.assertEqual([Scene(plain("INT. HOUSE - DAY"))], play.body)

    def test_other_elements_are_kept(self) -> None:
        play = parse("@Mary\nHello.\n\n> CURTAIN.\n\n> THE END <")
        self.assertIsInstance(play.body[0], Dialog)
        self.assertIsInstance(play.body[1], Transition)
        centered = play.body[2]
        assert isinstance(centered, Action)
        self.assertTrue(centered.centered)

    def test_inline_names_use_cue_and_cast_names(self) -> None:
        play = parse(
            "# Cast\n\nMrs. Danvers\n\n===\n\n"
            "@Mrs. Danvers greets @Mary.\n\n@Mary\nHello."
        )
        self.assertEqual(
            StageDirection(
                [
                    [
                        CharacterName(plain("Mrs. Danvers")),
                        plain(" greets "),
                        CharacterName(plain("Mary")),
                        plain("."),
                    ]
                ]
            ),
            play.body[0],
        )


class ContinuationTests(TestCase):
    def test_markers_are_removed(self) -> None:
        for cue in (
            "MARY (CONT'D)",
            "MARY (cont\u2019d)",
            "MARY (CONTD)",
            "MARY (CONT.)",
            "MARY (Continued)",
        ):
            self.assertEqual("MARY", strip_continuation(cue), cue)

    def test_other_extensions_are_kept(self) -> None:
        self.assertEqual("MARY (V.O.)", strip_continuation("MARY (V.O.) (CONT'D)"))
        self.assertEqual("MARY (aside)", strip_continuation("MARY (CONT'D) (aside)"))
        self.assertEqual("MARY (O.S.)", strip_continuation("MARY (O.S., CONT'D)"))

    def test_similar_words_are_kept(self) -> None:
        self.assertEqual("MARY (content)", strip_continuation("MARY (content)"))

    def test_removed_from_dialogue_in_body(self) -> None:
        play = parse("@Mary (CONT'D)\nHello.\n\n@John (V.O., cont'd)\nHi.")
        mary = play.body[0]
        assert isinstance(mary, Dialog)
        self.assertEqual("Mary", str(mary.character))
        self.assertEqual([(False, plain("Hello."))], mary.blocks)
        john = play.body[1]
        assert isinstance(john, Dialog)
        self.assertEqual("John (V.O.)", str(john.character))

    def test_removed_from_dual_dialogue(self) -> None:
        play = parse("@Mary (CONT'D)\nHello.\n\n@John (CONT'D) ^\nHi.")
        dual = play.body[0]
        assert isinstance(dual, DualDialog)
        self.assertEqual("Mary", str(dual.left.character))
        self.assertEqual("John", str(dual.right.character))


class SplitNamesTests(TestCase):
    def test_longest_known_name_wins(self) -> None:
        self.assertEqual(
            [CharacterName(plain("Mary Ann")), plain(" sits.")],
            split_names(plain("@Mary Ann sits."), ["Mary Ann", "Mary"]),
        )

    def test_known_names_are_case_insensitive(self) -> None:
        self.assertEqual(
            [CharacterName(plain("the stranger")), plain(" waits.")],
            split_names(plain("@the stranger waits."), ["The Stranger"]),
        )

    def test_unknown_name_falls_back_to_one_word(self) -> None:
        self.assertEqual(
            [CharacterName(plain("O'Brien")), plain(" sits.")],
            split_names(plain("@O'Brien sits."), []),
        )

    def test_known_name_must_end_at_word_boundary(self) -> None:
        self.assertEqual(
            [CharacterName(plain("Maryanne")), plain(" sits.")],
            split_names(plain("@Maryanne sits."), ["Mary"]),
        )

    def test_email_address_is_not_a_name(self) -> None:
        self.assertEqual(
            [plain("Mail mary@example.com.")],
            split_names(plain("Mail mary@example.com."), ["Mary"]),
        )

    def test_lone_at_sign_is_kept(self) -> None:
        self.assertEqual(
            [plain("Meet @ noon.")], split_names(plain("Meet @ noon."), [])
        )

    def test_emphasis_is_kept(self) -> None:
        self.assertEqual(
            [italic("Slowly, "), CharacterName(italic("Mary")), italic(" sits.")],
            split_names(italic("Slowly, @Mary sits."), []),
        )


class CommandLineTests(TestCase):
    @override
    def setUp(self) -> None:
        self.dir = tempfile.mkdtemp()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(self.dir)

    def write_source(self, content: str) -> str:
        path = os.path.join(self.dir, "play.fountain")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(content)
        return path

    def convert_to_html(self, *options: str) -> str:
        source = self.write_source("# Act One\n\nLights up.\n")
        target = os.path.join(self.dir, "play.html")
        main([*options, "--bare", source, target])
        with open(target, encoding="utf-8") as stream:
            return stream.read()

    def test_stageplay_flag_forces_stage_play(self) -> None:
        self.assertIn('class="act"', self.convert_to_html("--stageplay"))

    def test_screenplay_by_default(self) -> None:
        self.assertNotIn('class="act"', self.convert_to_html())

    def test_fdx_is_not_supported(self) -> None:
        source = self.write_source("Format: Stage Play\n\nLights up.\n")
        target = os.path.join(self.dir, "play.fdx")
        stderr = StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(stderr):
            main([source, target])
        self.assertIn("not yet supported for fdx", stderr.getvalue())
        self.assertFalse(os.path.exists(target))

    def test_pdf(self) -> None:
        source = self.write_source("Format: Stage Play\n\n@Mary\nHello.\n")
        target = os.path.join(self.dir, "play.pdf")
        main([source, target])
        with open(target, "rb") as stream:
            self.assertTrue(stream.read().startswith(b"%PDF"))

    def test_pdf_with_standard_font(self) -> None:
        source = self.write_source("Format: Stage Play\n\n@Mary\nHello.\n")
        target = os.path.join(self.dir, "play.pdf")
        main(["--standard-font", source, target])
        with open(target, "rb") as stream:
            self.assertTrue(stream.read().startswith(b"%PDF"))
