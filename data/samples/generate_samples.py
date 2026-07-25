"""One-off generator for the bundled sample audio tracks.

These are synthetic sine-wave tones (not recordings of real songs), generated
locally with Python's stdlib `wave` module so the project has zero network
dependency and zero licensing ambiguity (see docs/adr/0001-no-llm-local-only-agent.md
for the project's local-only stance). Treat them as CC0 / public-domain
placeholder audio for grading and demo purposes only.

Run this script again to regenerate the files if they are ever deleted:
    python data/samples/generate_samples.py
"""

import math
import os
import struct
import wave

SAMPLE_RATE = 44100
AMPLITUDE = 12000  # keep well under int16 max to avoid clipping/harshness

# (filename, frequency_hz, duration_seconds)
TONES = [
    ("tone_a.wav", 440.0, 3.0),   # A4 concert pitch
    ("tone_b.wav", 523.25, 3.0),  # C5
    ("tone_c.wav", 659.25, 3.0),  # E5
]


def write_tone(path: str, frequency: float, duration: float) -> None:
    n_samples = int(SAMPLE_RATE * duration)
    with wave.open(path, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit PCM
        wav_file.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            # simple fade in/out to avoid clicks at start/end
            fade_len = int(SAMPLE_RATE * 0.05)
            fade = 1.0
            if i < fade_len:
                fade = i / fade_len
            elif i > n_samples - fade_len:
                fade = (n_samples - i) / fade_len
            value = int(AMPLITUDE * fade * math.sin(2 * math.pi * frequency * t))
            frames += struct.pack("<h", value)
        wav_file.writeframes(bytes(frames))


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    for filename, freq, duration in TONES:
        path = os.path.join(here, filename)
        write_tone(path, freq, duration)
        print(f"wrote {path} ({freq} Hz, {duration}s)")


if __name__ == "__main__":
    main()
