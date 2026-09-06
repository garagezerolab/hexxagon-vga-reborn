"""Deterministic Hexxagon opponents, independent of Pygame.

Hard searches every distinct legal successor with iterative deepening and
alpha-beta pruning. Clone moves with different origins but the same destination
produce the same position, so only their first origin needs to be searched.
Bitboards keep the worker process responsive without changing the board rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time

from board import Board, COORDS, CPU, HUMAN, Move, NEIGHBORS, REACH


_ALL = (1 << len(COORDS)) - 1
_ADJ = tuple(sum(1 << i for i in neighbors) for neighbors in NEIGHBORS)
_REACH = tuple(sum(1 << i for i in targets) for targets in REACH)
_JUMPS = tuple(reach & ~adj for reach, adj in zip(_REACH, _ADJ))
_CONTROL = tuple(4 - max(abs(q), abs(r), abs(q + r)) for q, r in COORDS)
_WIN = 100_000.0


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A legal choice plus completed search depth and diagnostic counters."""

    move: Move | None
    score: float
    depth: int
    nodes: int
    elapsed: float


@dataclass(frozen=True, slots=True)
class _Position:
    human: int
    cpu: int
    turn: int


def _position(board: Board) -> _Position:
    human = cpu = 0
    for index, player in enumerate(board.cells):
        if player == HUMAN:
            human |= 1 << index
        elif player == CPU:
            cpu |= 1 << index
    return _Position(human, cpu, board.turn)


def _indices(bits: int):
    while bits:
        lowest = bits & -bits
        yield lowest.bit_length() - 1
        bits ^= lowest


def _destinations(pieces: int, empty: int) -> int:
    reachable = 0
    for index in _indices(pieces):
        reachable |= _REACH[index]
    return reachable & empty


def _has_move(pieces: int, empty: int) -> bool:
    return any(_REACH[index] & empty for index in _indices(pieces))


def _terminal(position: _Position, human_moves: int | None = None,
              cpu_moves: int | None = None) -> bool:
    if not position.human or not position.cpu:
        return True
    empty = _ALL ^ (position.human | position.cpu)
    if not empty:
        return True
    if human_moves is not None and cpu_moves is not None:
        return not human_moves and not cpu_moves
    return not _has_move(position.human, empty) and not _has_move(position.cpu, empty)


def _terminal_value(position: _Position, perspective: int) -> float:
    difference = position.human.bit_count() - position.cpu.bit_count()
    if perspective == CPU:
        difference = -difference
    return (_WIN + difference) if difference > 0 else (
        -_WIN + difference if difference < 0 else 0.0)


def _opportunities(targets: int, victims: int) -> tuple[int, int, int]:
    """Maximum capture, cumulative threats, and distinct exposed victims."""
    best = total = exposed = 0
    for target in _indices(targets):
        captures = _ADJ[target] & victims
        amount = captures.bit_count()
        best = max(best, amount)
        total += amount
        exposed |= captures
    return best, total, exposed.bit_count()


def _evaluate(position: _Position, perspective: int) -> float:
    empty = _ALL ^ (position.human | position.cpu)
    human_moves = _destinations(position.human, empty)
    cpu_moves = _destinations(position.cpu, empty)
    if _terminal(position, human_moves, cpu_moves):
        return _terminal_value(position, perspective)

    # These terms are color-symmetric: swapping the perspective negates the
    # score. Material grows more valuable as the remaining space disappears.
    human_count = position.human.bit_count()
    cpu_count = position.cpu.bit_count()
    occupancy = (human_count + cpu_count) / len(COORDS)
    material = (human_count - cpu_count) * (11.0 + 10.0 * occupancy)
    mobility = 1.8 * (human_moves.bit_count() - cpu_moves.bit_count())
    control = 0.65 * (sum(_CONTROL[i] for i in _indices(position.human))
                      - sum(_CONTROL[i] for i in _indices(position.cpu)))
    human_best, human_threats, exposed_cpu = _opportunities(human_moves, position.cpu)
    cpu_best, cpu_threats, exposed_human = _opportunities(cpu_moves, position.human)
    opportunity = 4.0 * (human_best - cpu_best) + 0.3 * (human_threats - cpu_threats)
    exposure = 1.4 * (exposed_cpu - exposed_human)
    # Empty cells reachable exclusively by one side are a useful territory
    # estimate; inaccessible holes are absent from the bitboards entirely.
    territory = 1.1 * ((human_moves & ~cpu_moves).bit_count()
                       - (cpu_moves & ~human_moves).bit_count())
    score = material + mobility + control + opportunity + exposure + territory
    return score if perspective == HUMAN else -score


def evaluate(board: Board, perspective: int) -> float:
    """Evaluate a board for HUMAN or CPU, with terminal results dominating."""
    if perspective not in (HUMAN, CPU):
        raise ValueError("perspective must be HUMAN or CPU")
    return _evaluate(_position(board), perspective)


def _ordered_moves(position: _Position, preferred: Move | None = None) -> list[Move]:
    """Complete legal move set, excluding identical clone successors only."""
    own, enemy = ((position.human, position.cpu) if position.turn == HUMAN
                  else (position.cpu, position.human))
    if not own or not enemy:
        return []
    empty = _ALL ^ (own | enemy)
    entries: list[tuple[float, int, int]] = []
    cloned = 0
    for source in _indices(own):
        clones = _ADJ[source] & empty & ~cloned
        cloned |= clones
        for target in _indices(clones):
            gain = 2 * (_ADJ[target] & enemy).bit_count() + 1
            entries.append((-gain * 20 - _CONTROL[target], source, target))
        for target in _indices(_JUMPS[source] & empty):
            gain = 2 * (_ADJ[target] & enemy).bit_count()
            entries.append((-gain * 20 - _CONTROL[target] + _CONTROL[source], source, target))
    entries.sort()
    moves = [Move(source, target) for _, source, target in entries]
    if preferred is not None and preferred in moves:
        moves.remove(preferred)
        moves.insert(0, preferred)
    return moves


def _play(position: _Position, move: Move) -> _Position:
    """Same clone, jump, conversion and automatic-pass rules as Board.play."""
    own, enemy = ((position.human, position.cpu) if position.turn == HUMAN
                  else (position.cpu, position.human))
    target = 1 << move.target
    if not (_ADJ[move.source] & target):
        own &= ~(1 << move.source)
    converted = _ADJ[move.target] & enemy
    own |= target | converted
    enemy &= ~converted
    human, cpu = (own, enemy) if position.turn == HUMAN else (enemy, own)
    next_turn = 3 - position.turn
    empty = _ALL ^ (human | cpu)
    if own and enemy and empty and not _has_move(enemy, empty) and _has_move(own, empty):
        next_turn = position.turn
    return _Position(human, cpu, next_turn)


def _immediate(position: _Position, move: Move) -> float:
    enemy = position.cpu if position.turn == HUMAN else position.human
    return 2.0 * (_ADJ[move.target] & enemy).bit_count() + float(move.is_clone)


def _normal_score(position: _Position, move: Move, child: _Position) -> float:
    value = _evaluate(child, position.turn)
    if abs(value) >= _WIN:
        return value
    own, enemy = ((child.human, child.cpu) if position.turn == HUMAN
                  else (child.cpu, child.human))
    empty = _ALL ^ (own | enemy)
    # These are real reachable opponent destinations after this move, including
    # the vacated origin of a jump. A skipped opponent has no response risk.
    best_response = 0.0
    if child.turn != position.turn:
        for target in _indices(_destinations(enemy, empty)):
            captures = (_ADJ[target] & own).bit_count()
            clone_gain = bool(_ADJ[target] & enemy)
            best_response = max(best_response, 2.0 * captures + clone_gain)
    return value + 2.5 * _immediate(position, move) - 4.5 * best_response


class _TimeUp(Exception):
    pass


@dataclass(slots=True)
class _Entry:
    depth: int
    value: float
    flag: int  # -1 upper bound, 0 exact, +1 lower bound
    move: Move | None


class _Search:
    def __init__(self, perspective: int, deadline: float):
        self.perspective = perspective
        self.deadline = deadline
        self.nodes = 0
        self.table: dict[_Position, _Entry] = {}

    def check_time(self) -> None:
        if time.perf_counter() >= self.deadline:
            raise _TimeUp

    def search(self, position: _Position, depth: int, alpha: float,
               beta: float) -> tuple[float, Move | None]:
        self.nodes += 1
        if self.nodes % 32 == 1:
            self.check_time()
        if depth == 0 or _terminal(position):
            return _evaluate(position, self.perspective), None

        original_alpha, original_beta = alpha, beta
        entry = self.table.get(position)
        if entry is not None and entry.depth >= depth:
            if entry.flag == 0:
                return entry.value, entry.move
            if entry.flag > 0:
                alpha = max(alpha, entry.value)
            else:
                beta = min(beta, entry.value)
            if alpha >= beta:
                return entry.value, entry.move

        maximizing = position.turn == self.perspective
        best = -math.inf if maximizing else math.inf
        best_move = None
        moves = _ordered_moves(position, entry.move if entry else None)
        if not moves:
            # Public Board.play already normalizes passes; this also supports
            # a manually supplied position whose blocked turn is not normalized.
            passed = _Position(position.human, position.cpu, 3 - position.turn)
            return self.search(passed, depth, alpha, beta)
        for move in moves:
            value, _ = self.search(_play(position, move), depth - 1, alpha, beta)
            if (maximizing and value > best) or (not maximizing and value < best):
                best, best_move = value, move
            if maximizing:
                alpha = max(alpha, best)
            else:
                beta = min(beta, best)
            if alpha >= beta:
                break
        flag = -1 if best <= original_alpha else (1 if best >= original_beta else 0)
        if len(self.table) < 100_000:
            self.table[position] = _Entry(depth, best, flag, best_move)
        return best, best_move


def choose_move(board: Board, difficulty: str = "Normal", depth: int = 3,
                time_limit: float = 2.0) -> SearchResult:
    """Return a deterministic legal move; Hard observes a search time budget.

    ``depth`` is Hard's maximum number of plies, including the candidate move.
    Hard returns the last completely searched iteration if its budget expires.
    A zero budget still returns a legal, immediately scored fallback. No move
    is returned for a terminal board or a blocked current side: callers can use
    ``Board.normalize_turn`` to perform that side's forced pass.
    """
    started = time.perf_counter()
    level = difficulty.strip().casefold()
    if level not in {"easy", "normal", "hard"}:
        raise ValueError("difficulty must be Easy, Normal or Hard")
    if not isinstance(depth, int) or depth < 1:
        raise ValueError("depth must be a positive integer")
    if not math.isfinite(time_limit) or time_limit < 0:
        raise ValueError("time_limit must be finite and nonnegative")
    position = _position(board)
    if _terminal(position):
        return SearchResult(None, _evaluate(position, board.turn), 0, 0,
                            time.perf_counter() - started)
    moves = _ordered_moves(position)
    if not moves:
        return SearchResult(None, _evaluate(position, board.turn), 0, 0,
                            time.perf_counter() - started)

    fallback = moves[0]
    best_score = _evaluate(_play(position, fallback), board.turn)
    if level == "hard":
        search = _Search(board.turn, started + time_limit)
        best_move, completed = fallback, 0
        for current_depth in range(1, depth + 1):
            try:
                search.check_time()
                score, move = search.search(position, current_depth, -math.inf, math.inf)
                # Only publish complete iterations, including the time check.
                search.check_time()
            except _TimeUp:
                break
            if move is not None:
                best_move, best_score, completed = move, score, current_depth
        return SearchResult(best_move, best_score, completed, search.nodes,
                            time.perf_counter() - started)

    best_move, best_score, nodes = fallback, -math.inf, 0
    for move in moves:
        child = _play(position, move)
        nodes += 1
        if level == "easy":
            score = (_terminal_value(child, board.turn) if _terminal(child)
                     else _immediate(position, move))
        else:
            score = _normal_score(position, move, child)
        if score > best_score:
            best_move, best_score = move, score
    return SearchResult(best_move, best_score, 1, nodes, time.perf_counter() - started)
