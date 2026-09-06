"""Original PC-speaker/AdLib-inspired effects, synthesized entirely in memory."""

from array import array
import logging
import math

import pygame

from config import AUDIO_RATE, AUDIO_VOLUME

LOG = logging.getLogger(__name__)
MELODIES: dict[str, tuple[tuple[float, float], ...]] = {
    "select": ((660, 0.035), (990, 0.045)),
    "move": ((330, 0.045), (440, 0.045), (660, 0.065)),
    "jump": ((220, 0.035), (330, 0.035), (550, 0.045), (880, 0.055)),
    "convert": ((1047, 0.035), (1319, 0.04), (1568, 0.055)),
    "error": ((147, 0.055), (110, 0.075)),
    "turn": ((440, 0.035), (554, 0.045)),
    "victory": ((523, 0.09), (659, 0.09), (784, 0.09), (1047, 0.22)),
    "defeat": ((392, 0.10), (330, 0.11), (262, 0.12), (196, 0.22)),
    "draw": ((440, 0.09), (554, 0.09), (440, 0.18)),
}


def synthesize(notes: tuple[tuple[float, float], ...], rate: int, channels: int) -> bytes:
    """Signed 16-bit PCM with short envelopes to avoid harsh boundary clicks."""
    samples = array("h")
    phase = 0.0
    for frequency, duration in notes:
        count = int(rate * duration)
        for index in range(count):
            phase = (phase + frequency / rate) % 1.0
            square = 1.0 if phase < 0.5 else -1.0
            fm = math.sin(2 * math.pi * phase + 1.5 * math.sin(4 * math.pi * phase))
            envelope = min(1.0, index / max(1, rate * 0.003),
                           (count - index - 1) / max(1, rate * 0.016))
            value = int((0.38 * square + 0.62 * fm) * envelope * 13000)
            samples.extend([value] * channels)
    return samples.tobytes()


class Audio:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.available = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(AUDIO_RATE, -16, 1, 512)
            rate, sample_format, channels = pygame.mixer.get_init()
            if sample_format != -16:
                raise pygame.error("Audio device did not provide signed 16-bit output")
            pygame.mixer.set_num_channels(8)
            for name, notes in MELODIES.items():
                sound = pygame.mixer.Sound(buffer=synthesize(notes, rate, channels))
                sound.set_volume(AUDIO_VOLUME)
                self.sounds[name] = sound
            self.available = True
        except pygame.error as exc:
            LOG.warning("Audio unavailable; continuing silently: %s", exc)

    def play(self, name: str) -> None:
        if self.enabled and self.available and name in self.sounds:
            self.sounds[name].play()

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        if not self.enabled and self.available:
            pygame.mixer.stop()
        return self.enabled
