"""Run with `python main.py`. No files or assets are required at runtime."""

import argparse
import logging
import multiprocessing
import os
from pathlib import Path

import config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hexxagon: original VGA-style strategy")
    parser.add_argument("--difficulty", choices=config.DIFFICULTIES,
                        default=config.DEFAULT_DIFFICULTY)
    parser.add_argument("--depth", type=int, default=config.HARD_DEPTH,
                        help="Maximum Hard search depth (iterative deepening)")
    parser.add_argument("--scale", type=int, default=config.WINDOW_SCALE)
    parser.add_argument("--debug", action="store_true", default=config.DEBUG)
    parser.add_argument("--mute", action="store_true")
    parser.add_argument("--autostart", action="store_true", help="Start a new match immediately")
    parser.add_argument("--headless", action="store_true", help="Use SDL dummy drivers for QA")
    parser.add_argument("--smoke-frames", type=int, default=0,
                        help="Exit after this many rendered frames (0: unlimited)")
    parser.add_argument("--smoke-cpu", action="store_true",
                        help="Verify a real CPU worker and exit (packaging QA)")
    parser.add_argument("--screenshot", type=Path,
                        help="Save the final internal-resolution frame on exit")
    args = parser.parse_args()
    if args.depth < 1 or args.scale < 1 or args.smoke_frames < 0:
        parser.error("depth and scale must be positive; smoke-frames cannot be negative")
    if args.headless and not args.smoke_frames:
        parser.error("--headless requires --smoke-frames to guarantee termination")
    return args


def main() -> int:
    args = parse_args()
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    try:
        from game import Game
    except ModuleNotFoundError as exc:
        if exc.name != "pygame":
            raise
        print("Pygame is not installed. Run: pip install pygame pytest")
        return 1
    if args.smoke_cpu:
        import time
        from board import Board
        from worker import AIWorker
        board = Board.initial()
        board = board.play(board.legal_moves()[0])
        worker = AIWorker()
        try:
            worker.submit(board, args.difficulty, args.depth, config.AI_TIME_LIMIT)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                answer = worker.poll()
                if answer is not None:
                    result, error = answer
                    if error or result is None or not board.is_legal(result.move):
                        raise RuntimeError(f"CPU smoke failed: {error or answer}")
                    return 0
                time.sleep(0.01)
            raise TimeoutError("CPU smoke timed out")
        finally:
            worker.close()
    game = Game(difficulty=args.difficulty, depth=args.depth, scale=args.scale,
                debug=args.debug, sound=config.SOUND_ENABLED and not args.mute)
    if args.autostart:
        game.new_game()
    return game.run(max_frames=args.smoke_frames, screenshot=args.screenshot)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
