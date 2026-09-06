# Contributing

Use Python 3.10-3.13 and install `requirements.txt`. Run `pytest` and the headless
startup command from the README before submitting a change.

Keep rules and search independent from Pygame. Rule changes need behavioral tests;
bitboard changes must preserve equivalence with `Board.play`. Rendering and
animation code must never mutate logical state. Do not add proprietary assets.

When reporting a bug, include OS, Python/Pygame versions, difficulty, move sequence,
and expected versus actual behavior. `python main.py --debug` enables logs.

Keep local environments, caches, `dist`, `.qa`, and `artifacts` out of the
repository. Rebuild releases with `python tools/build_release.py`.

