"""Build and package a native PyInstaller distribution on Windows or Linux."""
from pathlib import Path
import hashlib
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config


def build():
    system = platform.system().lower()
    if system not in ('windows', 'linux'):
        raise SystemExit('Run this builder on Windows or Linux; cross compilation is not supported.')
    architecture = platform.machine().lower()
    name = f'hexxagon-vga-reborn-{config.VERSION}-{system}-{architecture}'
    output = ROOT / 'dist' / name
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--onedir', '--noupx', '--name', 'Hexxagon',
               '--distpath', str(output), '--workpath', str(ROOT / 'build' / system),
               '--specpath', str(ROOT / 'build'), '--collect-data', 'pygame']
    if system == 'windows':
        command.append('--windowed')
    subprocess.run(command + [str(ROOT / 'main.py')], cwd=ROOT, check=True)
    folder = output / 'Hexxagon'
    for filename in ('LICENSE', 'README.md'):
        shutil.copy2(ROOT / filename, folder / filename)
    shutil.copytree(ROOT / 'licenses', folder / 'licenses', dirs_exist_ok=True)
    (folder / 'PLAY.txt').write_text(
        'Hexxagon VGA Reborn ' + config.VERSION + '\n\n'
        'Windows: double-click Hexxagon.exe.\n'
        'Linux: run ./Hexxagon (requires a graphical desktop).\n'
        'No Python installation is required. Keep the _internal folder next to the executable.\n'
        'Mouse: select a ruby stone, then a highlighted destination.\n'
        'Esc: pause. R: restart. M: sound. F11: fullscreen. F1: help.\n'
        'See licenses/ and THIRD-PARTY.txt for third-party notices and sources.\n', encoding='utf-8')
    shutil.copy2(ROOT / 'THIRD-PARTY.txt', folder / 'THIRD-PARTY.txt')
    executable = folder / ('Hexxagon.exe' if system == 'windows' else 'Hexxagon')
    subprocess.run([str(executable), '--headless', '--autostart', '--smoke-frames', '5'],
                   cwd=folder, check=True, timeout=30)
    subprocess.run([str(executable), '--smoke-cpu', '--difficulty', 'Hard'],
                   cwd=folder, check=True, timeout=25)
    archive = ROOT / 'dist' / (name + ('.zip' if system == 'windows' else '.tar.gz'))
    if system == 'windows':
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as package:
            for path in sorted(folder.rglob('*')):
                if path.is_file():
                    package.write(path, path.relative_to(output))
    else:
        with tarfile.open(archive, 'w:gz') as package:
            package.add(folder, arcname='Hexxagon')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(archive.name + '.sha256').write_text(
        f'{digest}  {archive.name}\n', encoding='utf-8')
    print(f'Created {archive} ({archive.stat().st_size:,} bytes)')
    return archive


if __name__ == '__main__':
    build()
