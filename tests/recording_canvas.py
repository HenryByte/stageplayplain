"""A stand-in canvas that records what is drawn on it, for checking plans
by their primitives rather than their pixels.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Shape:
    """One drawn primitive, in page coordinates, with the pen it used."""

    kind: str
    args: tuple[float, ...]
    stroke: float
    fill: float
    line_width: float
    dashed: bool
    filled: bool = False
    text: str = ""
    font: tuple[str, float] = ("", 0)
    points: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class _Pen:
    stroke: float = 0
    fill: float = 0
    line_width: float = 1
    dashed: bool = False
    font: tuple[str, float] = ("", 0)
    dx: float = 0
    dy: float = 0


class Path:
    def __init__(self) -> None:
        self.points: list[tuple[float, float]] = []

    def moveTo(self, x: float, y: float) -> None:
        self.points.append((x, y))

    def lineTo(self, x: float, y: float) -> None:
        self.points.append((x, y))

    def close(self) -> None:
        pass


class Recorder:
    """Records shapes and text. Only translation is tracked, not scaling."""

    def __init__(self) -> None:
        self.shapes: list[Shape] = []
        self.pen = _Pen()
        self._saved: list[_Pen] = []

    # State

    def saveState(self) -> None:
        self._saved.append(_Pen(**vars(self.pen)))

    def restoreState(self) -> None:
        self.pen = self._saved.pop()

    def translate(self, dx: float, dy: float) -> None:
        self.pen.dx += dx
        self.pen.dy += dy

    def setStrokeGray(self, gray: float) -> None:
        self.pen.stroke = gray

    def setFillGray(self, gray: float) -> None:
        self.pen.fill = gray

    def setLineWidth(self, width: float) -> None:
        self.pen.line_width = width

    def setDash(self, *args: float) -> None:
        self.pen.dashed = bool(args)

    def setFont(self, name: str, size: float) -> None:
        self.pen.font = (name, size)

    # Drawing

    def _add(self, kind: str, *args: float, filled: bool = False) -> None:
        x, y, *rest = args
        self.shapes.append(
            Shape(
                kind,
                (x + self.pen.dx, y + self.pen.dy, *rest),
                self.pen.stroke,
                self.pen.fill,
                self.pen.line_width,
                self.pen.dashed,
                filled,
            )
        )

    def rect(self, x: float, y: float, w: float, h: float, fill: int = 0) -> None:
        self._add("rect", x, y, w, h, filled=bool(fill))

    def roundRect(
        self, x: float, y: float, w: float, h: float, r: float, fill: int = 0
    ) -> None:
        self._add("roundRect", x, y, w, h, r, filled=bool(fill))

    def circle(self, x: float, y: float, r: float, fill: int = 0) -> None:
        self._add("circle", x, y, r, filled=bool(fill))

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self._add("line", x1, y1, x2 + self.pen.dx, y2 + self.pen.dy)

    def beginPath(self) -> Path:
        return Path()

    def drawPath(self, path: Path, fill: int = 0, stroke: int = 1) -> None:
        x, y = path.points[0]
        self._add("path", x, y, filled=bool(fill))
        if not stroke:
            self.shapes[-1].stroke = -1
        self.shapes[-1].points = [
            (px + self.pen.dx, py + self.pen.dy) for px, py in path.points
        ]

    def _text(self, kind: str, x: float, y: float, text: str) -> None:
        self._add(kind, x, y)
        self.shapes[-1].text = text
        self.shapes[-1].font = self.pen.font

    def drawString(self, x: float, y: float, text: str) -> None:
        self._text("text", x, y, text)

    def drawCentredString(self, x: float, y: float, text: str) -> None:
        self._text("centred", x, y, text)

    def drawRightString(self, x: float, y: float, text: str) -> None:
        self._text("right", x, y, text)

    # Queries

    def drawn(self, kind: str) -> list[Shape]:
        """Shapes of a kind, leaving out white halos."""
        return [
            shape
            for shape in self.shapes
            if shape.kind == kind and not (shape.stroke == 1 and not shape.filled)
        ]

    def halos(self) -> list[Shape]:
        return [s for s in self.shapes if s.stroke == 1 and not s.filled]

    def texts(self) -> list[str]:
        return [shape.text for shape in self.shapes if shape.text]

    def text(self, text: str) -> Shape:
        matches = [shape for shape in self.shapes if shape.text == text]
        assert len(matches) == 1, f"{text!r} drawn {len(matches)} times"
        return matches[0]
