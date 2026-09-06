"""The sound generator needs no external files and tolerates unavailable audio."""

import os
os.environ["SDL_AUDIODRIVER"] = "dummy"

from array import array
from unittest.mock import Mock

import pygame

from audio import Audio, MELODIES, synthesize


def test_all_sounds_have_bounded_non_silent_pcm():
    for notes in MELODIES.values():
        samples = array("h")
        samples.frombytes(synthesize(notes, 22050, 1))
        assert len(samples) == sum(int(duration * 22050) for _, duration in notes)
        assert max(samples) > 0 > min(samples)
        assert max(abs(value) for value in samples) <= 13000
        assert samples[0] == samples[-1] == 0


def test_missing_audio_device_is_nonfatal(monkeypatch):
    monkeypatch.setattr(pygame.mixer, "get_init", lambda: None)
    monkeypatch.setattr(pygame.mixer, "init", Mock(side_effect=pygame.error("no device")))
    audio = Audio()
    assert not audio.available
    audio.play("victory")
    assert audio.toggle() is False
