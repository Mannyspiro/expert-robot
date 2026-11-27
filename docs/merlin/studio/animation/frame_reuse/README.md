# Save fewer animation frames

Yes. For a held shot, the renderer can replay the same image when the
crop, mouth and blink state are identical. For a small change, a
lossless archive can store a full image occasionally and encode the
difference from the previous image. For camera moves, use a
motion-predictive codec or regenerate from the original layers and camera
keys. The animation renderer now reuses the last composited result for
identical states.

## Pilot measurement

Two 408-frame runs used the same 640 × 360 RGB artwork and acting.
In one run the camera held each shot's initial pose. In the other it
moved according to the Xenomaths plan. Every restored frame's RGB
SHA-256 matched the pre-encoding source. Values include actual archive
overhead, exclude audio and use decimal MB.

| Ready-to-decode format | Held camera | Moving camera |
|---|---:|---:|
| Independent PNG frames, baseline | 180.76 MB | 178.55 MB |
| Only unique PNG frames plus references | 15.51 MB | 173.37 MB |
| Exact previous-frame differences, every 24 frames a full base | 9.11 MB | 122.84 MB |
| Independent FFV1 frames | 131.93 MB | 130.17 MB |
| Lossless H.264 RGB, 24-frame key intervals | **7.98 MB** | **79.12 MB** |

The previous-frame experiment stores a compressed XOR residual, or
repeats the previous frame exactly if its pixels match. It uses a full
PNG whenever the residual would be larger. A checkpoint limits a
single-frame restore to at most 24 records. The benchmark restored
all frames in both regimes and tested a single-frame restore. The
32-frame example also rejected a modified checksum and a missing
last frame.

Keeping the original art, motion and rig plans, and dialogue exposure sheet required
2.82 MB of picture inputs. It also requires the software and a fresh
render. The held-camera re-render changed from 6.46 to 2.41 seconds
after adding last-state reuse, with a byte-for-byte RGB match. On
moving shots it went from 6.07 to 5.97 seconds. These are single local
timing observations with cache and machine-load effects.

## Ranked by use

1. **Editable project.** Save the source art, camera keys, mouth/blink
   controls, audio, and software versions. Regenerate from the original
   layers after changes. Continue sending exact holds to the encoder so
   the timing stays intact.
2. **Compact lossless cache.** Of the ready-to-decode methods tested,
   lossless H.264 RGB was smallest in both regimes. Confirm editor
   support and use a lossless intermediate for future transcodes.
3. **Standalone frame access.** Independent PNG or FFV1 frames are
   useful when a shot is composited or reviewed frame by frame. FFV1
   does not use motion between frames.
4. **Experimental delta cache.** The SQLite example restores exact
   RGB and can expose which frames reuse older data. Prefer the
   measured standard formats for sessions that need interchange.

The [protocol](protocol.json), [Merlin Ideonomy run](Merlin_Ideonomy.json)
and [evidence](Results.json) describe the inputs, 84 considered
combinations, per-method times, and exactness checks. The private
Merlin bridge was disconnected. This run used the versioned research
module from the pinned USB release source. The full OS was not booted.

This study does not establish a general ranking for full-resolution
CG, painterly effects, film grain, transparency, HDR or every editing
app. For 3D, a small camera move can expose previously hidden content
or change reflections. Reuse scene assets and render invalidated
views when exact output matters.

## Try the example

Use Python 3.11+, NumPy and Pillow.

```bash
tool=tools/merlin_studio/animation
python3 "$tool/frame_archive.py" restore Relay_32_Frame_Delta.sqlite3 frame.rgb --frame 17
ffmpeg -f rawvideo -pixel_format rgb24 -video_size 640x360 -i frame.rgb -frames:v 1 frame.png
```

[FFV1 RFC](https://www.rfc-editor.org/rfc/rfc9043.html) and
[FFmpeg RGB lossless encoder documentation](https://www.ffmpeg.org/ffmpeg-codecs.html#libx264_002c-libx264rgb)
describe the standard formats.
