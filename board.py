"""Pure Hexxagon rules and flat-top hex geometry, independent of Pygame.

The board is a radius-four axial hexagon with three rotationally symmetric
holes: 58 playable cells. Six alternating corner pieces give each player
three pieces. A jump measures hex distance; it does not need a clear path.
Only the landing cell's six immediate neighbors are converted.

The historical board is represented with an original layout and no game
assets. A player without a move passes automatically. The score is the
number of occupied cells; inaccessible empty cells are never awarded.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Mapping


EMPTY = 0
HUMAN = 1
CPU = 2
Coord = tuple[int, int]
RADIUS = 4
HOLES: frozenset[Coord] = frozenset(((0, -2), (-2, 2), (2, 0)))
DIRECTIONS: tuple[Coord, ...] = (
    (1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)
)


def hex_distance(a: Coord, b: Coord) -> int:
    """Return axial/cube distance, including across holes or board edges."""
    dq, dr = a[0] - b[0], a[1] - b[1]
    return max(abs(dq), abs(dr), abs(dq + dr))


def neighbors(coord: Coord) -> tuple[Coord, ...]:
    """Return all six logical neighbors, including off-board coordinates."""
    q, r = coord
    return tuple((q + dq, r + dr) for dq, dr in DIRECTIONS)


COORDS: tuple[Coord, ...] = tuple(
    (q, r)
    for q in range(-RADIUS, RADIUS + 1)
    for r in range(-RADIUS, RADIUS + 1)
    if hex_distance((q, r), (0, 0)) <= RADIUS and (q, r) not in HOLES
)
INDEX: dict[Coord, int] = {coord: index for index, coord in enumerate(COORDS)}
NEIGHBORS: tuple[tuple[int, ...], ...] = tuple(
    tuple(j for j, other in enumerate(COORDS) if hex_distance(coord, other) == 1)
    for coord in COORDS
)
REACH: tuple[tuple[int, ...], ...] = tuple(
    tuple(j for j, other in enumerate(COORDS) if 1 <= hex_distance(coord, other) <= 2)
    for coord in COORDS
)
_CORNERS: tuple[Coord, ...] = (
    (0, -4), (4, -4), (4, 0), (0, 4), (-4, 4), (-4, 0)
)
_INITIAL_MAP = {coord: HUMAN if i % 2 == 0 else CPU for i, coord in enumerate(_CORNERS)}
_INITIAL_CELLS: tuple[int, ...] = tuple(_INITIAL_MAP.get(coord, EMPTY) for coord in COORDS)


@dataclass(frozen=True, slots=True)
class Move:
    """A source and landing cell, indexed into COORDS."""

    source: int
    target: int

    @property
    def is_clone(self) -> bool:
        return hex_distance(COORDS[self.source], COORDS[self.target]) == 1


@dataclass(frozen=True, slots=True)
class Board:
    """Immutable game state suitable for snapshots and AI search.

    Constructed positions retain their supplied turn. Call normalize_turn()
    to apply an automatic pass; play() already does so after every move.
    """

    cells: tuple[int, ...] = _INITIAL_CELLS
    turn: int = HUMAN
    ply: int = 0

    def __post_init__(self) -> None:
        # A caller passing a list must not be able to mutate a frozen state.
        object.__setattr__(self, "cells", tuple(self.cells))
        if len(self.cells) != len(COORDS):
            raise ValueError(f"Expected {len(COORDS)} cells, got {len(self.cells)}")
        if any(type(value) is not int or value not in (EMPTY, HUMAN, CPU) for value in self.cells):
            raise ValueError("Cells must contain EMPTY (0), HUMAN (1), or CPU (2)")
        if type(self.turn) is not int or self.turn not in (HUMAN, CPU):
            raise ValueError("Turn must be HUMAN (1) or CPU (2)")
        if type(self.ply) is not int or self.ply < 0:
            raise ValueError("Ply must be a nonnegative integer")

    @classmethod
    def initial(cls) -> Board:
        return cls()

    @classmethod
    def from_mapping(cls, mapping: Mapping[Coord, int], turn: int = HUMAN) -> Board:
        """Build a position, leaving unspecified playable cells empty."""
        unknown = set(mapping).difference(INDEX)
        if unknown:
            raise ValueError(f"Coordinates are not playable cells: {sorted(unknown)}")
        return cls(tuple(mapping.get(coord, EMPTY) for coord in COORDS), turn)

    def count(self, player: int) -> int:
        """Count a faction's pieces, or empty cells when player is EMPTY."""
        return self.cells.count(player)

    def _has_moves(self, player: int) -> bool:
        return any(
            self.cells[target] == EMPTY
            for source, value in enumerate(self.cells)
            if value == player
            for target in REACH[source]
        )

    def legal_moves(self, player: int | None = None) -> tuple[Move, ...]:
        """Enumerate moves in deterministic source/target index order.

        An explicit player supports evaluating the other side's mobility.
        Multiple sources cloning into one target remain distinct legal moves.
        """
        player = self.turn if player is None else player
        if type(player) is not int or player not in (HUMAN, CPU):
            raise ValueError("Player must be HUMAN (1) or CPU (2)")
        if HUMAN not in self.cells or CPU not in self.cells:
            return ()
        return tuple(
            Move(source, target)
            for source, value in enumerate(self.cells)
            if value == player
            for target in REACH[source]
            if self.cells[target] == EMPTY
        )

    def is_legal(self, move: Move) -> bool:
        """Check a move for the current side without changing this board."""
        if not isinstance(move, Move):
            return False
        if any(type(index) is not int or not 0 <= index < len(COORDS)
               for index in (move.source, move.target)):
            return False
        return (
            self.cells[move.source] == self.turn
            and self.cells[move.target] == EMPTY
            and move.target in REACH[move.source]
            and HUMAN in self.cells
            and CPU in self.cells
        )

    def converted_by(self, move: Move) -> tuple[int, ...]:
        """Return opponent cells converted by a legal current-player move."""
        if not self.is_legal(move):
            raise ValueError("Illegal move")
        opponent = 3 - self.turn
        return tuple(index for index in NEIGHBORS[move.target] if self.cells[index] == opponent)

    def play(self, move: Move) -> Board:
        """Apply clone/jump, convert neighbors, and automatically pass if needed."""
        converted = self.converted_by(move)  # Validates before any work is done.
        cells = list(self.cells)
        if not move.is_clone:
            cells[move.source] = EMPTY
        cells[move.target] = self.turn
        for index in converted:
            cells[index] = self.turn
        return Board(tuple(cells), 3 - self.turn, self.ply + 1).normalize_turn()

    def normalize_turn(self) -> Board:
        """Pass once when only the other side can move; never loop on stalemate."""
        if self.end_reason is not None or self._has_moves(self.turn):
            return self
        return replace(self, turn=3 - self.turn)

    @property
    def end_reason(self) -> str | None:
        """Return 'extinction', 'full', 'blocked', or None while playable."""
        if HUMAN not in self.cells or CPU not in self.cells:
            return "extinction"
        if EMPTY not in self.cells:
            return "full"
        if not self._has_moves(HUMAN) and not self._has_moves(CPU):
            return "blocked"
        return None

    @property
    def winner(self) -> int | None:
        """Winner's faction, EMPTY for a draw, or None while play can continue."""
        if self.end_reason is None:
            return None
        human, cpu = self.count(HUMAN), self.count(CPU)
        return HUMAN if human > cpu else CPU if cpu > human else EMPTY


@dataclass(frozen=True, slots=True)
class HexLayout:
    """Flat-top axial geometry using the outer (corner-to-center) radius."""

    size: float = 12.0
    origin: tuple[float, float] = (105.0, 129.0)

    def __post_init__(self) -> None:
        if not math.isfinite(self.size) or self.size <= 0:
            raise ValueError("Hex size must be finite and positive")
        if len(self.origin) != 2 or not all(math.isfinite(value) for value in self.origin):
            raise ValueError("Origin must contain two finite coordinates")

    def _center(self, coord: Coord) -> tuple[float, float]:
        q, r = coord
        return (
            self.origin[0] + 1.5 * self.size * q,
            self.origin[1] + math.sqrt(3) * self.size * (r + q / 2),
        )

    def to_pixel(self, coord: Coord) -> tuple[int, int]:
        x, y = self._center(coord)
        return round(x), round(y)

    def from_pixel(self, point: tuple[float, float]) -> Coord:
        """Find the nearest logical hex by cube rounding, even off-board."""
        x, y = point[0] - self.origin[0], point[1] - self.origin[1]
        q = (2 / 3) * x / self.size
        r = (-x / 3 + math.sqrt(3) * y / 3) / self.size
        s = -q - r
        rq, rr, rs = round(q), round(r), round(s)
        dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
        if dq > dr and dq > ds:
            rq = -rr - rs
        elif dr > ds:
            rr = -rq - rs
        return rq, rr

    def cell_at(self, point: tuple[float, float]) -> int | None:
        """Hit-test playable hex interiors; holes and outside clicks return None."""
        if not all(math.isfinite(value) for value in point):
            return None
        coord = self.from_pixel(point)
        index = INDEX.get(coord)
        if index is None:
            return None
        cx, cy = self._center(coord)
        dx, dy = abs(point[0] - cx), abs(point[1] - cy)
        # Half-plane tests for a flat-top hex, with tiny round-off tolerance.
        epsilon = 1e-9
        if (dx > self.size + epsilon
                or dy > math.sqrt(3) * self.size / 2 + epsilon
                or math.sqrt(3) * dx + dy > math.sqrt(3) * self.size + epsilon):
            return None
        return index

    def polygon(self, coord: Coord, inset: float = 0) -> tuple[tuple[int, int], ...]:
        """Return six pixel corners, optionally shrinking for grid-line gutters."""
        cx, cy = self._center(coord)
        radius = max(0.0, self.size - inset)
        return tuple(
            (round(cx + radius * math.cos(i * math.pi / 3)),
             round(cy + radius * math.sin(i * math.pi / 3)))
            for i in range(6)
        )
