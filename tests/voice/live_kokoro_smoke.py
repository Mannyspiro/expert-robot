#!/usr/bin/env python3
"""Download-backed Avrea smoke: synthesize a short WAV and verify its container."""

import argparse
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from python.voice.kokoro_server import KokoroEngine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/voice/kokoro/kokoro-v1.0.onnx")
    parser.add_argument("--voices", default="models/voice/kokoro/voices-v1.0.bin")
    parser.add_argument("--output", default="artifacts/kokoro-council-smoke.wav")
    args = parser.parse_args()

    engine = KokoroEngine(args.model, args.voices)
    audio = engine.synthesize(
        "Merlin council is ready. Four perspectives, one evidence-first review.",
        "af_heart", "en-us", 1.0
    )
    if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
        raise RuntimeError("Kokoro did not return a valid WAV container")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(audio)
    with wave.open(str(output), "rb") as wav:
        if wav.getnframes() <= 0 or wav.getframerate() <= 0:
            raise RuntimeError("Kokoro WAV contains no audio frames")
        print(f"PASS: {output} ({wav.getnframes()} frames at {wav.getframerate()} Hz)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
