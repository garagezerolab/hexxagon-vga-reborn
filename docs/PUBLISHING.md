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

