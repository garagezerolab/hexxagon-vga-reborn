"""Original, asset-free VGA pixel art and presentation for Hexxagon.

Everything is painted at the game's internal resolution.  No system font,
antialiasing, downloaded art, or display-resolution-dependent geometry is used.
The renderer observes board state; it never changes game rules or turn state.
"""

from __future__ import annotations

import math
import random
from typing import Any

import pygame

from board import Board, COORDS, HexLayout


# A deliberately small, shared VGA-style palette.  Stone ramps are below.
INK = (7, 6, 15)
SPACE = (12, 10, 24)
PANEL = (29, 24, 43)
PANEL_INNER = (21, 19, 33)
PURPLE = (64, 47, 79)
LILAC = (124, 96, 139)
MUTED = (141, 129, 157)
TEXT = (222, 213, 226)
CREAM = (255, 232, 189)
GOLD = (222, 163, 83)
GOLD_DARK = (105, 70, 55)
GREEN = (137, 217, 144)
RED = (241, 83, 96)
CYAN = (95, 224, 232)


# Each glyph is an original 5-by-7 bitmap.  Keeping the font in code makes
# launch deterministic on Windows, macOS, Linux, and headless SDL drivers.
_GLYPHS = {
    "A": "01110/11011/11011/11111/11011/11011/11011",
    "B": "11110/11011/11011/11110/11011/11011/11110",
    "C": "01111/11000/11000/11000/11000/11000/01111",
    "D": "11110/11011/11011/11011/11011/11011/11110",
    "E": "11111/11000/11000/11110/11000/11000/11111",
    "F": "11111/11000/11000/11110/11000/11000/11000",
    "G": "01111/11000/11000/11011/11011/11011/01110",
    "H": "11011/11011/11011/11111/11011/11011/11011",
    "I": "11111/00100/00100/00100/00100/00100/11111",
    "J": "00111/00011/00011/00011/11011/11011/01110",
    "K": "11011/11010/11100/11100/11010/11011/11011",
    "L": "11000/11000/11000/11000/11000/11000/11111",
    "M": "10001/11011/11111/10101/10001/10001/10001",
    "N": "11001/11001/11101/11111/11011/11011/11001",
    "O": "01110/11011/11011/11011/11011/11011/01110",
    "P": "11110/11011/11011/11110/11000/11000/11000",
    "Q": "01110/11011/11011/11011/11111/01110/00011",
    "R": "11110/11011/11011/11110/11100/11010/11011",
    "S": "01111/11000/11000/01110/00011/00011/11110",
    "T": "11111/00100/00100/00100/00100/00100/00100",
    "U": "11011/11011/11011/11011/11011/11011/01110",
    "V": "11011/11011/11011/11011/11011/01010/00100",
    "W": "10001/10001/10001/10101/11111/11011/10001",
    "X": "11011/11011/01010/00100/01010/11011/11011",
    "Y": "11011/11011/11011/01110/00100/00100/00100",
    "Z": "11111/00011/00110/00100/01100/11000/11111",
    "0": "01110/11011/11011/11011/11011/11011/01110",
    "1": "00100/01100/00100/00100/00100/00100/01110",
    "2": "01110/11011/00011/00110/01100/11000/11111",
    "3": "11110/00011/00011/01110/00011/00011/11110",
    "4": "00011/00111/01011/11011/11111/00011/00011",
    "5": "11111/11000/11000/11110/00011/00011/11110",
    "6": "01110/11000/11000/11110/11011/11011/01110",
    "7": "11111/00011/00010/00110/00100/01100/01100",
    "8": "01110/11011/11011/01110/11011/11011/01110",
    "9": "01110/11011/11011/01111/00011/00011/01110",
    " ": "00000/00000/00000/00000/00000/00000/00000",
    ".": "00000/00000/00000/00000/00000/00110/00110",
    ",": "00000/00000/00000/00000/00110/00110/00100",
    ":": "00000/00110/00110/00000/00110/00110/00000",
    ";": "00000/00110/00110/00000/00110/00110/00100",
    "!": "00100/00100/00100/00100/00100/00000/00100",
    "?": "01110/11011/00011/00110/00100/00000/00100",
    "-": "00000/00000/00000/11111/00000/00000/00000",
    "_": "00000/00000/00000/00000/00000/00000/11111",
    "+": "00000/00100/00100/11111/00100/00100/00000",
    "=": "00000/00000/11111/00000/11111/00000/00000",
    "/": "00001/00011/00010/00100/01000/11000/10000",
    "\\": "10000/11000/01000/00100/00010/00011/00001",
    "(": "00010/00100/01100/01100/01100/00100/00010",
    ")": "01000/00100/00110/00110/00110/00100/01000",
    "[": "01110/01100/01100/01100/01100/01100/01110",
    "]": "01110/00110/00110/00110/00110/00110/01110",
    "<": "00010/00100/01000/10000/01000/00100/00010",
    ">": "01000/00100/00010/00001/00010/00100/01000",
    "'": "00110/00110/00100/00000/00000/00000/00000",
    '"': "01010/01010/01010/00000/00000/00000/00000",
    "%": "11001/11010/00010/00100/01000/01011/10011",
    "#": "01010/11111/01010/01010/11111/01010/00000",
    "*": "00000/10101/01110/11111/01110/10101/00000",
    "|": "00100/00100/00100/00100/00100/00100/00100",
}

_MICRO = {
    "0": "111/101/101/101/111", "1": "010/110/010/010/111",
    "2": "110/001/010/100/111", "3": "110/001/010/001/110",
    "4": "101/101/111/001/001", "5": "111/100/110/001/110",
    "6": "011/100/111/101/111", "7": "111/001/010/010/010",
    "8": "111/101/111/101/111", "9": "111/101/111/001/110",
    "-": "000/000/111/000/000", ",": "000/000/000/010/100",
}


class PixelFont:
    """A cached bitmap font, always rendered on an integer pixel grid."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, tuple[int, ...], int], pygame.Surface] = {}

    @staticmethod
    def width(text: str, scale: int = 1) -> int:
        return max(0, len(text) * 6 - 1) * scale

    def paint(
        self, surface: pygame.Surface, text: str, x: float, y: float,
        color: tuple[int, ...] = TEXT, scale: int = 1, align: str = "left",
    ) -> pygame.Rect:
        text = str(text).upper()
        width = self.width(text, scale)
        x = round(x - (width // 2 if align == "center" else width if align == "right" else 0))
        y = round(y)
        for index, char in enumerate(text):
            key = (char, color, scale)
            glyph = self._cache.get(key)
            if glyph is None:
                glyph = pygame.Surface((5 * scale, 7 * scale), pygame.SRCALPHA)
                for row, line in enumerate(_GLYPHS.get(char, _GLYPHS["?"]).split("/")):
                    for column, bit in enumerate(line):
                        if bit == "1":
                            glyph.fill(color, (column * scale, row * scale, scale, scale))
                self._cache[key] = glyph
            surface.blit(glyph, (x + index * 6 * scale, y))
        return pygame.Rect(x, y, width, 7 * scale)


def _hex(center: tuple[float, float], radius: float) -> list[tuple[int, int]]:
    return [
        (round(center[0] + radius * math.cos(k * math.pi / 3)),
         round(center[1] + radius * math.sin(k * math.pi / 3)))
        for k in range(6)
    ]


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


class Renderer:
    """Paint the complete UI from a read-only controller view dictionary."""

    def __init__(self, surface: pygame.Surface, layout: HexLayout) -> None:
        self.surface = surface
        self.layout = layout
        self.font = PixelFont()
        self._stones: dict[tuple[int, int], pygame.Surface] = {}
        self._background = self._make_background(surface.get_size())
        self._shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        self._shade.fill((3, 2, 10, 177))
        self._menu_layout = HexLayout(size=7.2, origin=(105, 146))
        self._indices = {coord: i for i, coord in enumerate(COORDS)}
        self._full_coords = tuple(
            (q, r) for q in range(-4, 5) for r in range(-4, 5)
            if max(abs(q), abs(r), abs(q + r)) <= 4
        )

    def buttons(self, view: dict[str, Any]) -> dict[str, pygame.Rect]:
        """The exact live hitboxes; the controller handles their actions."""
        screen = view.get("screen", "menu")
        if screen == "menu":
            return {
                "new_game": pygame.Rect(220, 96, 146, 23),
                "difficulty": pygame.Rect(220, 124, 146, 21),
                "instructions": pygame.Rect(220, 150, 146, 21),
                "sound": pygame.Rect(220, 176, 146, 21),
                "quit": pygame.Rect(220, 202, 146, 21),
            }
        if screen == "paused":
            return {
                "resume": pygame.Rect(111, 90, 162, 22),
                "new_game": pygame.Rect(111, 118, 162, 22),
                "instructions": pygame.Rect(111, 146, 162, 22),
                "quit": pygame.Rect(111, 174, 162, 22),
            }
        if screen == "instructions":
            return {"back": pygame.Rect(146, 195, 92, 19)}
        if screen == "gameover":
            return {
                "restart": pygame.Rect(97, 171, 90, 20),
                "menu": pygame.Rect(197, 171, 90, 20),
            }
        if screen == "playing":
            return {
                "restart": pygame.Rect(230, 155, 65, 18),
                "menu": pygame.Rect(301, 155, 65, 18),
                "sound": pygame.Rect(230, 178, 136, 18),
            }
        return {}

    def draw(self, view: dict[str, Any]) -> None:
        self.surface.blit(self._background, (0, 0))
        screen = view.get("screen", "menu")
        if screen in ("menu", "instructions"):
            self._draw_menu(view)
        else:
            self._draw_game(view)
        if screen == "paused":
            self._draw_paused(view)
        elif screen == "instructions":
            self._draw_instructions(view)
        elif screen == "gameover":
            self._draw_gameover(view)
        if view.get("debug") and screen in ("playing", "paused", "gameover"):
            self._draw_debug(view)
        self._draw_cursor(view)

    def _text(self, text: str, x: float, y: float, color: tuple[int, ...] = TEXT,
              scale: int = 1, align: str = "left") -> None:
        self.font.paint(self.surface, text, x, y, color, scale, align)

    def _make_background(self, size: tuple[int, int]) -> pygame.Surface:
        surface = pygame.Surface(size)
        surface.fill(SPACE)
        rng = random.Random(1993)
        # Restrained nebula stippling, with no gradients or noisy full-screen texture.
        for _ in range(1400):
            x = rng.randrange(size[0])
            y = rng.randrange(size[1])
            ridge = 143 - 0.30 * x + 22 * math.sin(x / 74)
            if abs(y - ridge) < rng.randrange(4, 53):
                surface.set_at((x, y), rng.choice(((20, 14, 34), (23, 16, 38), (18, 14, 31))))
        for _ in range(95):
            x = rng.randrange(8, size[0] - 8)
            y = rng.randrange(8, size[1] - 8)
            color = rng.choice(((60, 48, 77), (76, 66, 91), (97, 83, 110), (134, 118, 140)))
            surface.set_at((x, y), color)
            if rng.random() < 0.09:
                pygame.draw.line(surface, (44, 35, 60), (x - 2, y), (x + 2, y))
                pygame.draw.line(surface, (44, 35, 60), (x, y - 2), (x, y + 2))
                surface.set_at((x, y), color)
        pygame.draw.rect(surface, (44, 31, 54), (3, 3, size[0] - 6, size[1] - 6), 1)
        # Cut-corner brackets and small bronze rivets frame every screen.
        for x, sx in ((3, 1), (size[0] - 4, -1)):
            for y, sy in ((3, 1), (size[1] - 4, -1)):
                pygame.draw.line(surface, GOLD_DARK, (x, y), (x + sx * 13, y))
                pygame.draw.line(surface, GOLD_DARK, (x, y), (x, y + sy * 10))
                surface.set_at((x + sx * 2, y + sy * 2), GOLD)
        return surface

    def _panel(self, rect: pygame.Rect | tuple[int, int, int, int], accent: bool = False) -> None:
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.surface, INK, rect.move(2, 3))
        pygame.draw.rect(self.surface, GOLD_DARK if accent else PURPLE, rect)
        pygame.draw.rect(self.surface, PANEL, rect.inflate(-2, -2))
        pygame.draw.line(self.surface, GOLD if accent else LILAC,
                         (rect.left + 1, rect.top + 1), (rect.right - 2, rect.top + 1))
        pygame.draw.line(self.surface, (85, 66, 97),
                         (rect.left + 1, rect.top + 2), (rect.left + 1, rect.bottom - 2))
        pygame.draw.line(self.surface, (15, 12, 23),
                         (rect.left + 1, rect.bottom - 2), (rect.right - 2, rect.bottom - 2))
        for x in (rect.left + 4, rect.right - 5):
            for y in (rect.top + 4, rect.bottom - 5):
                self.surface.set_at((x, y), GOLD_DARK)

    def _button(self, rect: pygame.Rect, label: str, view: dict[str, Any], primary: bool = False) -> None:
        hovered = rect.collidepoint(view.get("mouse", (-1, -1)))
        pygame.draw.rect(self.surface, INK, rect.move(1, 2))
        pygame.draw.rect(self.surface, GOLD if hovered else (126, 92, 88) if primary else (92, 72, 113), rect)
        inner = rect.inflate(-2, -2)
        pygame.draw.rect(self.surface, (74, 49, 59) if primary else (58, 43, 75) if hovered else (43, 34, 58), inner)
        pygame.draw.line(self.surface, (174, 130, 110) if primary else (113, 87, 133),
                         (rect.x + 2, rect.y + 2), (rect.right - 3, rect.y + 2))
        pygame.draw.line(self.surface, (25, 18, 34),
                         (rect.x + 2, rect.bottom - 3), (rect.right - 3, rect.bottom - 3))
        color = CREAM if hovered or primary else TEXT
        self._text(label, rect.centerx, rect.centery - 3, color, align="center")
        if hovered and self.font.width(label) < rect.width - 25:
            cx, cy = rect.x + 8, rect.centery
            pygame.draw.polygon(self.surface, GOLD, ((cx, cy - 2), (cx + 3, cy), (cx, cy + 2)))

    def _title(self) -> None:
        title, scale, x, y = "HEXXAGON", 5, 75, 25
        # Four-pixel extrusion and a per-scanline golden face give the logo
        # the heavy, embossed character of a 1990s title screen.
        for dx, dy in ((4, 5), (3, 4), (2, 3)):
            self.font.paint(self.surface, title, x + dx, y + dy, (44, 24, 44), scale)
        rows = ((255, 232, 189), (245, 201, 133), (233, 175, 99),
                (206, 133, 71), (180, 102, 59), (223, 155, 84), (244, 191, 116))
        for index, char in enumerate(title):
            for row, line in enumerate(_GLYPHS[char].split("/")):
                for col, bit in enumerate(line):
                    if bit == "1":
                        box = pygame.Rect(x + index * 30 + col * 5, y + row * 5, 5, 5)
                        pygame.draw.rect(self.surface, rows[row], box)
                        if row == 0 or _GLYPHS[char].split("/")[row - 1][col] == "0":
                            pygame.draw.line(self.surface, CREAM, box.topleft, (box.right - 1, box.top))
        self._stone((40, 44), 1, 13)
        self._stone((343, 44), 2, 13)
        self._sparkle((33, 34), CREAM, 3)
        self._sparkle((336, 34), (212, 255, 255), 3)
        self._text("DOS STRATEGY REBORN", 192, 73, MUTED, align="center")
        pygame.draw.line(self.surface, GOLD_DARK, (49, 76), (124, 76))
        pygame.draw.line(self.surface, GOLD_DARK, (260, 76), (335, 76))

    def _draw_menu(self, view: dict[str, Any]) -> None:
        self._title()
        # The ornamental board is an actual geometrical board rendered at
        # a smaller scale, so the game's identity is visible before starting.
        board = view.get("board")
        self._draw_board(board, self._menu_layout, {}, menu=True)
        t = float(view.get("time", 0.0))
        for index, (x, y) in enumerate(((36, 123), (175, 170), (67, 190), (159, 104))):
            if math.sin(t * 1.7 + index * 1.9) > 0.35:
                self._sparkle((x, y), (133, 108, 139), 2)
        pygame.draw.line(self.surface, (70, 47, 70), (205, 97), (205, 219))
        for y in (97, 219):
            pygame.draw.polygon(self.surface, GOLD_DARK, ((205, y - 2), (208, y), (205, y + 2), (202, y)))
        self._text("CLONE. JUMP. CONQUER.", 106, 207, GOLD, align="center")
        self._text("ONE BOARD. NO MERCY.", 106, 220, MUTED, align="center")
        labels = {
            "new_game": "NEW GAME",
            "difficulty": f"CPU: {view.get('difficulty', 'Normal')}",
            "instructions": "HOW TO PLAY",
            "sound": f"SOUND: {'ON' if view.get('sound', True) else 'OFF'}",
            "quit": "QUIT",
        }
        # Instructions reuse this scene beneath a modal; keep the menu's
        # controls visible in the background but noninteractive there.
        menu_view = dict(view, screen="menu")
        for name, rect in self.buttons(menu_view).items():
            self._button(rect, labels[name], view, primary=name == "new_game")
        self._text("01", 13, 14, GOLD_DARK)
        self._text("VGA", 371, 14, GOLD_DARK, align="right")

    def _draw_game(self, view: dict[str, Any]) -> None:
        board = view.get("board")
        self._text("HEXXAGON", 13, 10, GOLD, scale=2)
        self._text("CLASSIC / 58 CELLS", 370, 14, MUTED, align="right")
        pygame.draw.line(self.surface, GOLD_DARK, (14, 28), (370, 28))
        self._draw_board(board, self.layout, view)
        pygame.draw.line(self.surface, (61, 43, 70), (211, 40), (211, 226))
        self._panel((220, 35, 154, 199))
        self._text("COMMAND", 297, 40, GOLD, align="center")
        turn = getattr(board, "turn", 1)
        for player, y, name, subtitle, color in (
            (1, 51, "HUMAN", "RUBY", RED),
            (2, 86, "CPU", "CYAN", CYAN),
        ):
            active = turn == player and getattr(board, "winner", None) is None
            rect = pygame.Rect(230, y, 136, 29)
            pygame.draw.rect(self.surface, color if active else (62, 48, 75), rect, 1)
            pygame.draw.rect(self.surface, PANEL_INNER, rect.inflate(-2, -2))
            if active:
                pygame.draw.rect(self.surface, color, (231, y + 2, 2, 25))
            self._stone((244, y + 15), player, 7)
            self._text(name, 257, y + 5, TEXT)
            self._text(subtitle, 257, y + 17, color)
            count = board.count(player) if board is not None else 3
            self._text(f"{count:02d}", 358, y + 7, color, scale=2, align="right")
        ribbon = pygame.Rect(230, 121, 136, 16)
        pygame.draw.rect(self.surface, (44, 32, 52), ribbon)
        turn_age = float(view.get("turn_age", 1.0))
        if turn_age < 0.36:
            pygame.draw.rect(self.surface, (86, 54, 72) if turn == 1 else (35, 77, 88),
                             (ribbon.x, ribbon.y, round(ribbon.w * _clamp(turn_age / 0.36)), ribbon.h))
        busy = bool(view.get("busy"))
        if getattr(board, "winner", None) is not None:
            turn_label, turn_color = "MATCH COMPLETE", GOLD
        elif view.get("animation"):
            turn_label, turn_color = "CONVERTING...", GOLD
        elif busy or turn == 2:
            turn_label, turn_color = "CPU THINKING", CYAN
        else:
            turn_label, turn_color = "YOUR MOVE", RED
        self._text(turn_label, 298, 126, turn_color, align="center")
        self._text(f"CPU: {view.get('difficulty', 'Normal')}", 231, 143, MUTED)
        if busy:
            frame = int(float(view.get("time", 0)) * 7) % 4
            for index in range(4):
                pygame.draw.rect(self.surface, CYAN if index == frame else (48, 66, 79),
                                 (342 + index * 6, 144, 3, 3))
        playing_view = dict(view, screen="playing")
        labels = {"restart": "RESTART", "menu": "MENU",
                  "sound": f"SOUND: {'ON' if view.get('sound', True) else 'OFF'}"}
        for name, rect in self.buttons(playing_view).items():
            self._button(rect, labels[name], view)
        pygame.draw.line(self.surface, (71, 52, 80), (231, 201), (365, 201))
        message = str(view.get("message") or ("CHOOSE A RUBY STONE." if turn == 1 else "THE CYAN ARMY IS THINKING."))
        for row, line in enumerate(self._wrap(message, 22)[:3]):
            self._text(line, 231, 206 + row * 8, MUTED)
        self._marker((47, 233), True)
        self._text("CLONE", 55, 230, GREEN)
        self._marker((105, 233), False)
        self._text("JUMP", 114, 230, GOLD)
        self._text("ESC PAUSE", 199, 230, MUTED, align="right")

    def _tile(self, center: tuple[float, float], radius: float,
              hover: bool = False, hole: bool = False) -> None:
        x, y = center
        outer = _hex(center, radius)
        pygame.draw.polygon(self.surface, INK, [(px + 1, py + 3) for px, py in outer])
        pygame.draw.polygon(self.surface, (85, 56, 67), [(px, py + 2) for px, py in outer])
        pygame.draw.polygon(self.surface, (31, 22, 40), outer)
        face = _hex(center, radius - 1)
        if hole:
            pygame.draw.polygon(self.surface, (72, 48, 68), face)
            pygame.draw.polygon(self.surface, (4, 4, 10), _hex((x, y + 1), radius - 2))
            pygame.draw.lines(self.surface, (102, 66, 83), False, [face[2], face[3], face[4]], 1)
            pygame.draw.line(self.surface, (21, 17, 32), (round(x - 3), round(y + 3)), (round(x + 3), round(y + 3)))
            return
        pygame.draw.polygon(self.surface, (77, 59, 90) if hover else (57, 44, 71), face)
        pygame.draw.polygon(self.surface, (85, 65, 95) if hover else (65, 50, 77),
                            [face[3], face[4], face[5], (round(x + 2), round(y))])
        pygame.draw.lines(self.surface, (153, 116, 130) if hover else (121, 89, 111),
                          False, [face[3], face[4], face[5], face[0]], 1)
        pygame.draw.lines(self.surface, (31, 26, 43), False, [face[0], face[1], face[2], face[3]], 1)

    def _draw_board(self, board: Any, layout: HexLayout, view: dict[str, Any], menu: bool = False) -> None:
        if board is None:
            cells = Board.initial().cells
        else:
            cells = board.cells
        # A title-screen position stays decorative even after returning from
        # a completed match; its six starting stones form a balanced emblem.
        if menu:
            cells = Board.initial().cells
        radius = layout.size
        centers = [layout.to_pixel(coord) for coord in COORDS]
        selected, hovered = view.get("selected"), view.get("hover")
        valid = view.get("valid") or {}
        for coord in sorted(self._full_coords, key=lambda item: layout.to_pixel(item)[1]):
            index = self._indices.get(coord)
            center = layout.to_pixel(coord)
            self._tile(center, radius, hover=index is not None and index == hovered, hole=index is None)
            if index is not None and index in valid:
                self._marker(center, bool(valid[index]), bright=index == hovered)
        animation = view.get("animation") if not menu else None
        converted: tuple[int, ...] = ()
        phase, progress = 0.0, 0.0
        if animation:
            elapsed = max(0.0, float(animation["elapsed"]))
            duration = max(0.01, float(animation["duration"]))
            landing = duration * 0.52
            progress = _clamp(elapsed / landing)
            phase = _clamp((elapsed - landing) / (duration - landing))
            cells = animation["before"].cells if progress < 1 else animation["after"].cells
            converted = tuple(animation.get("converted", ()))
        for index in sorted(range(len(COORDS)), key=lambda i: centers[i][1]):
            value = cells[index]
            if animation and progress < 1:
                if index == animation["move"].source and not animation["move"].is_clone:
                    continue
            stone_radius = 5 if menu else 8
            if animation and progress >= 1 and index in converted:
                order = converted.index(index)
                local = _clamp((phase - order * 0.055) / 0.72)
                if local < 0.5:
                    value = animation["before"].cells[index]
                    stone_radius = max(1, round(8 * (1 - 2 * local)))
                else:
                    value = animation["player"]
                    stone_radius = max(1, round(8 * (2 * local - 1)))
                if 0.05 < local < 0.9:
                    self._ring(centers[index], round(8 + 3 * math.sin(local * math.pi)),
                               CREAM if value == 1 else (191, 255, 255))
            if value:
                self._stone(centers[index], value, stone_radius)
            if index == selected and not menu and not animation:
                color = CREAM if int(float(view.get("time", 0)) * 5) % 2 else GOLD
                self._ring(centers[index], 10, color)
                cx, cy = centers[index]
                self._sparkle((round(cx - 6), round(cy - 9)), CREAM, 2)
        if animation and progress < 1:
            move = animation["move"]
            sx, sy = centers[move.source]
            tx, ty = centers[move.target]
            smooth = progress * progress * (3 - 2 * progress)
            x, y = sx + (tx - sx) * smooth, sy + (ty - sy) * smooth
            y -= math.sin(progress * math.pi) * (7 if move.is_clone else 16)
            stone_radius = max(2, round(3 + 5 * progress)) if move.is_clone else 8
            self._stone((x, y), animation["player"], stone_radius)
            self._sparkle((round(x - stone_radius + 1), round(y - stone_radius)), CREAM, 2)
        elif animation and phase < 0.45:
            center = centers[animation["move"].target]
            self._ring(center, 9 + round(phase * 7), GOLD if animation["player"] == 1 else CYAN)
        if not menu and view.get("debug"):
            for coord, center in zip(COORDS, centers):
                self._micro_text(f"{coord[0]},{coord[1]}", center[0], center[1] + 4)

    def _stone(self, center: tuple[float, float], player: int, radius: int = 8) -> None:
        radius = max(1, int(radius))
        key = (int(player), radius)
        stone = self._stones.get(key)
        if stone is None:
            stone = self._make_stone(player, radius)
            self._stones[key] = stone
        self.surface.blit(stone, (round(center[0] - radius - 4), round(center[1] - radius - 5)))

    @staticmethod
    def _make_stone(player: int, radius: int) -> pygame.Surface:
        r = radius
        result = pygame.Surface((2 * r + 9, 2 * r + 11), pygame.SRCALPHA)
        cx, cy = r + 4, r + 3
        if player == 1:
            edge, dark, base, lit, shine, white = (
                (51, 8, 24), (118, 13, 38), (193, 30, 55),
                (242, 64, 77), (255, 143, 139), (255, 226, 197),
            )
        else:
            edge, dark, base, lit, shine, white = (
                (5, 37, 52), (9, 83, 112), (17, 153, 188),
                (43, 210, 227), (145, 248, 245), (221, 255, 247),
            )
        pygame.draw.ellipse(result, (4, 4, 11, 230), (cx - r + 1, cy + r - 2, 2 * r + 2, max(3, r // 2 + 2)))
        pygame.draw.circle(result, edge, (cx, cy), r)
        if r < 3:
            pygame.draw.circle(result, shine, (cx, cy), max(1, r - 1))
            return result
        pygame.draw.circle(result, dark, (cx, cy), r - 1)
        pygame.draw.circle(result, base, (cx - 1, cy - 1), r - 2)
        pygame.draw.circle(result, lit, (cx - max(1, r // 4), cy - max(1, r // 4)), max(1, r - 3))
        # Deliberately angular facets, each contained inside the circular rim.
        pygame.draw.polygon(result, base, (
            (cx + r // 3, cy - r + 3), (cx + r - 2, cy - 1),
            (cx + r - 3, cy + r // 2), (cx, cy + r - 2), (cx + r // 3, cy),
        ))
        pygame.draw.ellipse(result, shine, (cx - r + 3, cy - r + 2, max(2, r - 1), max(2, r // 2)))
        pygame.draw.rect(result, white, (cx - max(1, r // 3), cy - r + 2, max(1, r // 3), 1 if r < 10 else 2))
        pygame.draw.line(result, dark, (cx - r // 2, cy + r - 2), (cx + r // 2, cy + r - 2))
        result.set_at((cx + r - 2, cy), lit)
        return result

    def _marker(self, center: tuple[float, float], clone: bool, bright: bool = False) -> None:
        x, y = round(center[0]), round(center[1])
        if clone:
            pygame.draw.polygon(self.surface, (35, 61, 49), ((x, y - 4), (x + 4, y), (x, y + 4), (x - 4, y)))
            pygame.draw.polygon(self.surface, CREAM if bright else GREEN,
                                ((x, y - 2), (x + 2, y), (x, y + 2), (x - 2, y)))
        else:
            pygame.draw.polygon(self.surface, CREAM if bright else GOLD, _hex((x, y), 4), 1)
            self.surface.set_at((x, y), (44, 31, 41))

    def _ring(self, center: tuple[float, float], radius: int, color: tuple[int, ...]) -> None:
        points = _hex(center, radius)
        # Short segments read as a targeting bracket without covering stones.
        for index, (x, y) in enumerate(points):
            nx, ny = points[(index + 1) % 6]
            end = (round(x + (nx - x) * 0.36), round(y + (ny - y) * 0.36))
            pygame.draw.line(self.surface, color, (x, y), end)

    def _sparkle(self, center: tuple[int, int], color: tuple[int, ...], radius: int) -> None:
        x, y = center
        pygame.draw.line(self.surface, color, (x - radius, y), (x + radius, y))
        pygame.draw.line(self.surface, color, (x, y - radius), (x, y + radius))
        self.surface.set_at((x, y), CREAM)

    def _draw_paused(self, view: dict[str, Any]) -> None:
        self.surface.blit(self._shade, (0, 0))
        self._panel((79, 46, 226, 160), accent=True)
        self._text("PAUSED", 192, 60, GOLD, 2, "center")
        self._text("THE BOARD CAN WAIT.", 192, 79, MUTED, align="center")
        labels = {"resume": "RESUME", "new_game": "NEW GAME", "instructions": "HOW TO PLAY", "quit": "QUIT"}
        for name, rect in self.buttons(view).items():
            self._button(rect, labels[name], view, primary=name == "resume")

    def _draw_instructions(self, view: dict[str, Any]) -> None:
        self.surface.blit(self._shade, (0, 0))
        self._panel((30, 26, 324, 198), accent=True)
        self._text("HOW TO PLAY", 192, 38, GOLD, 2, "center")
        self._text("YOU ARE RUBY. THE COMPUTER IS CYAN.", 192, 63, TEXT, align="center")
        for clone, x in ((True, 43), (False, 199)):
            pygame.draw.rect(self.surface, PANEL_INNER, (x, 80, 142, 46))
            self._tile((x + 27, 98), 11)
            self._tile((x + 112, 98), 11)
            if clone:
                self._stone((x + 27, 98), 1)
            else:
                self._ring((x + 27, 98), 7, GOLD_DARK)
            self._stone((x + 112, 98), 1)
            pygame.draw.line(self.surface, GREEN if clone else GOLD, (x + 50, 97), (x + 87, 97))
            pygame.draw.polygon(self.surface, GREEN if clone else GOLD,
                                ((x + 88, 97), (x + 83, 94), (x + 83, 100)))
            self._text("1 STEP: CLONE" if clone else "2 STEPS: JUMP", x + 71, 115,
                       GREEN if clone else GOLD, align="center")
        lines = (
            "CLICK A RUBY STONE, THEN A LIT HEX.",
            "ADJACENT ENEMIES BECOME YOUR COLOR.",
            "NO LEGAL MOVE? YOUR TURN IS SKIPPED.",
            "FULL, ELIMINATED OR BOTH BLOCKED: END.",
            "MOST STONES WINS. EQUAL SCORES DRAW.",
        )
        for index, line in enumerate(lines):
            self._text(line, 192, 129 + index * 10, TEXT, align="center")
        self._text("ESC PAUSE / R RESTART / M SOUND / F3 DEBUG", 192, 181, MUTED, align="center")
        self._button(self.buttons(view)["back"], "BACK", view)

    def _draw_gameover(self, view: dict[str, Any]) -> None:
        self.surface.blit(self._shade, (0, 0))
        board = view.get("board")
        winner = getattr(board, "winner", 0)
        age = float(view.get("outcome_age", 0))
        if winner == 1:
            # Finite, repeatable little victory sparks; no state or random
            # number generation is tied to the render frame rate.
            for index in range(24):
                phase = (age * 0.65 + index * 0.043) % 1
                angle = index * 2.39996
                x = round(192 + math.cos(angle) * (38 + phase * 126))
                y = round(106 + math.sin(angle) * (23 + phase * 75))
                if phase < 0.78:
                    self._sparkle((x, y), GOLD if index % 2 else RED, 1)
        self._panel((73, 56, 238, 143), accent=True)
        heading = "VICTORY" if winner == 1 else "DEFEAT" if winner == 2 else "DRAW GAME"
        color = GOLD if winner == 1 else CYAN if winner == 2 else TEXT
        intro_offset = round(10 * (1 - _clamp(age / 0.25)) ** 2)
        self._text(heading, 192, 72 - intro_offset, color, 2, "center")
        subtitle = "THE BOARD IS YOURS." if winner == 1 else "THE CYAN ARMY PREVAILS." if winner == 2 else "AN EVENLY MATCHED BATTLE."
        self._text(subtitle, 192, 95, MUTED, align="center")
        pygame.draw.line(self.surface, (82, 59, 81), (94, 109), (290, 109))
        self._stone((113, 131), 1, 10)
        self._text("HUMAN", 133, 119, RED)
        self._text(f"{board.count(1) if board is not None else 0:02d}", 133, 131, CREAM, 2)
        self._stone((224, 131), 2, 10)
        self._text("CPU", 244, 119, CYAN)
        self._text(f"{board.count(2) if board is not None else 0:02d}", 244, 131, CREAM, 2)
        reason = str(getattr(board, "end_reason", "") or "")
        reason_map = {
            "full": "THE BOARD IS FULL.",
            "extinction": "ONE ARMY HAS BEEN ELIMINATED.",
            "blocked": "NEITHER ARMY CAN MOVE.",
        }
        label = reason_map.get(reason, "FINAL STONE COUNT")
        self._text(label, 192, 155, MUTED, align="center")
        for name, rect in self.buttons(view).items():
            self._button(rect, "PLAY AGAIN" if name == "restart" else "MENU", view, primary=name == "restart")

    def _micro_text(self, text: str, x: float, y: float) -> None:
        left, top = round(x - (len(text) * 4 - 1) / 2), round(y)
        pygame.draw.rect(self.surface, (12, 9, 20), (left - 1, top - 1, len(text) * 4 + 1, 7))
        for index, char in enumerate(text):
            for row, line in enumerate(_MICRO.get(char, _MICRO["-"]).split("/")):
                for col, bit in enumerate(line):
                    if bit == "1":
                        self.surface.set_at((left + index * 4 + col, top + row), CREAM)

    def _draw_debug(self, view: dict[str, Any]) -> None:
        self._panel((8, 31, 201, 34))
        board = view.get("board")
        score = view.get("ai_score")
        label = "--" if score is None else f"{score:+.1f}"
        lines = (
            f"FPS {view.get('fps', 0):.0f} TURN {getattr(board, 'turn', 0)} PLY {getattr(board, 'ply', 0)}",
            f"AI {label} D{view.get('ai_depth', 0)} N{view.get('ai_nodes', 0)}",
            f"SEL {view.get('selected')} VALID {len(view.get('valid') or {})}",
        )
        for index, line in enumerate(lines):
            self._text(line[:31], 14, 37 + index * 9, CREAM if index == 0 else MUTED)

    def _draw_cursor(self, view: dict[str, Any]) -> None:
        mouse = view.get("mouse", (-1, -1))
        if not mouse or not self.surface.get_rect().collidepoint(mouse):
            return
        x, y = round(mouse[0]), round(mouse[1])
        active = any(rect.collidepoint(mouse) for rect in self.buttons(view).values())
        active = active or (view.get("screen") == "playing" and view.get("hover") in (view.get("valid") or {}))
        points = ((x, y), (x, y + 11), (x + 3, y + 8), (x + 6, y + 12),
                  (x + 8, y + 11), (x + 5, y + 7), (x + 10, y + 7))
        pygame.draw.polygon(self.surface, INK, [(px + 1, py + 1) for px, py in points])
        pygame.draw.polygon(self.surface, GOLD if active else TEXT, points)
        pygame.draw.polygon(self.surface, INK, points, 1)
        pygame.draw.line(self.surface, CREAM, (x + 1, y + 2), (x + 1, y + 8))

    @staticmethod
    def _wrap(text: str, width: int) -> list[str]:
        lines: list[str] = []
        current = ""
        for word in text.upper().split():
            # Long diagnostic words are split as well, never painted past
            # the console border.
            while len(word) > width:
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:width])
                word = word[width:]
            if len(current) + len(word) + bool(current) > width:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            lines.append(current)
        return lines or [""]
