"""Behavioral checks for legal, deterministic and genuinely searched AI moves."""

from dataclasses import FrozenInstanceError
import math
import pickle

import pytest

from ai import _ordered_moves, _play, _position, choose_move, evaluate
from board import Board, COORDS, CPU, HUMAN


def _late_board() -> Board:
    empties = {(0, 0), (1, 0), (-1, 1)}
    return Board.from_mapping({coord: (HUMAN if i % 3 else CPU)
                               for i, coord in enumerate(COORDS)
                               if coord not in empties}, turn=CPU)


def _pass_board() -> Board:
    empties = {(4, -4), (4, -3), (3, -4)}
    return Board.from_mapping({coord: HUMAN if coord == (-4, 0) else CPU
                               for coord in COORDS if coord not in empties}, turn=CPU)


def _minimax(board: Board, depth: int, perspective: int) -> float:
    if depth == 0 or board.winner is not None:
        return evaluate(board, perspective)
    moves = board.legal_moves()
    if not moves:
        return _minimax(board.normalize_turn(), depth, perspective)
    values = [_minimax(board.play(move), depth - 1, perspective) for move in moves]
    return max(values) if board.turn == perspective else min(values)


@pytest.mark.parametrize("difficulty", ["Easy", "Normal", "Hard"])
def test_choices_are_legal_and_deterministic(difficulty):
    board = Board.initial()
    first = choose_move(board, difficulty, depth=1, time_limit=3.0)
    second = choose_move(board, difficulty, depth=1, time_limit=3.0)
    assert first.move in board.legal_moves()
    assert first.move == second.move
    assert first.score == second.score
    assert first.depth == 1
    assert first.nodes > 0


@pytest.mark.parametrize("difficulty", ["Easy", "Normal", "Hard"])
def test_obvious_extinction_win_is_taken(difficulty):
    board = Board.from_mapping({(0, 0): CPU, (2, -1): HUMAN}, turn=CPU)
    result = choose_move(board, difficulty, depth=2, time_limit=3.0)
    assert result.move is not None
    assert board.play(result.move).winner == CPU
    assert result.score > 100_000


@pytest.mark.parametrize("difficulty", ["Easy", "Normal", "Hard"])
def test_terminal_board_returns_no_move(difficulty):
    board = Board.from_mapping({(0, 0): CPU}, turn=CPU)
    result = choose_move(board, difficulty)
    assert result.move is None
    assert result.depth == result.nodes == 0
    assert result.score > 100_000


def test_zero_budget_returns_legal_fallback():
    board = Board.initial()
    result = choose_move(board, "Hard", depth=8, time_limit=0.0)
    assert result.move in board.legal_moves()
    assert result.depth == 0
    assert result.elapsed < 0.3


def test_hard_respects_short_time_budget():
    result = choose_move(Board.initial(), "Hard", depth=30, time_limit=0.025)
    assert result.move in Board.initial().legal_moves()
    assert result.depth < 30
    assert result.elapsed < 0.5


@pytest.mark.parametrize("board_factory", [_late_board, _pass_board])
def test_hard_matches_unpruned_minimax_and_configured_depth(board_factory):
    board = board_factory()
    result = choose_move(board, "Hard", depth=2, time_limit=8.0)
    expected = _minimax(board, 2, board.turn)
    assert result.depth == 2
    assert result.score == pytest.approx(expected)
    assert result.move is not None
    assert _minimax(board.play(result.move), 1, board.turn) == pytest.approx(expected)


def test_pass_board_really_grants_extra_turn():
    board = _pass_board()
    assert not board.legal_moves(HUMAN)
    clone = next(move for move in board.legal_moves() if move.is_clone)
    child = board.play(clone)
    assert child.turn == CPU
    assert child.winner is None
    assert _play(_position(board), clone) == _position(child)


def test_blocked_current_side_returns_none_until_caller_normalizes():
    active = _pass_board()
    blocked = Board(active.cells, HUMAN, active.ply)
    assert blocked.winner is None
    assert choose_move(blocked, "Hard").move is None
    normalized = blocked.normalize_turn()
    assert normalized.turn == CPU
    assert choose_move(normalized, "Easy").move in normalized.legal_moves()


def test_evaluation_is_symmetric_and_color_neutral():
    board = _late_board()
    assert evaluate(board, HUMAN) == -evaluate(board, CPU)
    swapped = Board(tuple(3 - cell if cell else cell for cell in board.cells),
                    3 - board.turn, board.ply)
    assert evaluate(swapped, HUMAN) == pytest.approx(evaluate(board, CPU))


def test_clone_deduplication_preserves_all_distinct_successors():
    board = Board.from_mapping({(0, 0): HUMAN, (1, 0): HUMAN, (4, -4): CPU})
    regular = {_position(board.play(move)) for move in board.legal_moves()}
    position = _position(board)
    optimized = {_play(position, move) for move in _ordered_moves(position)}
    assert optimized == regular
    assert len(_ordered_moves(position)) < len(board.legal_moves())


def test_bitboard_transitions_match_public_board_over_full_match():
    board = Board.initial()
    # Deterministic greedy play reaches crowded states and exercises extinction,
    # conversion, jumps and clones without depending on the random module.
    for ply in range(120):
        if board.winner is not None:
            break
        position = _position(board)
        moves = board.legal_moves()
        for move in moves:
            assert _play(position, move) == _position(board.play(move))
        selected = choose_move(board, "Easy").move
        assert selected is not None
        board = board.play(selected)
    assert board.winner is not None


def test_search_result_can_cross_process_boundary_and_is_immutable():
    result = choose_move(Board.initial(), "Easy")
    assert pickle.loads(pickle.dumps(result)) == result
    with pytest.raises(FrozenInstanceError):
        result.score = 0.0


@pytest.mark.parametrize("kwargs", [{"difficulty": "Impossible"}, {"depth": 0},
                                    {"depth": 1.5}, {"time_limit": -1},
                                    {"time_limit": math.inf}])
def test_invalid_search_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        choose_move(Board.initial(), **kwargs)


def test_invalid_evaluation_perspective_is_rejected():
    with pytest.raises(ValueError):
        evaluate(Board.initial(), 0)
