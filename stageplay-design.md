# Stage Play Output — Design Decisions

Agreed design for adding stage-play output to Screenplain. Settings for
alternatives noted as "later" are deferred, not rejected.

## Detection & parsing

1. **Activation** — stage-play mode is enabled by a title-page key
   `Format: Stage Play` or `Format: Stageplay` (case-insensitive), or forced
   with the `--stageplay` CLI flag. Mode is a property of the input, so
   `-f pdf` / `-f html` produce stage-play layout automatically.
2. **Front matter boundary** — in stage-play mode, the *first* `===` ends the
   front matter; any later `===` is an ordinary page break. If there is no
   `===`, there is no front matter. Screenplay mode is unchanged.
3. **Architecture** — the Fountain line parser is unchanged. A post-parse
   transform `to_stageplay(Screenplay) -> StagePlay` restructures the
   paragraphs. New types: `StagePlay`, `FrontMatterSection`, `CastList`,
   `CastMember`, `Act`, `Scene`. Existing `Dialog` and `Action` are reused.
4. **Front matter sections** — a section titled `Dramatis Personae`, `Cast`,
   `Characters` or `Cast of Characters` (case-insensitive) becomes a
   structured `CastList`:
   - a `Dialog` paragraph (e.g. `@Mary` / `A teacher.`) → name + description
   - a single-line `Action` paragraph → name with no description
   - `##` inside the cast list → group heading (e.g. `## The Royal Court`)

   All other sections (Notes, Time, Setting, unknown headings, …) render
   generically as heading + prose. *Later: special styling for more sections.*
5. **Body structure** — `#` = Act, `##` = Scene, `###`+ rendered like Scenes.
   Headings are printed verbatim; no automatic numbering.
   *Later: optional auto scene numbering setting.*
6. **Screenplay-only elements in the body**

   | Element | Handling |
   |---|---|
   | Slugline (`INT. …`, `.FORCED`) | Treated as a Scene heading, verbatim |
   | Transition (`> CURTAIN.`) | Kept, right-aligned |
   | Centered action (`> THE END <`) | Kept, centered |
   | Dual dialogue | Kept, side by side |
   | Scene numbers (`#12#`) | Dropped |
   | Notes / boneyard | Already stripped by the parser |

7. **Inline character names** — `@Name` inside a stage direction marks a
   character name. The name is the longest match against known names (cast
   list + dialogue cues), falling back to the single word after `@`. The `@`
   is not printed. Names without `@` are never altered, regardless of case
   (ALL CAPS is not a stage-play convention we rely on).

   Gotcha: a direction paragraph of two or more lines whose first line starts
   with `@` parses as dialogue. Writers must use Fountain's forced-action
   prefix: `!@Mary enters.` This is documented in the spec.

## Output

8. **Formats** — PDF and HTML. FDX exits with a clear error in stage-play
   mode ("stage play output not yet supported for fdx").
9. **House style** — published acting edition (Samuel French / Faber style).
   *Later: US manuscript style as a `Style:` setting.*
   - Page size: A4 only. *Later: page size setting.*
   - Font: EB Garamond 12pt, bundled (OFL) like Courier Prime;
     `--standard-font` falls back to built-in Times.
   - Margins: ~25mm, slightly wider left/right to keep line length readable.
   - Small caps are simulated (lowercase drawn as uppercase at ~80% size),
     as reportlab has no OpenType feature support.
10. **Dialogue**
    ```
    MARY. Did you hear that?
    HAMLET (aside). He knows.
    JOHN. I — (He stops.) I don't know what you mean.
         It was nothing.
    ```
    - Cue: name in small caps + period, speech runs in on the same line.
    - Extension (`@Hamlet (aside)`) in italic between name and period.
    - Parentheticals inline, italic, within the speech paragraph.
    - Continuation lines use a ~1.5em hanging indent.
    - ½ line of space between speeches.
11. **Stage directions** — italic, indented ~2em, no added parentheses,
    ½ line of space around. Inline `@` names in roman small caps.
12. **Page layout**
    - Title page (existing keys: Title, Credit, Author, Draft date, Contact),
      restyled in the serif font, centered.
    - Front matter sections flow together after the title page (not one per
      page). Headings centered small caps. Cast list as
      `NAME, description` (name small caps, description italic). Group
      headings italic, centered.
    - The play body always starts on a new page.
    - Acts: uppercased, centered, each on a new page.
    - Scene headings: centered small caps, body size, no page break, 2 lines
      of space above and 1 below.
    - Opening scene descriptions get no special styling (ordinary
      directions). *Later: optional distinct style.*
    - Page numbers top right, starting from the play body; front matter is
      unnumbered.
13. **HTML**
    - Separate `StagePlayFormatter` in `html.py`; screenplay HTML output stays
      byte-identical.
    - New `stageplay.css` beside `default.css`: serif stack
      (`"EB Garamond", Garamond, Georgia, serif`), `font-variant: small-caps`,
      run-in cues, italic directions. Font is not embedded.
    - Semantic classes: `.stageplay`, `.front-matter`, `.cast-list`,
      `.cast-member`, `.act`, `.scene`, `.direction`, `.speech`, `.cue`,
      `.extension`, `.character`.
    - `--bare` and `--css` keep working; `--css` replaces `stageplay.css` for
      stage-play input.

## Tests & docs

14. - `tests/stageplay_test.py`: unit tests for `to_stageplay` — first vs later
      `===`, cast list extraction (Dialog / Action / `##` groups), Acts and
      Scenes, slugline → Scene, inline `@` matching (longest match, fallback),
      `Format:` detection, no `===` → no front matter.
    - `tests/files/stageplay.fountain` + expected `stageplay.html` in
      `files_test.py`, plus tests for the FDX error and `--stageplay`.
    - `tests/files/stageplay.pdf` reference for the visual diff test,
      generated once and reviewed by eye before committing.
    - Rewrite `stageplaywrite.spec.md` as a clean spec; add a "Stage plays"
      section to `README.md`.
    - Existing test suite, `ruff` and `ty` must stay green.

## Notes

- Fetching the EB Garamond TTFs + licence from the official source is a
  network download; confirm before doing it.
