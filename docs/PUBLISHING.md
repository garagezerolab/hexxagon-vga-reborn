# Publishing release 1.0.0

This project is prepared for GitHub and source distribution. It contains no
credentials, private links, or development-machine paths. The archive is built
from an explicit allowlist of public files.

## Release checks

```bash
python -m pip install -r requirements.txt
pytest
python main.py --headless --autostart --smoke-frames 5
python tools/build_release.py
```

Extract the ZIP into an empty directory and repeat the tests there. The archive
contains source, documentation, screenshots, tests, license, and CI workflow.
It excludes `.python`, `.venv`, `.uv-cache`, `.qa`, `artifacts`, and caches.

The GitHub workflow tests Windows and Linux with Python 3.10 and 3.13. Local
validation uses Python 3.13.14, Pygame 2.6.1, and pytest 9.1.1.

Suggested title: **Hexxagon VGA Reborn 1.0.0**.

> Independent Hexxagon reinterpretation in Python and Pygame. Classic 58-cell
> board, three CPU levels, alpha-beta minimax in a separate process, VGA pixel
> art, and code-generated sound. Requires Python 3.10-3.13 and Pygame.

This is a verified source release, not a standalone Windows executable.


## Native Windows and Linux builds

Build on the target OS (PyInstaller does not cross-compile):

```bash
python -m pip install -r requirements-build.txt
python tools/build_native.py
```

The builder creates a Windows ZIP or Linux tar.gz in `dist/`, plus a SHA256
checksum. Extract the whole archive and keep `_internal` beside `Hexxagon.exe`
(Windows) or `Hexxagon` (Linux). Python is bundled. Build verification includes
headless rendering and a real Hard CPU subprocess via `--smoke-cpu`.

The `Native builds` GitHub Actions workflow builds Windows x64 and Linux x64
on Ubuntu 22.04, and retains downloadable artifacts. It can be started manually
or by pushing a version tag. Linux requires a graphical desktop and compatible
system libraries (glibc 2.35 or newer for the Ubuntu 22.04 runner); it is not a
universal Linux binary. Native builds are unsigned.

### Local WSL build verified on 2026-11-06

Ubuntu-22.04 is installed in WSL2. Build user: `hexxagon` (no password configured).
Build directory: `/home/hexxagon/build/hexxagon-vga-reborn-1.0.0`.
Verified with Python 3.10.12, Pygame 2.6.1, PyInstaller 6.22.3 and glibc 2.35.
All 91 tests passed. The extracted Linux tar.gz passed rendering and real Hard
CPU subprocess checks, including executable permission and SHA256 verification.
A short graphical WSLg launch also completed; PulseAudio initialized successfully
after installing `libpulse0` and selecting `SDL_AUDIODRIVER=pulseaudio`.
This was not a full manual gameplay or audible audio-quality assessment.

To open the build environment from PowerShell:

```powershell
wsl -d Ubuntu-22.04 -u hexxagon
```

To play the extracted verification copy in WSLg:

```bash
cd /home/hexxagon/verify/Hexxagon
SDL_AUDIODRIVER=pulseaudio ./Hexxagon
```

The Linux archive is copied to the Windows project's `dist/` directory.
Extract with `tar -xzf hexxagon-vga-reborn-1.0.0-linux-x86_64.tar.gz`, then run
`./Hexxagon/Hexxagon`. Keep the complete extracted folder together.
