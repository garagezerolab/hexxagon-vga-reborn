"""Rules, terminal positions, and rendering-independent geometry checks."""

from dataclasses import FrozenInstanceError
import math

import pytest

from board import (
    Board, COORDS, CPU, EMPTY, HexLayout, HOLES, HUMAN, INDEX,
    Move, NEIGHBORS, REACH, hex_distance, neighbors,
)


def move(source, target):
    return Move(INDEX[source], INDEX[target])


def test_board_shape_and_rotationally_symmetric_holes():
    assert len(COORDS) == len(INDEX) == 58
    assert len(set(COORDS)) == 58
    assert not set(COORDS).intersection(HOLES)
    assert all(hex_distance(coord, (0, 0)) <= 4 for coord in COORDS)
    # A 120-degree cube rotation maps each omitted cell to another hole.
    assert {(-q - r, q) for q, r in HOLES} == set(HOLES)


def test_initial_position_has_alternating_corners_and_human_turn():
    board = Board.initial()
    assert Board() == board
    assert board.turn == HUMAN and board.ply == 0
    assert board.count(HUMAN) == board.count(CPU) == 3
    assert board.count(EMPTY) == 52
    corners = ((0, -4), (4, -4), (4, 0), (0, 4), (-4, 4), (-4, 0))
    assert [board.cells[INDEX[coord]] for coord in corners] == [1, 2, 1, 2, 1, 2]
    assert board.winner is None and board.end_reason is None


def test_six_neighbors_are_unbounded_and_reciprocal():
    assert set(neighbors((0, 0))) == {(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)}
    assert len(neighbors((4, 0))) == 6
    assert (5, 0) in neighbors((4, 0))
    for source, adjacent in enumerate(NEIGHBORS):
        for target in adjacent:
            assert source in NEIGHBORS[target]
            assert hex_distance(COORDS[source], COORDS[target]) == 1
    assert len(NEIGHBORS[INDEX[(0, 0)]]) == 6


@pytest.mark.parametrize("a,b,expected", [
    ((0, 0), (0, 0), 0), ((0, 0), (1, -1), 1),
    ((0, 0), (2, -1), 2), ((0, 0), (1, 1), 2),
    ((-4, 0), (4, 0), 8), ((0, -4), (4, 0), 8),
    ((-2, 1), (1, -2), 3),
])
def test_hex_distance(a, b, expected):
    assert hex_distance(a, b) == hex_distance(b, a) == expected


def test_reach_includes_exactly_playable_distance_one_and_two_cells():
    for source, coord in enumerate(COORDS):
        expected = {j for j, other in enumerate(COORDS) if 1 <= hex_distance(coord, other) <= 2}
        assert set(REACH[source]) == expected
        assert set(NEIGHBORS[source]).issubset(REACH[source])


def test_legal_moves_match_independent_distance_oracle():
    board = Board.initial()
    for player in (HUMAN, CPU):
        expected = {
            Move(source, target)
            for source, value in enumerate(board.cells) if value == player
            for target, occupant in enumerate(board.cells)
            if occupant == EMPTY and 1 <= hex_distance(COORDS[source], COORDS[target]) <= 2
        }
        actual = board.legal_moves(player)
        assert set(actual) == expected
        assert actual == tuple(sorted(actual, key=lambda item: (item.source, item.target)))
    assert all(board.is_legal(item) for item in board.legal_moves())


def test_clone_keeps_source_and_adds_one_piece_without_mutating_parent():
    board = Board.from_mapping({(0, 0): HUMAN, (4, -4): CPU})
    action = move((0, 0), (1, 0))
    assert action.is_clone
    child = board.play(action)
    assert child.cells[action.source] == child.cells[action.target] == HUMAN
    assert child.count(HUMAN) == 2
    assert child.turn == CPU and child.ply == 1
    assert board.count(HUMAN) == 1 and board.cells[action.target] == EMPTY


def test_jump_removes_source_and_preserves_piece_count():
    board = Board.from_mapping({(0, 0): HUMAN, (-4, 0): CPU})
    action = move((0, 0), (2, -1))
    assert not action.is_clone
    child = board.play(action)
    assert child.cells[action.source] == EMPTY
    assert child.cells[action.target] == HUMAN
    assert child.count(HUMAN) == 1


def test_jump_can_cross_a_missing_cell():
    board = Board.from_mapping({(-1, -2): HUMAN, (4, 0): CPU})
    action = move((-1, -2), (1, -2))
    assert (0, -2) in HOLES
    assert board.is_legal(action)
    assert board.play(action).cells[action.target] == HUMAN


def test_move_converts_all_six_adjacent_opponents_but_no_distant_piece():
    mapping = {coord: CPU for coord in neighbors((0, 0))}
    mapping[(2, -1)] = HUMAN
    mapping[(4, -4)] = CPU
    board = Board.from_mapping(mapping)
    action = move((2, -1), (0, 0))
    assert set(board.converted_by(action)) == set(NEIGHBORS[INDEX[(0, 0)]])
    child = board.play(action)
    assert child.count(HUMAN) == 7
    assert child.count(CPU) == 1
    assert child.cells[INDEX[(4, -4)]] == CPU


def test_friendly_neighbors_remain_friendly_and_are_not_reported_as_conversions():
    board = Board.from_mapping({(0, 0): HUMAN, (1, -1): HUMAN, (0, 1): CPU, (4, -4): CPU})
    action = move((0, 0), (1, 0))
    assert board.converted_by(action) == (INDEX[(0, 1)],)
    child = board.play(action)
    assert child.cells[INDEX[(1, -1)]] == HUMAN
    assert child.count(HUMAN) == 4


@pytest.mark.parametrize("action", [
    Move(-1, 0), Move(0, -1), Move(999, 0), Move(0, 999),
    Move(0.5, 1), Move(True, 1),
    move((0, 0), (0, 0)), move((0, 0), (4, 0)),
    move((0, 0), (1, 0)), move((4, 0), (3, 0)),
])
def test_illegal_moves_are_rejected_without_state_changes(action):
    board = Board.from_mapping({(0, 0): HUMAN, (1, 0): CPU, (4, 0): CPU})
    snapshot = board.cells
    assert not board.is_legal(action)
    with pytest.raises(ValueError, match="Illegal move"):
        board.play(action)
    assert board.cells == snapshot and board.ply == 0


def test_turn_changes_after_successful_moves_for_both_sides():
    board = Board.from_mapping({(0, -4): HUMAN, (0, 4): CPU})
    second = board.play(move((0, -4), (0, -3)))
    assert second.turn == CPU
    third = second.play(move((0, 4), (0, 3)))
    assert third.turn == HUMAN and third.ply == 2


def test_automatic_pass_when_cpu_is_trapped_at_corner():
    # Fill the entire corner's radius-two neighborhood with human stones.
    cpu_cell = INDEX[(4, 0)]
    mapping = {COORDS[index]: HUMAN for index in REACH[cpu_cell]}
    mapping[(4, 0)] = CPU
    mapping[(-4, 0)] = HUMAN
    board = Board.from_mapping(mapping)
    assert not board.legal_moves(CPU)
    child = board.play(move((-4, 0), (-3, 0)))
    assert child.turn == HUMAN
    assert child.winner is None and child.ply == 1
    assert child.legal_moves(HUMAN) and not child.legal_moves(CPU)


def test_normalize_turn_handles_either_side_without_incrementing_ply():
    human_cell = INDEX[(-4, 0)]
    mapping = {COORDS[index]: CPU for index in REACH[human_cell]}
    mapping[(-4, 0)] = HUMAN
    mapping[(4, 0)] = CPU
    board = Board.from_mapping(mapping, turn=HUMAN)
    assert not board.legal_moves()
    normalized = board.normalize_turn()
    assert normalized.turn == CPU
    assert normalized.cells == board.cells and normalized.ply == board.ply
    assert normalized.normalize_turn() is normalized


def test_full_board_draw_and_terminal_move_rejection():
    board = Board(tuple([HUMAN] * 29 + [CPU] * 29))
    assert board.end_reason == "full"
    assert board.winner == EMPTY
    assert board.legal_moves() == board.legal_moves(CPU) == ()
    assert board.normalize_turn() is board
    with pytest.raises(ValueError):
        board.play(Move(0, 1))


@pytest.mark.parametrize("human_count,winner", [(40, HUMAN), (10, CPU)])
def test_full_board_winner_uses_piece_counts(human_count, winner):
    board = Board(tuple([HUMAN] * human_count + [CPU] * (58 - human_count)))
    assert board.end_reason == "full" and board.winner == winner


@pytest.mark.parametrize("survivor", [HUMAN, CPU])
def test_extinction_ends_game_even_with_many_empty_cells(survivor):
    board = Board.from_mapping({(0, 0): survivor})
    assert board.end_reason == "extinction" and board.winner == survivor
    assert board.legal_moves(HUMAN) == board.legal_moves(CPU) == ()
    assert board.normalize_turn() is board


def test_last_enemy_conversion_ends_game():
    board = Board.from_mapping({(0, 0): HUMAN, (1, -1): CPU})
    child = board.play(move((0, 0), (1, 0)))
    assert child.winner == HUMAN and child.end_reason == "extinction"
    assert child.count(HUMAN) == 3 and child.count(CPU) == 0


def test_empty_custom_board_is_terminal_draw():
    board = Board.from_mapping({})
    assert board.winner == EMPTY and board.end_reason == "extinction"
    assert board.normalize_turn() is board


def test_neither_side_can_move_detection_is_independent_of_full_board(monkeypatch):
    # The standard board is connected: with both colors alive, an empty cell
    # must border an occupied region. A disconnected geometry can nonetheless
    # exercise the general neither-side-can-move rule without inventing walls.
    import board as rules
    position = Board.from_mapping({(-4, 0): HUMAN, (4, 0): CPU})
    monkeypatch.setattr(rules, "REACH", tuple(() for _ in COORDS))
    assert position.end_reason == "blocked" and position.winner == EMPTY
    assert position.normalize_turn() is position


def test_board_is_immutable_and_copies_mutable_input():
    source = list(Board.initial().cells)
    board = Board(source)
    source[INDEX[(0, -4)]] = EMPTY
    assert board.cells[INDEX[(0, -4)]] == HUMAN
    with pytest.raises(FrozenInstanceError):
        board.turn = CPU


@pytest.mark.parametrize("factory", [
    lambda: Board((EMPTY,)),
    lambda: Board(tuple([3] * 58)),
    lambda: Board(turn=EMPTY),
    lambda: Board(ply=-1),
    lambda: Board.from_mapping({(0, -2): HUMAN}),
    lambda: Board.from_mapping({(10, 10): CPU}),
    lambda: Board.initial().legal_moves(EMPTY),
])
def test_invalid_positions_and_players_raise_clear_errors(factory):
    with pytest.raises(ValueError):
        factory()


@pytest.mark.parametrize("layout", [HexLayout(), HexLayout(18.5, (207.3, 140.5)), HexLayout(6, (-100, -50))])
def test_hex_pixel_roundtrip_and_center_hit_tests(layout):
    for index, coord in enumerate(COORDS):
        pixel = layout.to_pixel(coord)
        assert layout.from_pixel(pixel) == coord
        assert layout.cell_at(pixel) == index
        # Every point clearly inside the polygon resolves to this cell.
        cx, cy = layout._center(coord)
        for angle in range(0, 360, 30):
            point = (cx + layout.size * .65 * math.cos(math.radians(angle)),
                     cy + layout.size * .65 * math.sin(math.radians(angle)))
            assert layout.cell_at(point) == index


def test_holes_and_outside_clicks_have_no_cell():
    layout = HexLayout()
    for coord in HOLES | {(5, 0), (-5, 0), (0, -5), (0, 5)}:
        assert layout.cell_at(layout.to_pixel(coord)) is None
    assert layout.cell_at((-10000, 10000)) is None
    assert layout.cell_at((float("nan"), 0)) is None
    assert layout.cell_at((0, float("inf"))) is None
    # Beyond the rightmost corner of the boundary cell's true polygon.
    cx, cy = layout._center((4, 0))
    assert layout.cell_at((cx + layout.size + 1, cy)) is None


def test_polygon_is_flat_top_with_six_integer_vertices_and_inset():
    layout = HexLayout(12, (100, 100))
    poly = layout.polygon((0, 0))
    assert len(poly) == 6 and len(set(poly)) == 6
    assert poly[0] == (112, 100) and poly[3] == (88, 100)
    assert poly[1][1] == poly[2][1] and poly[4][1] == poly[5][1]
    assert all(type(value) is int for point in poly for value in point)
    assert layout.polygon((0, 0), inset=2)[0] == (110, 100)


@pytest.mark.parametrize("size", [0, -1, float("inf"), float("nan")])
def test_invalid_hex_size_is_rejected(size):
    with pytest.raises(ValueError):
        HexLayout(size)
