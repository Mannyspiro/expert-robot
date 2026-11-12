#!/usr/bin/env python3
"""Local-only OpenAI-compatible TTS server backed by Kokoro ONNX.

POST /v1/audio/speech with {"input": "...", "voice": "af_heart"} returns WAV.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import struct
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MAX_TEXT_CHARS = 5000
DEFAULT_VOICE = "af_heart"
DEFAULT_LANGUAGE = "en-us"


def validate_request(payload: Any) -> tuple[str, str, str, float]:
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    text = payload.get("input")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("'input' must be a non-empty string")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"'input' exceeds {MAX_TEXT_CHARS} characters")
    voice = payload.get("voice", DEFAULT_VOICE)
    language = payload.get("language", DEFAULT_LANGUAGE)
    response_format = payload.get("response_format", "wav")
    speed = payload.get("speed", 1.0)
    if not isinstance(voice, str) or not voice:
        raise ValueError("'voice' must be a non-empty string")
    if language not in ("en-us", "en-gb"):
        raise ValueError("supported languages in this MVP: en-us, en-gb")
    if response_format != "wav":
        raise ValueError("only response_format='wav' is supported")
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.5 <= float(speed) <= 2.0:
        raise ValueError("'speed' must be between 0.5 and 2.0")
    return text.strip(), voice, language, float(speed)


def wav_bytes(samples: Any, sample_rate: int) -> bytes:
    """Encode mono float samples in [-1, 1] as 16-bit PCM WAV."""
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")
    values = samples.tolist() if hasattr(samples, "tolist") else list(samples)
    if not values:
        raise ValueError("TTS returned no audio samples")
    pcm = bytearray()
    for value in values:
        number = max(-1.0, min(1.0, float(value)))
        pcm.extend(struct.pack("<h", int(round(number * 32767))))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(bytes(pcm))
    return buffer.getvalue()


class KokoroEngine:
    def __init__(self, model_path: str, voices_path: str) -> None:
        from kokoro_onnx import Kokoro
        from kokoro_onnx.tokenizer import Tokenizer

        if not Path(model_path).is_file() or not Path(voices_path).is_file():
            raise FileNotFoundError("Kokoro assets missing; run scripts/models/download_kokoro.sh")
        self._model = Kokoro(model_path, voices_path)
        self._tokenizer = Tokenizer()
        self._voices = set(self._model.get_voices())

    def synthesize(self, text: str, voice: str, language: str, speed: float) -> bytes:
        if voice not in self._voices:
            raise ValueError(f"unknown voice '{voice}'")
        phonemes = self._tokenizer.phonemize(text, lang=language)
        samples, sample_rate = self._model.create(
            phonemes, voice=voice, speed=speed, is_phonemes=True
        )
        return wav_bytes(samples, sample_rate)


class Handler(BaseHTTPRequestHandler):
    engine: KokoroEngine

    def _json(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"ok": True, "engine": "kokoro-onnx", "voices": sorted(self.engine._voices)})
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/v1/audio/speech":
            self._json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("request body must be between 1 byte and 1 MB")
            payload = json.loads(self.rfile.read(length))
            text, voice, language, speed = validate_request(payload)
            audio = self.engine.synthesize(text, voice, language, speed)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._json(400, {"error": "invalid_request", "message": str(exc)})
            return
        except Exception as exc:
            self._json(500, {"error": "synthesis_failed", "message": str(exc)})
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)

    def log_message(self, fmt: str, *args: Any) -> None:
        print("kokoro-tts:", fmt % args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Kokoro TTS server")
    parser.add_argument("--host", default=os.getenv("KOKORO_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("KOKORO_PORT", "8880")))
    parser.add_argument("--model", default=os.getenv("KOKORO_MODEL", "models/voice/kokoro/kokoro-v1.0.onnx"))
    parser.add_argument("--voices", default=os.getenv("KOKORO_VOICES", "models/voice/kokoro/voices-v1.0.bin"))
    args = parser.parse_args()
    Handler.engine = KokoroEngine(args.model, args.voices)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Kokoro TTS listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
