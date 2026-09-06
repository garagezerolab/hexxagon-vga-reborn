"""Input, screen flow and animation timing; board.py alone owns the rules."""

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any

import pygame

from ai import SearchResult, choose_move
from audio import Audio
from board import Board, CPU, HUMAN, HexLayout, Move
import config
from renderer import Renderer
from worker import AIWorker

LOG = logging.getLogger(__name__)


@dataclass
class Match:
    """Selection is UI state and is never stored inside the logical board."""

    board: Board = field(default_factory=Board.initial)
    selected: int | None = None

    @property
    def valid(self) -> dict[int, bool]:
        if self.selected is None or self.board.turn != HUMAN or self.board.winner is not None:
            return {}
        return {move.target: move.is_clone for move in self.board.legal_moves()
                if move.source == self.selected}

    def select(self, cell: int | None) -> bool:
        if (cell is not None and 0 <= cell < len(self.board.cells)
                and self.board.turn == HUMAN and self.board.winner is None
                and self.board.cells[cell] == HUMAN):
            self.selected = cell
            return True
        self.selected = None
        return False

    def apply(self, move: Move) -> Board:
        before = self.board
        self.board = before.play(move)
        self.selected = None
        return before


class Game:
    def __init__(self, difficulty: str = config.DEFAULT_DIFFICULTY,
                 depth: int = config.HARD_DEPTH, scale: int = config.WINDOW_SCALE,
                 debug: bool = config.DEBUG, sound: bool = True) -> None:
        pygame.mixer.pre_init(config.AUDIO_RATE, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption(config.TITLE)
        self.window_size = tuple(value * max(1, scale) for value in config.INTERNAL_SIZE)
        self.window = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        self.surface = pygame.Surface(config.INTERNAL_SIZE)
        self.layout = HexLayout(config.HEX_SIZE, config.BOARD_ORIGIN)
        self.renderer = Renderer(self.surface, self.layout)
        self.audio = Audio(sound)
        self.worker = AIWorker()
        self.clock = pygame.time.Clock()
        self.match = Match()
        self.difficulty = difficulty
        self.depth = max(1, depth)
        self.debug = debug
        self.screen = "menu"
        self.help_return = "menu"
        self.running = True
        self.fullscreen = False
        self.time = 0.0
        self.turn_started = 0.0
        self.outcome_started = 0.0
        self.cpu_started = 0.0
        self.mouse = (-20, -20)
        self.animation: dict[str, Any] | None = None
        self.pending_result: SearchResult | None = None
        self.last_result: SearchResult | None = None
        self.message = "SELECT A RUBY STONE"
        self.message_until = 0.0
        self._conversion_sound = False
        self._closed = False
        self._scale = 1
        self._offset = (0, 0)
        self._update_viewport()

    def _update_viewport(self) -> None:
        width, height = self.window.get_size()
        iw, ih = config.INTERNAL_SIZE
        self._scale = max(1, min(width // iw, height // ih))
        self._offset = ((width - iw * self._scale) // 2,
                        (height - ih * self._scale) // 2)

    def to_internal(self, point: tuple[int, int]) -> tuple[int, int]:
        return ((point[0] - self._offset[0]) // self._scale,
                (point[1] - self._offset[1]) // self._scale)

    def new_game(self) -> None:
        self.worker.close()
        self.match = Match()
        self.animation = None
        self.pending_result = None
        self.last_result = None
        self.screen = "playing"
        self.turn_started = self.time
        self._say("SELECT A RUBY STONE")
        self.audio.play("turn")
        LOG.info("New game: %s, hard depth %s", self.difficulty, self.depth)

    def _say(self, message: str, duration: float = 0.0) -> None:
        self.message = message
        self.message_until = self.time + duration if duration else 0.0

    def _default_message(self) -> str:
        return "CPU IS THINKING..." if self.match.board.turn == CPU else "SELECT A RUBY STONE"

    def _commit(self, move: Move) -> None:
        before = self.match.board
        converted = before.converted_by(move)
        self.match.apply(move)
        self.animation = {
            "before": before, "after": self.match.board, "move": move,
            "converted": converted, "elapsed": 0.0,
            "duration": config.MOVE_DURATION + config.CONVERSION_DURATION,
            "player": before.turn,
        }
        self._conversion_sound = False
        self.audio.play("move" if move.is_clone else "jump")
        action = "CLONE" if move.is_clone else "JUMP"
        self._say(f"{action} / {len(converted)} CONVERTED")
        LOG.debug("Player %s %s -> %s; converted %s", before.turn,
                  move.source, move.target, converted)

    def _finish_animation(self) -> None:
        before_turn = self.animation["player"] if self.animation else self.match.board.turn
        self.animation = None
        self.turn_started = self.time
        board = self.match.board
        if board.winner is not None:
            self.screen = "gameover"
            self.outcome_started = self.time
            self.audio.play({HUMAN: "victory", CPU: "defeat", 0: "draw"}[board.winner])
            self._say({"full": "BOARD COMPLETE", "extinction": "FACTION ELIMINATED",
                       "blocked": "NO LEGAL MOVES"}.get(board.end_reason, "GAME OVER"))
            LOG.info("Game over: %s, human %s CPU %s", board.end_reason,
                     board.count(HUMAN), board.count(CPU))
        elif before_turn == board.turn:
            name = "CPU" if board.turn == HUMAN else "HUMAN"
            self._say(f"{name} HAS NO MOVES / PASS", 2.8)
            self.audio.play("turn")
        else:
            self._say(self._default_message())
            self.audio.play("turn")

    def _click_board(self, point: tuple[int, int]) -> None:
        if self.animation or self.match.board.turn != HUMAN or self.match.board.winner is not None:
            return
        cell = self.layout.cell_at(point)
        valid = self.match.valid
        if cell in valid and self.match.selected is not None:
            self._commit(Move(self.match.selected, cell))
        elif self.match.select(cell):
            self.audio.play("select")
            self._say("NEAR: CLONE / FAR: JUMP")
        elif cell is not None:
            self.audio.play("error")
            self._say("SELECT YOUR RUBY STONES", 1.7)
        else:
            self._say(self._default_message())

    def _action(self, action: str) -> None:
        if action in ("new_game", "restart"):
            self.new_game()
        elif action == "quit":
            self.running = False
        elif action == "difficulty":
            index = (config.DIFFICULTIES.index(self.difficulty) + 1) % 3
            self.difficulty = config.DIFFICULTIES[index]
            self.audio.play("select")
        elif action == "sound":
            self.audio.toggle()
            self.audio.play("select")
        elif action == "menu":
            if self.screen == "gameover":
                self.screen = "menu"
            else:
                self.screen = "paused"
        elif action == "resume":
            self.screen = "playing"
        elif action == "instructions":
            self.help_return = self.screen
            self.screen = "instructions"
        elif action == "back":
            self.screen = self.help_return

    def _toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.window_size = self.window.get_size()
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        self._update_viewport()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
            size = (max(config.INTERNAL_SIZE[0], event.w),
                    max(config.INTERNAL_SIZE[1], event.h))
            self.window = pygame.display.set_mode(size, pygame.RESIZABLE)
            self._update_viewport()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.screen == "instructions":
                    self._action("back")
                elif self.screen == "playing":
                    self.screen = "paused"
                elif self.screen == "paused":
                    self.screen = "playing"
                elif self.screen == "gameover":
                    self.screen = "menu"
                else:
                    self.running = False
            elif event.key == pygame.K_m:
                self._action("sound")
            elif event.key == pygame.K_F3:
                self.debug = not self.debug
            elif event.key == pygame.K_F11:
                self._toggle_fullscreen()
            elif event.key == pygame.K_r and self.screen in ("playing", "paused", "gameover"):
                self.new_game()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.screen in ("menu", "gameover"):
                    self.new_game()
                elif self.screen == "paused":
                    self.screen = "playing"
                elif self.screen == "instructions":
                    self._action("back")
            elif self.screen == "menu" and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.difficulty = config.DIFFICULTIES[event.key - pygame.K_1]
                self.audio.play("select")
            elif event.key == pygame.K_F1 and self.screen != "instructions":
                self._action("instructions")
        elif event.type == pygame.MOUSEBUTTONDOWN:
            point = self.to_internal(event.pos)
            if event.button == 3 and self.screen == "playing":
                self.match.selected = None
            elif event.button == 1:
                for action, rect in self.renderer.buttons(self.view()).items():
                    if rect.collidepoint(point):
                        self._action(action)
                        return
                if self.screen == "playing":
                    self._click_board(point)

    def update(self, dt: float) -> None:
        self.time += dt
        if self.screen != "playing":
            return
        if self.message_until and self.time >= self.message_until:
            self._say(self._default_message())
        if self.animation is not None:
            self.animation["elapsed"] += dt
            if self.animation["elapsed"] >= config.MOVE_DURATION and not self._conversion_sound:
                if self.animation["converted"]:
                    self.audio.play("convert")
                self._conversion_sound = True
            if self.animation["elapsed"] >= self.animation["duration"]:
                self._finish_animation()
            return
        board = self.match.board
        if board.winner is not None:
            self._finish_animation()
            return
        # Normalizing also makes imported/custom states with an immobilized side safe.
        normalized = board.normalize_turn()
        if normalized.turn != board.turn:
            self.match.board = normalized
            self.match.selected = None
            self._say("NO LEGAL MOVES / TURN PASSED", 2.8)
            board = normalized
        if board.turn != CPU:
            return
        if not self.worker.busy and self.pending_result is None:
            try:
                self.worker.submit(board, self.difficulty, self.depth, config.AI_TIME_LIMIT)
                self.cpu_started = self.time
                if not self.message_until:
                    self._say("CPU IS THINKING...")
            except (OSError, RuntimeError) as exc:
                LOG.exception("Could not start CPU process")
                self._recover_cpu(str(exc))
        answer = self.worker.poll()
        if answer is not None:
            result, error = answer
            if error is not None or result is None:
                self._recover_cpu(error or "Empty AI result")
            else:
                self.pending_result = result
        if self.pending_result is not None and self.time - self.cpu_started >= config.CPU_MIN_DELAY:
            result = self.pending_result
            self.pending_result = None
            if result.move is None or not board.is_legal(result.move):
                self._recover_cpu("CPU returned an illegal move")
                result = self.pending_result
                self.pending_result = None
            if result is not None and result.move is not None:
                self.last_result = result
                LOG.debug("AI score %.1f depth %s nodes %s time %.3fs", result.score,
                          result.depth, result.nodes, result.elapsed)
                self._commit(result.move)

    def _recover_cpu(self, error: str) -> None:
        LOG.warning("CPU fallback to deterministic Easy evaluation: %s", error)
        self.worker.close()
        self.pending_result = choose_move(self.match.board, "Easy", 1, 0.05)
        self.cpu_started = self.time - config.CPU_MIN_DELAY
        self._say("CPU RECOVERED / EASY MOVE", 2.0)

    def view(self) -> dict[str, Any]:
        result = self.last_result
        hover = self.layout.cell_at(self.mouse) if self.screen == "playing" else None
        return {
            "screen": self.screen, "board": self.match.board,
            "selected": self.match.selected, "valid": self.match.valid,
            "hover": hover, "mouse": self.mouse, "time": self.time,
            "difficulty": self.difficulty, "sound": self.audio.enabled and self.audio.available,
            "busy": self.worker.busy or self.pending_result is not None,
            "message": self.message, "turn_age": self.time - self.turn_started,
            "fps": self.clock.get_fps(), "debug": self.debug,
            "ai_score": result.score if result else None,
            "ai_depth": result.depth if result else 0,
            "ai_nodes": result.nodes if result else 0,
            "animation": self.animation, "outcome_age": self.time - self.outcome_started,
        }

    def draw(self) -> None:
        focused = pygame.mouse.get_focused()
        pygame.mouse.set_visible(not focused)
        self.mouse = self.to_internal(pygame.mouse.get_pos()) if focused else (-20, -20)
        self.renderer.draw(self.view())
        self.window.fill((4, 3, 10))
        size = tuple(value * self._scale for value in config.INTERNAL_SIZE)
        self.window.blit(pygame.transform.scale(self.surface, size), self._offset)
        pygame.display.flip()

    def run(self, max_frames: int = 0, screenshot: Path | None = None) -> int:
        frames = 0
        try:
            while self.running:
                dt = min(self.clock.tick(config.FPS) / 1000.0, 0.1)
                for event in pygame.event.get():
                    self.handle_event(event)
                self.update(dt)
                self.draw()
                frames += 1
                if max_frames and frames >= max_frames:
                    break
            if screenshot is not None:
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(self.surface, str(screenshot))
                LOG.info("Saved screenshot: %s", screenshot)
        finally:
            self.close()
        return 0

    def close(self) -> None:
        if not self._closed:
            self.worker.close()
            pygame.mouse.set_visible(True)
            pygame.quit()
            self._closed = True
