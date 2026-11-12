import io
import struct
import unittest
import wave

from python.voice.kokoro_server import validate_request, wav_bytes


class KokoroContractTests(unittest.TestCase):
    def test_default_request(self):
        text, voice, language, speed = validate_request({"input": "Hello Merlin"})
        self.assertEqual((text, voice, language, speed), ("Hello Merlin", "af_heart", "en-us", 1.0))

    def test_reject_empty_text(self):
        with self.assertRaises(ValueError):
            validate_request({"input": "  "})

    def test_reject_oversized_text(self):
        with self.assertRaises(ValueError):
            validate_request({"input": "x" * 5001})

    def test_reject_unsupported_language(self):
        with self.assertRaises(ValueError):
            validate_request({"input": "bonjour", "language": "fr-fr"})

    def test_reject_invalid_speed(self):
        with self.assertRaises(ValueError):
            validate_request({"input": "Hello", "speed": 3.0})

    def test_wav_header_and_pcm(self):
        data = wav_bytes([0.0, 0.5, -0.5], 24000)
        with wave.open(io.BytesIO(data), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), 24000)
            self.assertEqual(wav.getnframes(), 3)
            frames = wav.readframes(3)
        values = struct.unpack("<hhh", frames)
        self.assertEqual(values[0], 0)
        self.assertGreater(values[1], 16000)
        self.assertLess(values[2], -16000)


if __name__ == "__main__":
    unittest.main()
