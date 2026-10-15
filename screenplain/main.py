#!/usr/bin/env python

# Copyright (c) 2011 Martin Vilcans
# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php

import argparse
import codecs
import sys

from screenplain import fse
from screenplain.parsers import fountain
from screenplain.stageplay import is_stageplay, to_stageplay
from screenplain.types import Screenplay, StagePlay

output_formats = ("fdx", "html", "pdf")

description = """Convert text file to viewable screenplay.

If a file name parameter is missing or a dash (-), input will be read
from standard input and output will be written to standard output.

Screenplain will try to auto-detect the output format if
an output-file is given. Otherwise use the --format option."""


def invalid_format(parser: argparse.ArgumentParser, message: str) -> None:
    formats = " ".join(output_formats)
    parser.error(
        f"{message}\nUse --format with one of the following formats: {formats}"
    )


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input_file", nargs="?", help="Input screenplay file (default: stdin)"
    )
    parser.add_argument("output_file", nargs="?", help="Output file (default: stdout)")
    parser.add_argument(
        "-f",
        "--format",
        dest="output_format",
        metavar="FORMAT",
        help=(
            "Set what kind of file to create. FORMAT can be one of "
            f"{', '.join(output_formats)}"
        ),
    )
    parser.add_argument(
        "--bare",
        action="store_true",
        help=(
            "For HTML output, only output the actual screenplay, "
            "not a complete HTML document."
        ),
    )
    parser.add_argument(
        "--css",
        metavar="FILE",
        help=(
            "For HTML output, inline the given CSS file in the HTML document "
            "instead of the default."
        ),
    )
    parser.add_argument(
        "--stageplay",
        action="store_true",
        help=(
            "Format the input as a stage play, even if its title page "
            "has no 'Format: Stage Play' key."
        ),
    )
    parser.add_argument(
        "--strong",
        action="store_true",
        help=("For PDF output, scene headings will appear Bold and Underlined."),
    )
    parser.add_argument(
        "--standard-font",
        action="store_true",
        help=(
            "For PDF output, use the standard Courier font instead of Courier Prime "
            "(Times instead of EB Garamond for stage plays)."
        ),
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Text encoding of the input file. "
        "Should be one of Python's built-in encodings.",
    )
    parser.add_argument(
        "--encoding-errors",
        default="strict",
        choices=["strict", "ignore", "replace", "backslashreplace", "surrogateescape"],
        help="How to handle invalid character codes in the input file",
    )
    parser.add_argument(
        "--no-warnings",
        action="store_true",
        help="Don't print warnings about FSE stage blocking. Errors still print.",
    )
    args = parser.parse_args(argv)

    # Handle dash as stdin/stdout
    if not args.input_file or args.input_file == "-":
        input_file = None
    else:
        input_file = args.input_file

    if not args.output_file or args.output_file == "-":
        output_file = None
    else:
        output_file = args.output_file

    try:
        codecs.lookup(args.encoding)
    except LookupError:
        parser.error(f"Unknown encoding: {args.encoding}")

    out_format = args.output_format
    if out_format is None and output_file:
        if output_file.endswith(".fdx"):
            out_format = "fdx"
        elif output_file.endswith(".html"):
            out_format = "html"
        elif output_file.endswith(".pdf"):
            out_format = "pdf"
        else:
            invalid_format(
                parser, f"Could not detect output format from file name {output_file}"
            )

    if out_format not in output_formats:
        invalid_format(parser, f'Unsupported output format: "{out_format}".')

    if input_file:
        input_stream = open(
            input_file, encoding=args.encoding, errors=args.encoding_errors
        )
    else:
        input_stream = codecs.getreader(args.encoding)(sys.stdin.buffer)
        input_stream.errors = args.encoding_errors
    screenplay = fountain.parse(input_stream)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
    if input_file:
        input_stream.close()
    as_stageplay = args.stageplay or is_stageplay(screenplay)
    if as_stageplay and out_format == "fdx":
        parser.error("Stage play output is not yet supported for fdx")

    # FSE runs before the output is opened, so an error leaves it untouched.
    # The Blocking is not used yet: every output is Script mode.
    if fse.has_fse_notes(screenplay):
        process_fse(screenplay, input_file or "<stdin>", args.no_warnings)

    stageplay = to_stageplay(screenplay) if as_stageplay else None

    if out_format == "pdf":
        output_encoding = None
    else:
        output_encoding = "utf-8"

    if output_file:
        if output_encoding:
            output = open(output_file, mode="w", encoding=output_encoding)
        else:
            output = open(output_file, "wb")
    else:
        if output_encoding:
            output = codecs.getwriter(output_encoding)(sys.stdout.buffer)
        else:
            output = sys.stdout.buffer

    try:
        if stageplay:
            convert_stageplay(stageplay, out_format, output, args)
        elif out_format == "fdx":
            from screenplain.export.fdx import to_fdx

            to_fdx(screenplay, output)  # ty: ignore[invalid-argument-type]
        elif out_format == "html":
            from screenplain.export.html import convert

            convert(screenplay, output, css_file=args.css, bare=args.bare)  # ty: ignore[invalid-argument-type]
        elif out_format == "pdf":
            from screenplain.export import pdf

            font_settings = None
            if args.standard_font:
                font_settings = pdf.get_standard_font_settings()
            settings = pdf.Settings(
                font_settings=font_settings, strong_slugs=args.strong
            )
            pdf.to_pdf(screenplay, output, settings=settings)  # ty: ignore[invalid-argument-type]
    finally:
        if output_file:
            output.close()


def process_fse(screenplay: Screenplay, path: str, no_warnings: bool) -> None:
    """Processes a script's FSE notes, printing reports to stderr.

    Raises SystemExit(1) on an error.
    """
    try:
        warnings = fse.process(screenplay).reports
        error = None
    except fse.FseError as exception:
        warnings, error = exception.warnings, exception.report
    if not no_warnings:
        for report in warnings:
            print(report.format(path), file=sys.stderr)
    if error:
        print(error.format(path), file=sys.stderr)
        print("screenplain: no output written (1 error)", file=sys.stderr)
        raise SystemExit(1)


def convert_stageplay(
    play: StagePlay, out_format: str, output: object, args: argparse.Namespace
) -> None:
    if out_format == "html":
        from screenplain.export.html import convert_stageplay

        convert_stageplay(play, output, css_file=args.css, bare=args.bare)  # ty: ignore[invalid-argument-type]
    elif out_format == "pdf":
        from screenplain.export import stageplay_pdf

        font_settings = None
        if args.standard_font:
            font_settings = stageplay_pdf.get_standard_font_settings()
        settings = stageplay_pdf.StagePlaySettings(font_settings=font_settings)
        stageplay_pdf.to_pdf(play, output, settings=settings)  # ty: ignore[invalid-argument-type]


def cli() -> None:
    """setup.py entry point for console scripts."""
    main(sys.argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:])
