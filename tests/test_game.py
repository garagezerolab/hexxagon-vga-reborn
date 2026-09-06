"""Controller and real multiprocessing integration using SDL's dummy drivers."""

import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import Mock

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
import pytest

from board import Board, COORDS, CPU, HUMAN
from game import Game, Match
from worker import AIWorker
import worker as worker_module


@pytest.fixture
def game():
    instance = Game(scale=2, sound=False)
    yield instance
    instance.close()


def test_selection_illegal_input_and_snapshot():
    match = Match()
    assert not match.select(-1)
    assert not match.select(100)
    assert not match.select(None)
    move = match.board.legal_moves()[0]
    assert match.select(move.source)
    assert move.target in match.valid
    before = match.apply(move)
    assert before == Board.initial()
    assert match.board != before
    assert match.selected is None
    assert match.board.turn == CPU
    assert not match.select(move.target)


def test_scaled_board_click_animation_and_pause(game):
    game.new_game()
    move = game.match.board.legal_moves()[0]
    game._click_board(game.layout.to_pixel(COORDS[move.source]))
    assert game.match.selected == move.source
    game._click_board(game.layout.to_pixel(COORDS[move.target]))
    assert game.animation is not None
    assert game.match.board.ply == 1
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    game.update(0.3)
    assert game.screen == "paused"
    assert game.animation["elapsed"] == 0
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    game.update(0.6)
    assert game.screen == "playing"
    assert game.animation is None
    assert game.match.board.turn == CPU


def test_letterbox_coordinates_and_offboard_click(game):
    game.new_game()
    game.handle_event(pygame.event.Event(pygame.VIDEORESIZE, w=901, h=611))
    assert game._scale == 2
    source = game.match.board.legal_moves()[0].source
    internal = game.layout.to_pixel(COORDS[source])
    window_point = tuple(game._offset[i] + internal[i] * game._scale for i in (0, 1))
    assert game.to_internal(window_point) == internal
    game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=window_point, button=1))
    assert game.match.selected == source
    game._click_board((-50, -50))
    assert game.match.selected is None
    assert game.match.board == Board.initial()


def test_all_menu_flows_and_terminal_overlays(game):
    game._action("difficulty")
    assert game.difficulty == "Hard"
    game._action("instructions")
    assert game.screen == "instructions"
    game.renderer.draw(game.view())
    game._action("back")
    assert game.screen == "menu"
    game._action("new_game")
    game._action("menu")
    assert game.screen == "paused"
    game._action("resume")
    for player in (HUMAN, CPU, 0):
        game.match.board = Board(tuple(player for _ in COORDS))
        game.screen = "playing"
        game.update(0.01)
        assert game.screen == "gameover"
        assert game.match.board.winner == player
        game.renderer.draw(game.view())
        game._action("menu")
        assert game.screen == "menu"


def test_real_cpu_process_and_restart(game):
    game.new_game()
    game._commit(game.match.board.legal_moves()[0])
    game.update(0.6)
    game.update(0.01)
    assert game.worker.busy
    deadline = time.monotonic() + 10
    while game.match.board.ply < 2 and time.monotonic() < deadline:
        game.update(0.05)
        time.sleep(0.01)
    assert game.match.board.ply == 2, "Worker did not deliver a legal CPU move"
    assert game.last_result.move is not None
    assert game.match.board.turn == HUMAN
    process = game.worker.process
    game.new_game()
    assert game.match.board == Board.initial()
    assert game.worker.process is None
    assert game.pending_result is None
    assert game.animation is None
    assert process._closed


def test_restart_cancels_pending_search(game):
    game.new_game()
    board = game.match.board.play(game.match.board.legal_moves()[0])
    game.match.board = board
    game.worker.submit(board, "Hard", 20, 5)
    game.new_game()
    assert game.worker.process is None
    assert not game.worker.busy
    assert game.match.board.ply == 0


def test_failed_worker_start_closes_connections(monkeypatch):
    parent, child, process = Mock(), Mock(), Mock()
    process.start.side_effect = OSError("process creation unavailable")
    context = Mock()
    context.Pipe.return_value = (parent, child)
    context.Process.return_value = process
    monkeypatch.setattr(worker_module.mp, "get_context", lambda *_: context)
    cpu = AIWorker()
    with pytest.raises(OSError):
        cpu.submit(Board.initial(), "Normal", 3, 1)
    cpu.close()  # Must remain safe after the failed start.
    parent.close.assert_called_once()
    child.close.assert_called_once()
    assert cpu.process is None


def test_cpu_failure_has_legal_recovery(game, monkeypatch):
    game.new_game()
    game.match.board = game.match.board.play(game.match.board.legal_moves()[0])
    monkeypatch.setattr(game.worker, "submit", Mock(side_effect=OSError("unavailable")))
    game.update(0.01)
    assert game.match.board.ply == 2
    assert game.animation is not None
    assert game.last_result.move is not None


def test_main_entrypoint_smoke(tmp_path):
    screenshot = tmp_path / "screen.png"
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "main.py"), "--headless", "--autostart",
         "--smoke-frames", "2", "--screenshot", str(screenshot)],
        cwd=tmp_path, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert screenshot.read_bytes().startswith(b"\x89PNG")
