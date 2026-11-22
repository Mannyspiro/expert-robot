"""Local, bounded visual/audio feature sensing and synthetic synesthetic cues.

No model inference, semantic object recognition, camera/microphone access, media
playback, network access, person identification or subjective sensation occurs.
Only explicit caller-supplied PNG/WAV bytes are analyzed. Standard library only.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import math
import struct
import wave
import zlib

MAX_MEDIA_BYTES = 256 * 1024
MAX_PIXELS = 512 * 512
MAX_SECONDS = 3
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
SOURCES = frozenset({"user_upload", "camera_snapshot", "screen_snapshot", "microphone_sample", "workspace_file"})
NOTE_NAMES = ("C4", "D4", "E4", "G4", "A4", "C5", "D5", "E5")
NOTE_FREQUENCIES = (261.63, 293.66, 329.63, 392.00, 440.00, 523.25, 587.33, 659.25)
COLORS = ("red", "orange", "yellow", "green", "cyan", "blue", "violet", "neutral")


def _check_bytes(raw: bytes, kind: str) -> None:
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_MEDIA_BYTES:
        raise ValueError(f"{kind} must be 1 to 262144 bytes")


def decode_media(value: str, *, media_type: str) -> bytes:
    """Reject data URLs, whitespace ambiguity, unsupported types and oversize."""
    if media_type not in ("image/png", "audio/wav") or not isinstance(value, str):
        raise ValueError("Supported sensory formats are PNG images and PCM WAV audio")
    if len(value) > ((MAX_MEDIA_BYTES + 2) // 3) * 4:
        raise ValueError("Base64 sensory payload exceeds the byte budget")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Sensory input must be canonical base64 data") from exc
    _check_bytes(raw, media_type)
    if base64.b64encode(raw).decode("ascii") != value:
        raise ValueError("Noncanonical sensory base64 encoding")
    return raw


def _paeth(a: int, b: int, c: int) -> int:
    prediction = a + b - c
    da, db, dc = abs(prediction - a), abs(prediction - b), abs(prediction - c)
    return a if da <= db and da <= dc else b if db <= dc else c


def _png_pixels(raw: bytes):
    """Decode bounded noninterlaced 8-bit RGB/RGBA/gray PNG with verified CRC."""
    _check_bytes(raw, "PNG")
    if not raw.startswith(PNG_MAGIC):
        raise ValueError("PNG signature is invalid")
    offset = len(PNG_MAGIC)
    width = height = channels = None
    parts = []
    seen_idat = False
    ended_idat = False
    ended = False
    chunks = 0
    while offset < len(raw):
        chunks += 1
        if chunks > 100:
            raise ValueError("PNG chunk count exceeds budget")
        if offset + 12 > len(raw):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack_from(">I", raw, offset)[0]
        tag = raw[offset + 4:offset + 8]
        if length > MAX_MEDIA_BYTES or offset + 12 + length > len(raw):
            raise ValueError("PNG chunk length exceeds bounds")
        payload = raw[offset + 8:offset + 8 + length]
        crc = struct.unpack_from(">I", raw, offset + 8 + length)[0]
        if zlib.crc32(tag + payload) & 0xffffffff != crc:
            raise ValueError("PNG chunk CRC is invalid")
        offset += 12 + length
        if tag == b"IHDR":
            if width is not None or length != 13 or seen_idat:
                raise ValueError("Invalid PNG header sequence")
            width, height, bits, mode, comp, filt, interlace = struct.unpack(">IIBBBBB", payload)
            if (not 1 <= width <= 512 or not 1 <= height <= 512
                    or width * height > MAX_PIXELS or bits != 8 or mode not in (0, 2, 6)
                    or comp != 0 or filt != 0 or interlace != 0):
                raise ValueError("Only bounded 8-bit noninterlaced grayscale/RGB/RGBA PNG is supported")
            channels = {0: 1, 2: 3, 6: 4}[mode]
        elif tag == b"IDAT":
            if width is None or ended_idat or ended:
                raise ValueError("Out-of-order PNG pixel stream")
            seen_idat = True
            parts.append(payload)
        elif tag == b"IEND":
            if length or not seen_idat or ended or offset != len(raw):
                raise ValueError("PNG end marker or trailing bytes are invalid")
            ended = True
            break
        else:
            if seen_idat:
                ended_idat = True
            if tag in (b"acTL", b"fcTL", b"fdAT"):
                raise ValueError("Animated PNG is not supported")
            # Unrecognized critical chunks are unsupported. Ancillary metadata
            # must not affect pixels and is never copied to the result.
            if not tag or tag[0] & 0x20 == 0:
                raise ValueError("Unknown critical PNG chunk")
    if not ended or width is None or not parts:
        raise ValueError("Incomplete PNG image")
    row_length = width * channels
    required = (row_length + 1) * height
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(b"".join(parts), required + 1)
    if (len(decoded) != required or not decoder.eof or decoder.unused_data
            or decoder.unconsumed_tail):
        raise ValueError("PNG pixel stream length, compression or integrity differs")
    rows = []
    pos = 0
    previous = bytearray(row_length)
    for _ in range(height):
        flt = decoded[pos]
        pos += 1
        row = bytearray(decoded[pos:pos + row_length])
        pos += row_length
        if flt not in (0, 1, 2, 3, 4):
            raise ValueError("Unsupported PNG row filter")
        for j in range(row_length):
            left = row[j - channels] if j >= channels else 0
            above = previous[j]
            up_left = previous[j - channels] if j >= channels else 0
            predictor = (0 if flt == 0 else left if flt == 1 else above
                         if flt == 2 else (left + above) // 2 if flt == 3
                         else _paeth(left, above, up_left))
            row[j] = (row[j] + predictor) & 255
        rows.append(row)
        previous = row
    return width, height, channels, rows


def _color_name(rgb: tuple[float, float, float], saturation: float) -> str:
    if saturation < 0.14:
        return "neutral"
    r, g, b = rgb
    hi, lo = max(rgb), min(rgb)
    delta = hi - lo
    if delta <= 0:
        return "neutral"
    if hi == r:
        degrees = (60 * ((g - b) / delta)) % 360
    elif hi == g:
        degrees = 60 * ((b - r) / delta + 2)
    else:
        degrees = 60 * ((r - g) / delta + 4)
    if degrees < 15 or degrees >= 345:
        return "red"
    if degrees < 45:
        return "orange"
    if degrees < 75:
        return "yellow"
    if degrees < 155:
        return "green"
    if degrees < 205:
        return "cyan"
    if degrees < 265:
        return "blue"
    if degrees < 345:
        return "violet"
    return "neutral"


def analyze_png(raw: bytes) -> dict:
    width, height, channels, rows = _png_pixels(raw)
    weighted = [0.0, 0.0, 0.0]
    visible = 0.0
    saturation = 0.0
    brightness = 0.0
    edges = 0
    comparisons = 0
    previous_luma = [None] * width
    region_edges = [0, 0, 0, 0]
    for y, row in enumerate(rows):
        last = None
        for x in range(width):
            pos = x * channels
            if channels == 1:
                rgb = (row[pos],) * 3
                alpha = 1.0
            elif channels == 3:
                rgb = tuple(row[pos:pos + 3])
                alpha = 1.0
            else:
                rgb = tuple(row[pos:pos + 3])
                alpha = row[pos + 3] / 255
            lum = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255
            if alpha > 0:
                visible += alpha
                for k in range(3):
                    weighted[k] += alpha * rgb[k]
                brightness += alpha * lum
                high, low = max(rgb), min(rgb)
                saturation += alpha * ((high - low) / high if high else 0)
            # Transparent pixels have no measured visible edge.
            current = lum if alpha >= 0.9 else None
            quad = (2 if y >= height / 2 else 0) + (1 if x >= width / 2 else 0)
            for neighbor in (last, previous_luma[x]):
                if current is not None and neighbor is not None:
                    comparisons += 1
                    if abs(current - neighbor) > 0.18:
                        edges += 1
                        region_edges[quad] += 1
            last = current
            previous_luma[x] = current
    if not visible:
        raise ValueError("Fully transparent image has no visible pixels to measure")
    rgb_mean = tuple(v / visible for v in weighted)
    normalized = tuple(v / 255 for v in rgb_mean)
    avg_sat = saturation / visible
    avg_lum = brightness / visible
    color = _color_name(normalized, avg_sat)
    salience = ("top_left", "top_right", "bottom_left", "bottom_right")[
        max(range(4), key=lambda i: region_edges[i])]
    return {"schema": "merlin-visual-features/1", "source_sha256": hashlib.sha256(raw).hexdigest(),
            "media_type": "image/png", "width_px": width, "height_px": height,
            "visible_fraction": round(visible / (width * height), 4),
            "mean_rgb": [round(v) for v in rgb_mean],
            "luminance_0_1": round(avg_lum, 5),
            "saturation_0_1": round(avg_sat, 5),
            "edge_density_0_1": round(edges / max(1, comparisons), 5),
            "most_edged_quadrant": salience,
            "dominant_color_family": color,
            "semantic_object_detection": False, "ocr": False,
            "method": "bounded_stdlib_png_feature_extraction",
            "limitations": "Image features are not scene understanding, object recognition, or calibrated confidence."}


def analyze_wav(raw: bytes) -> dict:
    _check_bytes(raw, "PCM WAV")
    try:
        with wave.open(io.BytesIO(raw), "rb") as wav:
            channels, width, rate, frames = (wav.getnchannels(), wav.getsampwidth(),
                                              wav.getframerate(), wav.getnframes())
            if (channels not in (1, 2) or width != 2 or not 8000 <= rate <= 48000
                    or frames < 1 or frames > MAX_SECONDS * rate):
                raise ValueError("Audio requires 1-2 channels, 16-bit PCM, 8-48kHz, <=3 seconds")
            if wav.getcomptype() != "NONE":
                raise ValueError("Compressed WAV is unsupported")
            pcm = wav.readframes(frames)
            if len(pcm) != frames * channels * 2:
                raise ValueError("Truncated PCM frame samples")
    except (EOFError, wave.Error, struct.error) as exc:
        raise ValueError("Malformed or unsupported PCM WAV") from exc
    samples = struct.unpack("<" + "h" * (frames * channels), pcm)
    monophonic = [sum(samples[i:i + channels]) / (channels * 32768)
                  for i in range(0, len(samples), channels)]
    rms = math.sqrt(sum(v * v for v in monophonic) / frames)
    peak = max(abs(v) for v in monophonic)
    changes = sum((a < 0 <= b) or (b < 0 <= a)
                  for a, b in zip(monophonic, monophonic[1:]))
    return {"schema": "merlin-audio-features/1", "source_sha256": hashlib.sha256(raw).hexdigest(),
            "media_type": "audio/wav", "sample_rate_hz": rate, "channels": channels,
            "duration_s": round(frames / rate, 5),
            "rms_0_1": round(rms, 5), "peak_0_1": round(peak, 5),
            "zero_crossing_rate_hz": round(changes * rate / frames, 2),
            "speech_recognition": False, "sound_classification": False,
            "method": "bounded_stdlib_pcm_measurement",
            "limitations": "Zero crossings are not a reliable pitch estimate or speech transcription."}


def sensory_fusion(*, image: bytes | None = None, audio: bytes | None = None,
                   source: str, consent: bool) -> dict:
    """Explicit one-shot input, no listener, camera driver, recording or side effects."""
    if consent is not True:
        raise PermissionError("Sensory capture/analysis requires explicit user consent")
    if source not in SOURCES:
        raise ValueError("Unknown sensory source")
    if (image is None and audio is None) or (image is not None and audio is not None):
        raise ValueError("Each observation must have one measured modality")
    if image is not None:
        visual = analyze_png(image)
        color = visual["dominant_color_family"]
        brightness = visual["luminance_0_1"]
        intensity = visual["edge_density_0_1"]
        features = visual
        modality = "vision"
    else:
        acoustics = analyze_wav(audio)
        color = "neutral"
        brightness = acoustics["rms_0_1"]
        intensity = acoustics["peak_0_1"]
        features = acoustics
        modality = "hearing"
    # A designed association, not a claim of natural synesthesia. Audio cues are
    # just metadata: playing an original tone would require a separate UI action.
    cue_index = COLORS.index(color) if modality == "vision" else min(7, int(brightness * 8))
    cue = {"schema": "merlin-synesthetic-cue/1",
           "mapping": "deterministic_feature_to_tone_color_v1",
           "tone_label": NOTE_NAMES[cue_index],
           "tone_frequency_hz": NOTE_FREQUENCIES[cue_index],
           "visual_color_family": color if modality == "vision" else COLORS[cue_index],
           "haptic_intensity_0_1": round(min(1.0, intensity), 4),
           "generated_not_observed": True, "playback_performed": False}
    return {"schema": "merlin-sensory-observation/1", "source": source,
            "modality": modality, "features": features, "synesthetic_cue": cue,
            "epistemic_status": "measured_low_level_features_plus_synthetic_association",
            "physical_sensor_started_by_server": False,
            "raw_media_retained": False,
            "network_transmission_by_sensing": False,
            "independent_verification": False, "action_authority": False}
