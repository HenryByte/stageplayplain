"""The Fountain Stage Extension (FSE): stage blocking carried in notes.

`process(screenplay)` reads a parsed script's FSE notes and returns its
`Blocking`, or raises `FseError` on the first error.
"""

from screenplain.fse.blocking import Blocking, Change, Scene, Step, Timeline
from screenplain.fse.processor import process
from screenplain.fse.reports import FseError, Report, Severity
from screenplain.fse.script import has_fse_notes

__all__ = [
    "Blocking",
    "Change",
    "FseError",
    "Report",
    "Scene",
    "Severity",
    "Step",
    "Timeline",
    "has_fse_notes",
    "process",
]
