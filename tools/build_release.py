"""Build a reproducible source ZIP from an explicit public-file allowlist."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "main.py", "config.py", "board.py", "ai.py", "worker.py", "game.py",
    "renderer.py", "audio.py", "requirements.txt", "pytest.ini", "play.bat",
    "README.md", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md", ".gitignore",
    ".github/workflows/test.yml", "docs/PUBLISHING.md", "docs/menu.png",
    "docs/gameplay.png", "tools/build_release.py", "tests/test_board.py",
    "tests/test_ai.py", "tests/test_game.py", "tests/test_audio.py",
)


def build() -> Path:
    config_tree = ast.parse((ROOT / "config.py").read_text(encoding="utf-8"))
    version = next(ast.literal_eval(node.value) for node in config_tree.body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "VERSION"
                           for target in node.targets))
    name = f"hexxagon-vga-reborn-{version}"
    for relative in FILES:
        source = ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(f"Release file missing: {relative}")
        if source.suffix == ".py":
            ast.parse(source.read_text(encoding="utf-8"), filename=relative)
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    archive = destination / f"{name}-source.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for relative in sorted(FILES):
            info = zipfile.ZipInfo(f"{name}/{relative}", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, (ROOT / relative).read_bytes())
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(f"Created {archive.name}: {len(FILES)} files, {archive.stat().st_size:,} bytes")
    print(f"SHA256 {checksum}")
    return archive


if __name__ == "__main__":
    build()
